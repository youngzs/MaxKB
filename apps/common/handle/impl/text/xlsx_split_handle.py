# coding=utf-8
"""
    @project: maxkb
    @Author：虎
    @file： xlsx_parse_qa_handle.py
    @date：2024/5/21 14:59
    @desc:
"""
import io
import traceback
from typing import List

import openpyxl
from openpyxl import load_workbook

from common.handle.base_split_handle import BaseSplitHandle
from common.handle.impl.common_handle import xlsx_embed_cells_images
from common.handle.impl.text.excel_kv_common import (
    get_excel_ingest_mode,
    make_kv_paragraph,
    make_markdown_table_paragraphs,
    normalize_headers,
    normalize_row_values,
)
from common.utils.logger import maxkb_logger

splitter = '\n`-----------------------------------`\n'


def _row_values_with_merge(sheet, row_idx: int, merged_ranges) -> list:
    """读取指定行的单元格值，对合并单元格做左上角值传播。

    openpyxl 中合并单元格只有左上角单元有值，其余为 None；
    这里把这些 None 替换成合并范围左上角的值，便于按行序列化。
    """
    row_cells = list(sheet[row_idx])
    values = []
    for cell in row_cells:
        val = cell.value
        if val is None:
            for rng in merged_ranges:
                if cell.coordinate in rng:
                    val = sheet[rng.min_row][rng.min_col - 1].value
                    break
        values.append(val)
    return values


def handle_sheet(file_name, sheet, image_dict, limit: int):
    """序列化整张 sheet 为 paragraph 列表。

    模式由 MAXKB_EXCEL_INGEST_MODE 控制：
      - markdown（默认）：整张表 → 多个 Markdown 表格分块，每块都带表头（全局视图）
      - keyvalue（旧行为）：每一非空行 → 一个 KV paragraph

    file_name 实际上是 sheet 内容描述用的"上下文名称"，
    在外层调用时已根据 sheet 数量决定是用文件名还是 sheet 名作为 context。
    """
    paragraphs = []
    result = {'name': file_name, 'content': paragraphs}
    try:
        if sheet.max_row is None or sheet.max_row < 1 or sheet.max_column is None or sheet.max_column < 1:
            return result
        merged_ranges = list(sheet.merged_cells.ranges)
        # 第一行作为表头
        header_values = _row_values_with_merge(sheet, 1, merged_ranges)
        headers = normalize_headers(header_values)
        if not headers:
            return result

        mode = get_excel_ingest_mode()
        if mode == 'markdown':
            # Markdown 表格模式：以 sheet 名作为分块标题
            rows = []
            for row_idx in range(2, sheet.max_row + 1):
                row_values = _row_values_with_merge(sheet, row_idx, merged_ranges)
                rows.append(normalize_row_values(row_values, image_dict))
            paragraphs.extend(
                make_markdown_table_paragraphs(
                    title=sheet.title,
                    headers=headers,
                    rows=rows,
                    limit=limit,
                )
            )
            return result

        # keyvalue 模式（旧行为，fallback）：从第 2 行开始，每行一个 paragraph
        for row_idx in range(2, sheet.max_row + 1):
            row_values = _row_values_with_merge(sheet, row_idx, merged_ranges)
            paragraph = make_kv_paragraph(
                file_name=file_name,
                sheet_name=sheet.title,
                row_idx=row_idx,
                headers=headers,
                row_values=row_values,
                image_dict=image_dict,
                limit=limit,
            )
            if paragraph is not None:
                paragraphs.append(paragraph)
    except Exception as e:
        maxkb_logger.error(f"Error parsing XLSX sheet {sheet.title}: {e}, {traceback.format_exc()}")
    return result


class XlsxSplitHandle(BaseSplitHandle):
    def fill_merged_cells(self, sheet, image_dict):
        data = []

        # 获取第一行作为标题行
        headers = []
        for idx, cell in enumerate(sheet[1]):
            if cell.value is None:
                headers.append(' ' * (idx + 1))
            else:
                headers.append(cell.value)

        # 从第二行开始遍历每一行
        for row in sheet.iter_rows(min_row=2, values_only=False):
            row_data = {}
            for col_idx, cell in enumerate(row):
                cell_value = cell.value

                # 如果单元格为空，并且该单元格在合并单元格内，获取合并单元格的值
                if cell_value is None:
                    for merged_range in sheet.merged_cells.ranges:
                        if cell.coordinate in merged_range:
                            cell_value = sheet[merged_range.min_row][merged_range.min_col - 1].value
                            break

                image = image_dict.get(cell_value, None)
                if image is not None:
                    cell_value = f'![](./oss/file/{image.id})'

                # 使用标题作为键，单元格的值作为值存入字典
                row_data[headers[col_idx]] = cell_value
            data.append(row_data)

        return data

    def handle(self, file, pattern_list: List, with_filter: bool, limit: int, get_buffer, save_image):
        buffer = get_buffer(file)
        try:
            if type(limit) is str:
                limit = int(limit)
            # data_only=True：读取 Excel/WPS 缓存的公式计算结果而非公式字符串本身，
            # 避免 ="A1"&B1 这类公式被原样存入知识库导致检索失败。
            # 注：若文件由未写入缓存值的工具生成（罕见），公式格会变成 None；
            # 这是可接受降级 —— 无意义字符串污染索引比留空更差。
            workbook = openpyxl.load_workbook(io.BytesIO(buffer), data_only=True)
            try:
                image_dict: dict = xlsx_embed_cells_images(io.BytesIO(buffer))
                save_image([item for item in image_dict.values()])
            except Exception:
                image_dict = {}
            # 只保留可见 sheet —— Excel/WPS 财报常用隐藏 sheet 存中间计算或老版本草稿
            # （名字常见为 "1"/"2"/"详细附注"），这些不应进入知识库。
            worksheets = [s for s in workbook.worksheets if s.sheet_state == 'visible']
            worksheets_size = len(worksheets)
            # 工作簿文件名(去扩展名)——多 sheet 拆分时拼到文档名上，
            # 因为 sheet 名(如"资产负债表"/"利润表")在多份同结构工作簿间重复，
            # 单看 sheet 名无法区分公司/年度(信息恰在文件名里)。
            base_name = file.name.rsplit('.', 1)[0] if '.' in file.name else file.name
            results = []
            for sheet in worksheets:
                # paragraph 内的「文件：xxx」始终用真实文件名，与文档拆分名解耦
                sheet_result = handle_sheet(file.name, sheet, image_dict, limit)
                if worksheets_size == 1 and sheet.title == 'Sheet1':
                    # 单 sheet 且默认名：用文件名作为文档名（保留原行为）
                    sheet_result['name'] = file.name
                elif worksheets_size == 1:
                    # 单 sheet 具名：sheet 名即文档主题（保留原行为）
                    sheet_result['name'] = sheet.title
                else:
                    # 多 sheet：拼上文件名以区分来源工作簿（公司/年度），
                    # 形如「千岛…-2025财报(5) - 资产负债表」
                    sheet_result['name'] = f"{base_name} - {sheet.title}"
                results.append(sheet_result)
            return [r for r in results if r is not None]
        except Exception as e:
            maxkb_logger.error(f"Error processing XLSX file {file.name}: {e}, {traceback.format_exc()}")
            return [{'name': file.name, 'content': []}]

    def get_content(self, file, save_image):
        try:
            # 加载 Excel 文件；data_only=True 读取公式缓存值，避免公式字符串污染输出
            workbook = load_workbook(file, data_only=True)
            try:
                image_dict: dict = xlsx_embed_cells_images(file)
                if len(image_dict) > 0:
                    save_image(image_dict.values())
            except Exception as e:
                maxkb_logger.error(f'Exception: {e}')
                image_dict = {}
            md_tables = ''
            # 遍历所有工作表（跳过隐藏 sheet，详见 handle() 同名注释）
            for sheetname in workbook.sheetnames:
                sheet = workbook[sheetname]
                if sheet.sheet_state != 'visible':
                    continue
                rows = self.fill_merged_cells(sheet, image_dict)
                if len(rows) == 0:
                    continue

                # 添加 sheet 名称作为标题
                md_tables += f'## {sheetname}\n\n'

                # 提取表头和内容
                headers = [f"{key}" for key, value in rows[0].items()]

                # 构建 Markdown 表格
                md_table = '| ' + ' | '.join(headers) + ' |\n'
                md_table += '| ' + ' | '.join(['---'] * len(headers)) + ' |\n'
                for row in rows:
                    r = [self._escape_cell_content(value) for key, value in row.items()]
                    md_table += '| ' + ' | '.join(r) + ' |\n'

                md_tables += md_table + '\n\n'

            return md_tables
        except Exception as e:
            maxkb_logger.error(f'excel split handle error: {e}')
            return f'error: {e}'

    def _escape_cell_content(self, cell_value):
        """转义单元格内容,避免破坏 Markdown 表格结构"""
        if cell_value is None:
            return ''

        cell_str = str(cell_value)

        # 替换换行符为 <br>
        cell_str = cell_str.replace('\n', '<br>')

        # 转义管道符 | 为 HTML 实体
        cell_str = cell_str.replace('|', '&#124;')

        # 如果内容包含反引号,需要转义
        if '`' in cell_str:
            cell_str = cell_str.replace('`', '&#96;')

        return cell_str

    def support(self, file, get_buffer):
        file_name: str = file.name.lower()
        if file_name.endswith(".xlsx"):
            return True
        return False
