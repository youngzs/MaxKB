# coding=utf-8
"""
    @project: maxkb
    @file: markdown_table.py
    @desc: 从表格数据构建 Markdown 表格并分块，保证每个分块都是自洽、可读的表格：

    每个分块都重复表头行 + 分隔行，再加上可选的标题行，
    使向量检索命中任意分块时仍带有完整的列上下文（"全局视图"），
    而不是孤立的单元格。被 xlsx / csv / pdf(OCR) 文本拆分路径复用。
"""
import os
from typing import List

# 每个分块的数据行上限。表格很宽时字符上限会先触发；表格很窄时行数上限托底。
# 可用 MAXKB_TABLE_CHUNK_ROWS 覆盖。
_DEFAULT_MAX_ROWS_PER_CHUNK = int(os.environ.get('MAXKB_TABLE_CHUNK_ROWS', '30'))
# 每个分块的字符上限（含表头 + 分隔行 + 标题行）。可用 MAXKB_TABLE_CHUNK_CHARS 覆盖。
_DEFAULT_MAX_CHARS_PER_CHUNK = int(os.environ.get('MAXKB_TABLE_CHUNK_CHARS', '2000'))


def _escape_cell(value) -> str:
    """转义单元格内容，避免破坏 Markdown 表格结构。

    - None → ''
    - 管道符 | → 转义为 \\| （Markdown 表格列分隔符）
    - 换行/回车 → 替换为 <br>，保证整张表格仍是合法的单行单元格
    """
    if value is None:
        return ''
    text = str(value)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = text.replace('|', '\\|')
    text = text.replace('\n', '<br>')
    return text.strip()


def _normalize_headers(headers: List[str]) -> List[str]:
    """规范化表头：None / 空 → col1/col2/...，并转义。"""
    result = []
    for idx, h in enumerate(headers):
        if h is None:
            result.append(f'col{idx + 1}')
            continue
        text = _escape_cell(h)
        result.append(text if text else f'col{idx + 1}')
    return result


def _build_row_line(cells: List, width: int) -> str:
    """把一行数据渲染成 Markdown 表格行，并对齐到 width 列（不足补空、超出截断）。"""
    escaped = [_escape_cell(c) for c in cells]
    if len(escaped) < width:
        escaped = escaped + [''] * (width - len(escaped))
    else:
        escaped = escaped[:width]
    return '| ' + ' | '.join(escaped) + ' |'


def rows_to_markdown_table(headers: List[str], rows: List[list], *, title: str = '') -> str:
    """把 headers + rows 渲染成一张完整的 GitHub 风格 Markdown 表格。

    可选 title 会作为一行 '## {title}' 前缀。单元格内的管道符与换行会被转义。
    """
    norm_headers = _normalize_headers(headers)
    width = len(norm_headers)
    lines = []
    if title:
        lines.append(f'## {title}')
        lines.append('')
    lines.append('| ' + ' | '.join(norm_headers) + ' |')
    lines.append('| ' + ' | '.join(['---'] * width) + ' |')
    for row in rows:
        lines.append(_build_row_line(row, width))
    return '\n'.join(lines)


def chunk_markdown_table(
        headers: List[str],
        rows: List[list],
        *,
        title: str = '',
        max_rows_per_chunk: int = _DEFAULT_MAX_ROWS_PER_CHUNK,
        max_chars_per_chunk: int = _DEFAULT_MAX_CHARS_PER_CHUNK,
) -> List[str]:
    """把一张大表拆成多个 Markdown 表格分块。

    每个分块 = 可选标题行 + 表头行 + 分隔行 + 一窗口数据行。
    窗口大小取 min(max_rows_per_chunk, 在 max_chars_per_chunk 之内能放下的行数)。
    每个分块都是独立合法的 Markdown，且都带有表头 —— 这样向量检索命中任意分块，
    用户都能看到这些数字属于哪些列。

    返回分块字符串列表（rows 为空时返回 []）。
    """
    if not rows:
        return []

    norm_headers = _normalize_headers(headers)
    width = len(norm_headers)
    header_line = '| ' + ' | '.join(norm_headers) + ' |'
    separator_line = '| ' + ' | '.join(['---'] * width) + ' |'

    # 每个分块固定的前缀（标题 + 表头 + 分隔行）
    prefix_lines = []
    if title:
        prefix_lines.append(f'## {title}')
        prefix_lines.append('')
    prefix_lines.append(header_line)
    prefix_lines.append(separator_line)
    prefix_text = '\n'.join(prefix_lines)
    prefix_len = len(prefix_text)

    # 行数上限兜底；至少保证每个分块能放下 1 行数据
    row_cap = max(1, max_rows_per_chunk)

    chunks: List[str] = []
    current_lines: List[str] = []
    current_len = prefix_len

    def flush():
        if current_lines:
            chunks.append(prefix_text + '\n' + '\n'.join(current_lines))

    for row in rows:
        row_line = _build_row_line(row, width)
        # +1 为换行符
        projected_len = current_len + len(row_line) + 1
        # 当前分块已有数据行，且再加这一行会超字符上限或超行数上限 → 先收口
        if current_lines and (projected_len > max_chars_per_chunk or len(current_lines) >= row_cap):
            flush()
            current_lines = []
            current_len = prefix_len
            projected_len = current_len + len(row_line) + 1
        current_lines.append(row_line)
        current_len = projected_len

    flush()
    return chunks
