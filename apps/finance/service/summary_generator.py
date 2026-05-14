# coding=utf-8
"""
    @project: MaxKB
    @file： summary_generator.py
    @desc: AI-generated one-line summaries for candidate documents in a
    materials task.

    Gate 5 implementation: load the document's paragraph content from the
    knowledge module, truncate to a safe context budget, and call the
    workspace's default chat model for a 50-150 字 Chinese summary. Falls
    back to a recognisable placeholder string whenever:

      * the document has no content,
      * the workspace has no LLM configured,
      * the LLM call fails or returns an empty response.
"""
from __future__ import annotations

from uuid import UUID

from common.utils.logger import maxkb_logger

from finance.service.llm import chat_completion


# Safety limit — most providers handle 8K tokens comfortably for a single-
# turn summary; truncating at the character level avoids tokenizer round-trips.
_MAX_CONTENT_CHARS = 8000

_LLM_SYSTEM_PROMPT = (
    '你是融资材料分析助手。请对下面的文档内容生成 50-150 字的中文概要，'
    '突出对融资场景有用的关键事实（金额、期限、当事方、风险点等）。'
)

_STUB_TEMPLATE = '[AI 概要：{name} 的内容摘要将在 Gate 5 接入真实 LLM 后生成]'


def _load_document_content(document_id) -> tuple[str, str]:
    """
    Return `(document_name, content)`. Both are best-effort — on any error
    we return the raw id as the name and an empty string for content so the
    caller can decide whether to fall back to the stub.
    """
    document_name = str(document_id)
    content = ''
    try:
        from knowledge.models import Document, Paragraph  # local import: avoids
        # forcing knowledge app import at module load (helps test isolation).

        doc = Document.objects.filter(id=document_id).first()
        if doc is None:
            return document_name, content
        if getattr(doc, 'name', ''):
            document_name = doc.name

        # Pull paragraphs in document order. We cap the queryset early — even
        # if a document has 10K paragraphs we only need the first 8K chars.
        parts: list[str] = []
        budget = _MAX_CONTENT_CHARS
        for para in (
            Paragraph.objects.filter(document_id=document_id, is_active=True)
            .order_by('position')
            .values_list('content', flat=True)
            .iterator(chunk_size=50)
        ):
            if not para:
                continue
            parts.append(para)
            budget -= len(para)
            if budget <= 0:
                break
        content = '\n'.join(parts).strip()
        if len(content) > _MAX_CONTENT_CHARS:
            content = content[:_MAX_CONTENT_CHARS]
    except Exception as e:  # noqa: BLE001 — must not raise
        maxkb_logger.warning(f'[finance.summary] document load failed: {e}')
    return document_name, content


def generate_summary_for_document(document_id, workspace_id: UUID) -> str:
    """
    Produce a one-line Chinese-language AI summary of `document_id`.

    LLM-backed. Falls back to a stub string whenever the model is unavailable
    or returns nothing useful. Never raises.
    """
    document_name, content = _load_document_content(document_id)
    stub = _STUB_TEMPLATE.format(name=document_name)

    if not content:
        return stub

    ws_id = str(workspace_id) if workspace_id is not None else 'default'
    user_prompt = f'文档名称：{document_name}\n\n---\n\n{content}'
    try:
        text = chat_completion(ws_id, _LLM_SYSTEM_PROMPT, user_prompt)
    except Exception as e:  # noqa: BLE001 — chat_completion itself shouldn't raise,
        # but defend in depth: a 500 here would surface as a finance-API failure.
        maxkb_logger.warning(f'[finance.summary] chat_completion raised: {e}')
        return stub

    if not text:
        return stub
    summary = text.strip()
    if not summary:
        return stub
    return summary
