# coding=utf-8
"""
@project: maxkb
@Author：虎
@file： text_split_handle.py
@date：2024/3/27 18:19
@desc:
"""

import concurrent.futures
import os
import re
import tempfile
import time
import traceback
from typing import List

from pypdf import PdfReader
from pypdf.generic import Destination
from django.utils.translation import gettext_lazy as _

from common.handle.base_split_handle import BaseSplitHandle
from common.handle.impl.ocr import OcrConfigError, get_ocr_provider
from common.utils.logger import maxkb_logger
from common.utils.markdown_table import chunk_markdown_table
from common.utils.split_model import SplitModel, smart_split_paragraph

# 识别 Markdown 表格行：以 | 开头、以 | 结尾的非空行（允许首尾空白）
_MD_TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
# 识别 Markdown 表格的分隔行：| --- | --- | 形式（允许 :--- / ---: 对齐写法）
_MD_TABLE_SEP_RE = re.compile(r'^\s*\|(?:\s*:?-{1,}:?\s*\|)+\s*$')


def _parse_md_table_row(line: str) -> list:
    """把一行 Markdown 表格行拆成单元格列表。
    去掉首尾的 | 后按未转义的 | 分割；\\| 还原成字面量 |。"""
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    # 按未转义的 | 分割（前面不是反斜杠）
    parts = re.split(r'(?<!\\)\|', s)
    return [p.strip().replace('\\|', '|') for p in parts]


def _split_text_preserving_md_tables(text: str, split_model: 'SplitModel') -> list:
    """拆分文本，但把其中的 Markdown 表格块整体抽出来做表格感知分块。

    OCR 后的页面文本里如果含有 Markdown 表格（连续的 | ... | 行 + |---| 分隔行），
    直接喂给通用 split_model 会把表格的行切碎、丢掉表头上下文。这里：
      - 逐行扫描，识别出「表头行 + 分隔行 + 若干数据行」构成的表格块
      - 表格块用 chunk_markdown_table 分块，每块都带表头（全局视图）
      - 表格块之间的普通文本仍走原有的 split_model.parse
    非表格 PDF 不会命中任何表格块，等价于原行为。
    """
    lines = text.split('\n')
    paragraphs = []
    buffer_lines = []  # 累积的非表格文本

    def flush_text():
        if not buffer_lines:
            return
        chunk_text = '\n'.join(buffer_lines).strip()
        buffer_lines.clear()
        if chunk_text:
            paragraphs.extend(split_model.parse(chunk_text))

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # 表格块起点：当前行是表格行，且下一行是分隔行
        if (
            _MD_TABLE_ROW_RE.match(line)
            and i + 1 < n
            and _MD_TABLE_SEP_RE.match(lines[i + 1])
        ):
            header_cells = _parse_md_table_row(line)
            j = i + 2
            data_rows = []
            while j < n and _MD_TABLE_ROW_RE.match(lines[j]) and not _MD_TABLE_SEP_RE.match(lines[j]):
                data_rows.append(_parse_md_table_row(lines[j]))
                j += 1
            # 表格块结束，先收口前面的普通文本
            flush_text()
            if data_rows:
                for chunk in chunk_markdown_table(header_cells, data_rows):
                    paragraphs.append({'title': '', 'content': chunk})
            else:
                # 只有表头没有数据行，当普通文本处理
                buffer_lines.append(line)
                buffer_lines.append(lines[i + 1])
            i = j
            continue
        buffer_lines.append(line)
        i += 1

    flush_text()
    return paragraphs

# 当 pypdf 从一页抽到的文字短于该阈值时，认为是扫描页，尝试 OCR fallback
_OCR_PAGE_TEXT_THRESHOLD = 10
# OCR 时 PDF 页面渲染 DPI；越高越清晰但越慢/越占内存。
# 300 DPI 比 200 明显更锐利；配合 image_preprocess 的灰度化，字节体积仍可控。
_OCR_PAGE_DPI = 300
# 空白页 OCR 的并发度。每页一次视觉模型调用是 IO 密集型（等远端 LLM），
# 用线程池并发能把 41 页 PDF 从 ~14 分钟串行降到 ~3 分钟。
# 每页调用本身已有 120s 硬超时（见 vision_llm_provider），并发池只需等所有
# future 收敛即可，不再叠加外层超时。可用 MAXKB_OCR_CONCURRENCY 调整。
_OCR_MAX_CONCURRENCY = int(os.environ.get('MAXKB_OCR_CONCURRENCY', '6'))

default_pattern_list = [
    re.compile("(?<=^)# .*|(?<=\\n)# .*"),
    re.compile("(?<=\\n)(?<!#)## (?!#).*|(?<=^)(?<!#)## (?!#).*"),
    re.compile("(?<=\\n)(?<!#)### (?!#).*|(?<=^)(?<!#)### (?!#).*"),
    re.compile("(?<=\\n)(?<!#)#### (?!#).*|(?<=^)(?<!#)#### (?!#).*"),
    re.compile("(?<=\\n)(?<!#)##### (?!#).*|(?<=^)(?<!#)##### (?!#).*"),
    re.compile("(?<=\\n)(?<!#)###### (?!#).*|(?<=^)(?<!#)###### (?!#).*"),
    re.compile("(?<!\n)\n\n+"),
]


def check_links_in_pdf(doc):
    for page in doc.pages:
        if PdfSplitHandle.get_internal_links(doc, page):
            return True
    return False


def get_pdf_object(value):
    if hasattr(value, "get_object"):
        return value.get_object()
    return value


class PdfSplitHandle(BaseSplitHandle):
    # OCR 默认走 celery 异步任务（apps/knowledge/task/ocr.py），避免阻塞 split 请求线程。
    # 想在 split 同步路径里跑 OCR（旧行为），在调用前把这个属性置 True。
    enable_sync_ocr = False

    def handle(
        self,
        file,
        pattern_list: List,
        with_filter: bool,
        limit: int,
        get_buffer,
        save_image,
    ):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # 将上传的文件保存到临时文件中
            for chunk in file.chunks():
                temp_file.write(chunk)
            # 获取临时文件的路径
            temp_file_path = temp_file.name

        try:
            with open(temp_file_path, "rb") as pdf_file:
                pdf_document = PdfReader(pdf_file)
                if type(limit) is str:
                    limit = int(limit)
                if type(with_filter) is str:
                    with_filter = with_filter.lower() == "true"
                # 处理有目录的pdf
                result = self.handle_toc(pdf_document, limit)
                if result is not None:
                    return {"name": file.name, "content": result}

                # 没目录但是有链接的pdf
                result = self.handle_links(
                    pdf_document, pattern_list, with_filter, limit
                )
                if result is not None and len(result) > 0:
                    return {"name": file.name, "content": result}

                # 没有目录的pdf
                content = self.handle_pdf_content(
                    file, pdf_document, pdf_path=temp_file_path,
                    enable_ocr=self.enable_sync_ocr,
                )

                if pattern_list is not None and len(pattern_list) > 0:
                    split_model = SplitModel(pattern_list, with_filter, limit)
                else:
                    split_model = SplitModel(
                        default_pattern_list, with_filter=with_filter, limit=limit
                    )
        except BaseException as e:
            maxkb_logger.error(
                f"File: {file.name}, error: {e}, {traceback.format_exc()}"
            )
            return {"name": file.name, "content": []}
        finally:
            # 处理完后可以删除临时文件
            os.remove(temp_file_path)

        # OCR 后的页面文本可能含 Markdown 表格（见 DEFAULT_OCR_PROMPT）。
        # 表格块走表格感知分块（每块带表头），其余文本仍走通用 split_model。
        # 纯文本 PDF 不含表格块时等价于原来的 split_model.parse(content)。
        return {
            "name": file.name,
            "content": _split_text_preserving_md_tables(content, split_model),
        }

    @staticmethod
    def _ocr_pdf_page(pdf_path, page_num, ocr_provider):
        """渲染指定页为 PNG bytes，喂给 OCR provider。
        失败时抛异常，由上层 catch 并记日志，不阻断整本 PDF 处理。"""
        import fitz  # pymupdf；在用户启用 OCR 之前不会被 import
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=_OCR_PAGE_DPI)
            png_bytes = pix.tobytes('png')
        return ocr_provider.recognize(png_bytes)

    @staticmethod
    def _ocr_pdf_page_with_retry(pdf_path, page_num, ocr_provider, retries=1):
        """带重试的单页 OCR。
        - _ocr_pdf_page 抛异常、或返回空/纯空白文本，都视为失败并重试
        - 重试之间 sleep 2s，避开 provider 的瞬时抖动（限流 / 连接复位）
        - 重试耗尽后记 warning 并返回 ''（让该页保持空白，绝不抛出）
        并发 OCR 循环调用的是本函数，而不是 _ocr_pdf_page。"""
        attempts = retries + 1
        last_err = None
        for attempt in range(1, attempts + 1):
            try:
                ocr_text = PdfSplitHandle._ocr_pdf_page(pdf_path, page_num, ocr_provider)
                if ocr_text and ocr_text.strip():
                    return ocr_text
                last_err = 'empty/whitespace-only result'
            except Exception as e:
                last_err = e
            if attempt < attempts:
                maxkb_logger.info(
                    f"PDF OCR page {page_num + 1} attempt {attempt}/{attempts} "
                    f"failed ({last_err}); retrying in 2s"
                )
                time.sleep(2)
        maxkb_logger.warning(
            f"PDF OCR page {page_num + 1} gave up after {attempts} attempt(s): {last_err}"
        )
        return ''

    @staticmethod
    def _try_ocr_empty_pages(pdf_path, page_lines):
        """对 page_lines 中空（或几乎空）的页做 OCR fallback。
        - OCR provider 只在确实有空页时才加载（懒初始化）
        - OCR 未配置时直接跳过，不影响纯文本 PDF
        - 单页失败不影响其他页（错误隔离 + 单页重试）
        - 渲染依赖 pymupdf（fitz），未安装时记 warning 并跳过
        - 各空白页用线程池并发 OCR，结果先收集到 dict 再统一回写 page_lines，
          避免多线程直接写同一个 list（虽然写不同下标在 CPython 是安全的，
          collect-then-apply 更稳妥也更易读）
        """
        empty_indices = [
            i for i, lines in enumerate(page_lines)
            if sum(len(t) for t, _ in lines) < _OCR_PAGE_TEXT_THRESHOLD
        ]
        if not empty_indices:
            return  # 全文本 PDF 走这条快路

        # 懒加载 OCR provider
        try:
            from system_manage.serializers.ocr_setting import OcrSettingSerializer
            ocr_provider = get_ocr_provider(OcrSettingSerializer.one())
        except OcrConfigError as e:
            maxkb_logger.info(
                f"PDF has {len(empty_indices)} scanned page(s) but OCR is not configured; skipping. ({e})"
            )
            return
        except Exception as e:
            maxkb_logger.error(f"PDF OCR provider init failed: {e}")
            return

        # 校验 pymupdf 可用
        try:
            import fitz  # noqa: F401
        except ImportError:
            maxkb_logger.warning(
                "pymupdf is not installed; cannot OCR scanned PDF pages. "
                "pip install pymupdf to enable."
            )
            return

        # 并发 OCR：每个空白页提交一个 _ocr_pdf_page_with_retry 任务。
        # 单页内部已有 120s 硬超时 + 重试，这里不再叠加外层超时，只等全部收敛。
        max_workers = max(1, min(_OCR_MAX_CONCURRENCY, len(empty_indices)))
        results: dict[int, list] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(
                    PdfSplitHandle._ocr_pdf_page_with_retry, pdf_path, idx, ocr_provider
                ): idx
                for idx in empty_indices
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    ocr_text = future.result()
                except Exception as e:
                    # _ocr_pdf_page_with_retry 不抛异常；这里只是兜底，
                    # 保证单页崩溃绝不影响其他页。
                    maxkb_logger.error(f"PDF OCR failed on page {idx + 1}: {e}")
                    continue
                if not ocr_text or not ocr_text.strip():
                    continue
                # OCR 文本无字号；填 0，后续会被归类为正文段落
                results[idx] = [
                    (line.strip(), 0) for line in ocr_text.split('\n') if line.strip()
                ]
                maxkb_logger.info(
                    f"PDF OCR recovered page {idx + 1}: {len(ocr_text)} chars"
                )

        # 收集完毕后统一回写
        for idx, lines in results.items():
            page_lines[idx] = lines

        recovered = len(results)
        failed = len(empty_indices) - recovered
        maxkb_logger.info(
            f"PDF OCR: {recovered}/{len(empty_indices)} pages recovered, "
            f"{failed} failed/empty"
        )

    @staticmethod
    def handle_pdf_content(file, pdf_document, pdf_path=None, enable_ocr=False):
        # 第一步:收集所有字体大小
        font_sizes = []
        page_lines = []
        for page in pdf_document.pages:
            lines = PdfSplitHandle.extract_page_lines(page)
            page_lines.append(lines)
            for line_text, font_size in lines:
                if line_text and font_size > 0:
                    font_sizes.append(font_size)

        # 扫描页 OCR fallback。默认走 celery 异步任务（避免阻塞 split 请求），
        # 仅当调用方显式开启 enable_ocr 时才在本线程跑 OCR。
        if pdf_path and enable_ocr:
            PdfSplitHandle._try_ocr_empty_pages(pdf_path, page_lines)

        # 计算正文字体大小(众数)
        if not font_sizes:
            body_font_size = 12
        else:
            from collections import Counter

            body_font_size = Counter(font_sizes).most_common(1)[0][0]

        # 第二步:提取内容
        content = ""
        for page_num, page in enumerate(pdf_document.pages):
            start_time = time.time()

            for text, font_size in page_lines[page_num]:
                if not text:
                    continue

                # 根据与正文字体的差值判断
                size_diff = font_size - body_font_size

                if size_diff > 2:  # 明显大于正文
                    content += f"## {text}\n\n"
                elif size_diff > 0.5:  # 略大于正文
                    content += f"### {text}\n\n"
                else:  # 正文
                    content += f"{text}\n"

            # NOTE: 旧版本会在这里给每个内嵌图片输出
            #   ![image](image_<page>_<index>)
            # 占位符，但 image_<page>_<index> 不对应任何已保存的 File，前端
            # 渲染只能看到一堆"破图"。源 PDF 始终可在文档详情里下载，所以
            # 直接丢弃这些悬挂引用，不再污染段落。需要图片的话需要先把
            # 内嵌图片走 save_image 入库并改写 markdown，再恢复输出。
            content = content.replace("\0", "")

            elapsed_time = time.time() - start_time
            maxkb_logger.debug(
                f"File: {file.name}, Page: {page_num + 1}, Time: {elapsed_time:.3f}s"
            )

        return content

    @staticmethod
    def extract_page_lines(page):
        lines = []
        current_text = []
        current_sizes = []

        def flush_line():
            text = "".join(current_text).strip()
            if text:
                font_size = current_sizes[0] if current_sizes else 0
                lines.append((text, font_size))
            current_text.clear()
            current_sizes.clear()

        def visitor_text(text, cm, tm, font_dict, font_size):
            if text is None:
                return
            parts = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            for index, part in enumerate(parts):
                current_text.append(part)
                if part.strip() and font_size:
                    current_sizes.append(float(font_size))
                if index < len(parts) - 1:
                    flush_line()

        try:
            page.extract_text(visitor_text=visitor_text)
        except BaseException:
            text = PdfSplitHandle.extract_page_text(page)
            return [(line.strip(), 0) for line in text.splitlines() if line.strip()]
        flush_line()
        if lines:
            return lines

        text = page.extract_text() or ""
        return [(line.strip(), 0) for line in text.splitlines() if line.strip()]

    @staticmethod
    def get_page_image_count(page):
        try:
            return len(page.images)
        except BaseException:
            return 0

    @staticmethod
    def extract_page_text(page):
        return (page.extract_text() or "").replace("\0", "")

    @staticmethod
    def get_toc(doc):
        try:
            outline = doc.outline
        except BaseException:
            return []

        toc = []
        PdfSplitHandle.collect_toc(doc, outline, 1, toc)
        return toc

    @staticmethod
    def collect_toc(doc, outline, level, toc):
        for item in outline:
            if isinstance(item, list):
                PdfSplitHandle.collect_toc(doc, item, level + 1, toc)
                continue

            page_number = PdfSplitHandle.get_destination_page_number(doc, item)
            if page_number is None:
                continue

            title = getattr(item, "title", None)
            if title is None and hasattr(item, "get"):
                title = item.get("/Title")
            if title is None:
                title = str(item)
            toc.append((level, str(title), page_number))

    @staticmethod
    def handle_toc(doc, limit):
        # 找到目录
        toc = PdfSplitHandle.get_toc(doc)
        if toc is None or len(toc) == 0:
            return None

        # 创建存储章节内容的数组
        chapters = []
        # 累计真实抽到的正文长度（不含 fallback 成 title 的占位），用于判断是否为扫描版
        total_real_chapter_text_len = 0

        # 遍历目录并按章节提取文本
        for i, entry in enumerate(toc):
            level, title, start_page = entry
            chapter_title = title
            # 确定结束页码，如果是最后一个章节则到文档末尾
            if i + 1 < len(toc):
                end_page = toc[i + 1][2] - 1
            else:
                end_page = len(doc.pages) - 1
            end_page = max(start_page, end_page)

            # 去掉标题中的符号
            title = PdfSplitHandle.handle_chapter_title(title)

            # 提取该章节的文本内容
            chapter_text = ""
            for page_num in range(start_page, end_page + 1):
                text = PdfSplitHandle.extract_page_text(doc.pages[page_num])
                text = re.sub(r"(?<!。)\n+", "", text)
                text = re.sub(r"(?<!.)\n+", "", text)
                # print(f'title: {title}')

                idx = text.find(title)
                if idx > -1:
                    text = text[idx + len(title) :]

                if i + 1 < len(toc):
                    _level, next_title, next_start_page = toc[i + 1]
                    next_title = PdfSplitHandle.handle_chapter_title(next_title)
                    # print(f'next_title: {next_title}')
                    idx = text.find(next_title)
                    if idx > -1:
                        text = text[:idx]

                chapter_text += text  # 提取文本

            # Null characters are not allowed.
            chapter_text = chapter_text.replace("\0", "")
            total_real_chapter_text_len += len(chapter_text.strip())
            # 限制标题长度
            real_chapter_title = chapter_title[:256]
            # 限制章节内容长度
            if 0 < limit < len(chapter_text):
                split_text = smart_split_paragraph(chapter_text, limit)
                for text in split_text:
                    chapters.append({"title": real_chapter_title, "content": text})
            else:
                chapters.append(
                    {
                        "title": real_chapter_title,
                        "content": chapter_text if chapter_text else real_chapter_title,
                    }
                )
            # 保存章节内容和章节标题

        # 扫描版 PDF 即便带大纲，每章 extract_page_text 也几乎抽不到字。
        # 此时降级到 handle_pdf_content，让 OCR fallback 有机会跑。
        if total_real_chapter_text_len < _OCR_PAGE_TEXT_THRESHOLD * max(1, len(toc)):
            maxkb_logger.info(
                f"PDF TOC produced near-empty chapters "
                f"(total {total_real_chapter_text_len} chars over {len(toc)} entries); "
                f"falling back to full-page extraction so OCR can run."
            )
            return None
        return chapters

    @staticmethod
    def handle_links(doc, pattern_list, with_filter, limit):
        # 检查文档是否包含内部链接
        if not check_links_in_pdf(doc):
            return
        # 创建存储章节内容的数组
        chapters = []
        toc_start_page = -1
        page_content = ""
        handle_pre_toc = True
        # 累计真实抽到的章节正文长度，用于判断扫描版降级
        total_real_chapter_text_len = 0
        # 遍历 PDF 的每一页，查找带有目录链接的页
        for page_num, page in enumerate(doc.pages):
            links = PdfSplitHandle.get_internal_links(doc, page)
            # 如果目录开始页码未设置，则设置为当前页码
            if len(links) > 0 and toc_start_page < 0:
                toc_start_page = page_num
            if toc_start_page < 0:
                page_content += PdfSplitHandle.extract_page_text(page)
            # 检查该页是否包含内部链接（即指向文档内部的页面）
            for num in range(len(links)):
                link = links[num]
                # 获取链接目标的页面
                dest_page = link["page"]
                rect = link["from"]  # 获取链接的矩形区域
                # 如果目录开始页码包括前言部分，则不处理前言部分
                if dest_page < toc_start_page:
                    handle_pre_toc = False

                # 提取链接区域的文本作为标题
                link_title = PdfSplitHandle.extract_link_title(page, rect)
                if not link_title:
                    link_title = PdfSplitHandle.extract_first_line(doc.pages[dest_page])
                # 提取目标页面内容作为章节开始
                start_page = dest_page
                end_page = dest_page
                # 下一个link
                next_link = links[num + 1] if num + 1 < len(links) else None
                next_link_title = None
                if next_link is not None:
                    next_link_title = PdfSplitHandle.extract_link_title(
                        page, next_link["from"]
                    )
                    if not next_link_title:
                        next_link_title = PdfSplitHandle.extract_first_line(
                            doc.pages[next_link["page"]]
                        )
                    end_page = next_link["page"]

                # 提取章节内容
                chapter_text = ""
                for p_num in range(start_page, min(end_page, len(doc.pages) - 1) + 1):
                    text = PdfSplitHandle.extract_page_text(doc.pages[p_num])
                    text = re.sub(r"(?<!。)\n+", "", text)
                    text = re.sub(r"(?<!.)\n+", "", text)

                    idx = text.find(link_title)
                    if idx > -1:
                        text = text[idx + len(link_title) :]

                    if next_link_title is not None:
                        idx = text.find(next_link_title)
                        if idx > -1:
                            text = text[:idx]
                    chapter_text += text

                # Null characters are not allowed.
                chapter_text = chapter_text.replace("\0", "")
                total_real_chapter_text_len += len(chapter_text.strip())

                # 限制章节内容长度
                if 0 < limit < len(chapter_text):
                    split_text = smart_split_paragraph(chapter_text, limit)
                    for text in split_text:
                        chapters.append({"title": link_title, "content": text})
                else:
                    # 保存章节信息
                    chapters.append({"title": link_title, "content": chapter_text})

        # 目录中没有前言部分，手动处理
        if handle_pre_toc:
            pre_toc = []
            lines = page_content.strip().split("\n")
            try:
                for line in lines:
                    if re.match(r"^前\s*言", line):
                        pre_toc.append({"title": line, "content": ""})
                    else:
                        pre_toc[-1]["content"] += line
                for i in range(len(pre_toc)):
                    pre_toc[i]["content"] = re.sub(
                        r"(?<!。)\n+", "", pre_toc[i]["content"]
                    )
                    pre_toc[i]["content"] = re.sub(
                        r"(?<!.)\n+", "", pre_toc[i]["content"]
                    )
            except BaseException as e:
                maxkb_logger.error(
                    _(
                        "This document has no preface and is treated as ordinary text: {e}"
                    ).format(e=e)
                )
                if pattern_list is not None and len(pattern_list) > 0:
                    split_model = SplitModel(pattern_list, with_filter, limit)
                else:
                    split_model = SplitModel(
                        default_pattern_list, with_filter=with_filter, limit=limit
                    )
                # 插入目录前的部分
                page_content = re.sub(r"(?<!。)\n+", "", page_content)
                page_content = re.sub(r"(?<!.)\n+", "", page_content)
                page_content = page_content.strip()
                pre_toc = split_model.parse(page_content)
            chapters = pre_toc + chapters

        # 扫描版 PDF 即便有内部跳转链接，extract_page_text 也几乎抽不到字。
        # 任何 chapter 都接近空时降级到 handle_pdf_content 走 OCR。
        if chapters and total_real_chapter_text_len < _OCR_PAGE_TEXT_THRESHOLD * len(chapters):
            maxkb_logger.info(
                f"PDF internal-links produced near-empty chapters "
                f"({total_real_chapter_text_len} chars over {len(chapters)} entries); "
                f"falling back to full-page extraction so OCR can run."
            )
            return None
        return chapters

    @staticmethod
    def get_internal_links(doc, page):
        links = []
        annotations = getattr(page, "annotations", None) or []
        for annotation in annotations:
            annotation = get_pdf_object(annotation)
            if not hasattr(annotation, "get"):
                continue
            if annotation.get("/Subtype") != "/Link":
                continue
            dest_page = PdfSplitHandle.get_annotation_destination_page_number(
                doc, annotation
            )
            if dest_page is None or dest_page < 0 or dest_page >= len(doc.pages):
                continue
            rect = annotation.get("/Rect")
            links.append(
                {"page": dest_page, "from": PdfSplitHandle.normalize_rect(rect)}
            )
        return links

    @staticmethod
    def get_annotation_destination_page_number(doc, annotation):
        destination = annotation.get("/Dest")
        if destination is None:
            action = get_pdf_object(annotation.get("/A"))
            if hasattr(action, "get") and action.get("/S") == "/GoTo":
                destination = action.get("/D")
        return PdfSplitHandle.get_destination_page_number(doc, destination)

    @staticmethod
    def get_destination_page_number(doc, destination):
        if destination is None:
            return None

        destination = get_pdf_object(destination)

        if isinstance(destination, bytes):
            destination = destination.decode(errors="ignore")

        if isinstance(destination, str):
            destination = doc.named_destinations.get(destination)
            if destination is None:
                return None

        if isinstance(destination, Destination):
            try:
                page_number = doc.get_destination_page_number(destination)
                return page_number if page_number >= 0 else None
            except BaseException:
                return None

        if isinstance(destination, (list, tuple)) and len(destination) > 0:
            return PdfSplitHandle.get_page_number_by_reference(doc, destination[0])

        if hasattr(destination, "get") and destination.get("/D") is not None:
            return PdfSplitHandle.get_destination_page_number(
                doc, destination.get("/D")
            )

        return None

    @staticmethod
    def get_page_number_by_reference(doc, page_reference):
        try:
            page_number = int(page_reference)
            if 0 <= page_number < len(doc.pages):
                return page_number
        except BaseException:
            pass

        try:
            page = get_pdf_object(page_reference)
            page_number = doc.get_page_number(page)
            return page_number if page_number >= 0 else None
        except BaseException:
            return None

    @staticmethod
    def normalize_rect(rect):
        if rect is None or len(rect) < 4:
            return None
        left, bottom, right, top = [float(value) for value in rect[:4]]
        return min(left, right), min(bottom, top), max(left, right), max(bottom, top)

    @staticmethod
    def extract_link_title(page, rect):
        if rect is None:
            return ""

        left, bottom, right, top = rect
        tolerance = 2
        text_parts = []

        def visitor_text(text, cm, tm, font_dict, font_size):
            if not text:
                return
            x = tm[4] if len(tm) > 4 else 0
            y = tm[5] if len(tm) > 5 else 0
            text_top = y + (float(font_size) if font_size else 0)
            in_horizontal_range = left - tolerance <= x <= right + tolerance
            in_vertical_range = (
                bottom - tolerance <= y <= top + tolerance
                or bottom - tolerance <= text_top <= top + tolerance
            )
            if in_horizontal_range and in_vertical_range:
                text_parts.append(text)

        try:
            page.extract_text(visitor_text=visitor_text)
        except BaseException:
            return ""

        return "".join(text_parts).strip().split("\n")[0].replace(".", "").strip()

    @staticmethod
    def extract_first_line(page):
        text = PdfSplitHandle.extract_page_text(page).strip()
        return text.split("\n")[0].replace(".", "").strip() if text else ""

    @staticmethod
    def handle_chapter_title(title):
        title = re.sub(r"[一二三四五六七八九十\s*]、\s*", "", title)
        title = re.sub(r"第[一二三四五六七八九十]章\s*", "", title)
        return title

    def support(self, file, get_buffer):
        file_name: str = file.name.lower()
        if file_name.endswith(".pdf") or file_name.endswith(".PDF"):
            return True
        return False

    def get_content(self, file, save_image):
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # 将上传的文件保存到临时文件中
            temp_file.write(file.read())
            # 获取临时文件的路径
            temp_file_path = temp_file.name

        try:
            with open(temp_file_path, "rb") as pdf_file:
                pdf_document = PdfReader(pdf_file)
                return self.handle_pdf_content(file, pdf_document)
        except BaseException as e:
            traceback.print_exception(e)
            return f"{e}"
        finally:
            os.remove(temp_file_path)
