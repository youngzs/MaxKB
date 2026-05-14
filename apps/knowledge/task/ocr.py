# coding=utf-8
"""
@project: maxkb
@file: ocr.py
@desc: 异步 PDF OCR 任务。把 vision-LLM OCR 从 split 请求线程里挪出来，避免
       nginx / gunicorn 超时。

工作流：
  1. 用户上传 PDF
  2. /document/split  →  PdfSplitHandle.handle（enable_sync_ocr=False）秒返；
                        扫描页此时仅产出空段落
  3. /document POST   →  doc + paragraphs 落库 + post_embedding 回调
  4. post_embedding   →  enqueue ocr_pdf_document（本任务）
  5. 本任务在 celery worker 内：
       a. 拉源 PDF bytes
       b. 重跑 PdfSplitHandle.handle，但临时把 enable_sync_ocr 置 True
          让 _try_ocr_empty_pages 真正调用视觉模型
       c. 若新内容比库里现存的多，删旧 paragraph、按 OCR 文本重新写入
       d. 调 embedding_by_document 让向量库跟上

注意 import 约定：只有标准库 / 外部包 / celery_app / logger 在模块顶层 import。
所有 knowledge.* 与 common.handle.* 的 import 都延迟到函数体内 —— 这样
knowledge/task/__init__.py 里的 `from . import ocr` 触发本模块加载时不会引入
任何循环依赖，celery worker 也能在启动时稳定注册到 celery:ocr_pdf_document。
"""
import io
import re
import traceback

import uuid_utils.compat as uuid
from celery_once import QueueOnce
from django.db.models import QuerySet, Max

from common.utils.logger import maxkb_logger
from ops import celery_app


# 与 pdf_split_handle.py 中一致；放这里只用来判断"是不是悬挂图片占位段"。
_DANGLING_IMG_RE = re.compile(r'^(?:!\[image\]\(image_\d+_\d+\)\s*)+$')


class _BytesUpload:
    """Mimic Django UploadedFile so PdfSplitHandle.handle() can consume it."""

    def __init__(self, data: bytes, name: str):
        self._data = data
        self.name = name
        self.size = len(data)

    def chunks(self):
        buf = io.BytesIO(self._data)
        while True:
            chunk = buf.read(64 * 1024)
            if not chunk:
                return
            yield chunk

    # PdfSplitHandle.support() probes some callers via read/seek; the OCR
    # call-site bypasses support(), but keep these for safety.
    def read(self, *a, **kw):
        return self._data

    def seek(self, *a, **kw):
        return 0


def _get_source_pdf_bytes(document) -> bytes | None:
    """Resolve the upload's source File row and return its raw bytes, or None."""
    from knowledge.models import File

    file_id = (document.meta or {}).get('source_file_id')
    if not file_id:
        return None
    f = QuerySet(File).filter(id=file_id).first()
    if not f:
        return None
    if not (f.file_name or '').lower().endswith('.pdf'):
        return None
    try:
        return f.get_bytes()
    except Exception as e:
        maxkb_logger.error(f"OCR task: failed to read source PDF bytes for {document.id}: {e}")
        return None


def _document_needs_ocr(document) -> bool:
    """Heuristic: if every existing paragraph is empty or only contains
    dangling image placeholders, the document was a scan that pypdf
    couldn't read — worth trying OCR. Saves a render+LLM round-trip
    for ordinary text PDFs."""
    from knowledge.models import Paragraph

    paras = list(Paragraph.objects.filter(document_id=document.id).values_list('content', flat=True))
    if not paras:
        return True
    for content in paras:
        s = (content or '').strip()
        if not s:
            continue
        if _DANGLING_IMG_RE.match(s):
            continue
        # Found a paragraph with real text — skip OCR.
        return False
    return True


def _replace_paragraphs(document, content_list):
    """Wipe existing paragraphs (and their vectors) and bulk-insert
    OCR-derived ones. Skip any paragraph that's only image placeholders."""
    from knowledge.models import Document, Paragraph
    from knowledge.serializers.paragraph import delete_problems_and_mappings
    from knowledge.task.embedding import delete_embedding_by_document

    old_ids = list(
        Paragraph.objects.filter(document_id=document.id).values_list('id', flat=True)
    )
    if old_ids:
        delete_problems_and_mappings([str(pid) for pid in old_ids])
    delete_embedding_by_document(str(document.id))
    Paragraph.objects.filter(document_id=document.id).delete()

    new_rows = []
    total_chars = 0
    skipped_image_only = 0
    for item in content_list:
        if isinstance(item, dict):
            title = (item.get('title') or '')[:256]
            content = item.get('content') or ''
        else:
            title = ''
            content = str(item)
        stripped = content.strip()
        if not stripped:
            continue
        if _DANGLING_IMG_RE.match(stripped):
            skipped_image_only += 1
            continue
        # Also clean any trailing run of dangling placeholders glued onto
        # real text by the splitter.
        cleaned = re.sub(
            r'(?:!\[image\]\(image_\d+_\d+\)\s*)+$',
            '',
            stripped,
        ).strip()
        if not cleaned:
            skipped_image_only += 1
            continue
        total_chars += len(cleaned)
        new_rows.append(
            Paragraph(
                id=uuid.uuid7(),
                document_id=document.id,
                knowledge_id=document.knowledge_id,
                title=title,
                content=cleaned,
            )
        )
    if new_rows:
        max_position = Paragraph.objects.filter(document_id=document.id).aggregate(
            max_position=Max('position')
        )['max_position'] or 0
        for i, p in enumerate(new_rows):
            p.position = max_position + i + 1
        Paragraph.objects.bulk_create(new_rows)
    Document.objects.filter(id=document.id).update(char_length=total_chars)
    return len(new_rows), skipped_image_only, total_chars


@celery_app.task(
    base=QueueOnce,
    once={'keys': ['document_id']},
    name='celery:ocr_pdf_document',
)
def ocr_pdf_document(document_id):
    """Run vision-LLM OCR on a scanned PDF asynchronously.

    Safe to enqueue for any document; bails out cheaply if the doc isn't
    a PDF or its existing paragraphs already contain text."""
    from common.handle.impl.text.pdf_split_handle import PdfSplitHandle
    from knowledge.models import Document
    from knowledge.serializers.common import get_embedding_model_id_by_knowledge_id
    from knowledge.task.embedding import embedding_by_document

    try:
        document = QuerySet(Document).filter(id=document_id).first()
        if document is None:
            maxkb_logger.info(f"OCR task: document {document_id} no longer exists; skipping.")
            return

        if not _document_needs_ocr(document):
            maxkb_logger.info(f"OCR task: document {document_id} already has text; skipping.")
            return

        pdf_bytes = _get_source_pdf_bytes(document)
        if pdf_bytes is None:
            maxkb_logger.info(
                f"OCR task: document {document_id} has no source PDF file; skipping."
            )
            return

        handle = PdfSplitHandle()
        handle.enable_sync_ocr = True  # turn OCR on for THIS invocation only

        fake_upload = _BytesUpload(pdf_bytes, document.name or 'document.pdf')
        try:
            result = handle.handle(
                fake_upload,
                pattern_list=None,
                with_filter=False,
                limit=4096,
                get_buffer=lambda *a, **kw: None,
                save_image=lambda *a, **kw: None,
            )
        except Exception as e:
            maxkb_logger.error(
                f"OCR task: PdfSplitHandle failed for {document_id}: {e}\n{traceback.format_exc()}"
            )
            return

        content_list = (result or {}).get('content') or []
        if not content_list:
            maxkb_logger.info(
                f"OCR task: PdfSplitHandle returned no content for {document_id}; skipping."
            )
            return

        # Compute how much real (non-placeholder) text we recovered. If it's
        # not strictly more than what's already in the DB, leave things alone.
        new_real_chars = 0
        for item in content_list:
            c = (item.get('content') if isinstance(item, dict) else str(item)) or ''
            if not c.strip() or _DANGLING_IMG_RE.match(c.strip()):
                continue
            new_real_chars += len(c)
        if new_real_chars <= (document.char_length or 0):
            maxkb_logger.info(
                f"OCR task: no new text to add for {document_id} "
                f"(new={new_real_chars}, existing char_length={document.char_length}); skipping."
            )
            return

        inserted, skipped, total = _replace_paragraphs(document, content_list)
        maxkb_logger.info(
            f"OCR task: document {document_id} -> {inserted} paragraph(s), "
            f"{total} chars (skipped {skipped} image-only)."
        )

        # Re-queue embedding so vectors reflect the new content.
        try:
            embedding_model_id = get_embedding_model_id_by_knowledge_id(document.knowledge_id)
            embedding_by_document.delay(str(document.id), embedding_model_id)
        except Exception as e:
            # AlreadyQueued / model lookup errors are non-fatal; logged for ops.
            maxkb_logger.warning(
                f"OCR task: post-embedding enqueue failed for {document_id}: {e}"
            )
    except Exception as e:
        maxkb_logger.error(
            f"OCR task: unexpected failure on {document_id}: {e}\n{traceback.format_exc()}"
        )


def enqueue_ocr_if_pdf(document_id) -> bool:
    """Enqueue ocr_pdf_document for a freshly-created document. Safe no-op
    if the document doesn't exist, isn't a PDF, or the task is already
    queued (celery_once handles dedup)."""
    from knowledge.models import Document, File

    try:
        document = QuerySet(Document).filter(id=document_id).first()
        if document is None:
            return False
        file_id = (document.meta or {}).get('source_file_id')
        if not file_id:
            return False
        f = QuerySet(File).filter(id=file_id).first()
        if f is None or not (f.file_name or '').lower().endswith('.pdf'):
            return False
        ocr_pdf_document.delay(str(document_id))
        return True
    except Exception as e:
        maxkb_logger.warning(f"enqueue_ocr_if_pdf({document_id}) failed: {e}")
        return False
