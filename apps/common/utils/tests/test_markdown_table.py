# coding=utf-8
"""
    @project: maxkb
    @file: test_markdown_table.py
    @desc: markdown_table 工具的纯 Python 单元测试（不依赖 Django）。
"""
import unittest

from common.utils.markdown_table import (
    chunk_markdown_table,
    rows_to_markdown_table,
)


class RowsToMarkdownTableTest(unittest.TestCase):
    def test_basic_table(self):
        md = rows_to_markdown_table(['名称', '金额'], [['现金', 100], ['应收', 200]])
        self.assertIn('| 名称 | 金额 |', md)
        self.assertIn('| --- | --- |', md)
        self.assertIn('| 现金 | 100 |', md)
        self.assertIn('| 应收 | 200 |', md)

    def test_title_prefix(self):
        md = rows_to_markdown_table(['a'], [['x']], title='现金流量表')
        self.assertTrue(md.startswith('## 现金流量表'))

    def test_pipe_in_cell_escaped(self):
        md = rows_to_markdown_table(['col'], [['a|b']])
        self.assertIn('a\\|b', md)
        # 转义后该数据行只有一个真正的列分隔结构
        self.assertNotIn('| a|b |', md)

    def test_newline_in_cell_replaced(self):
        md = rows_to_markdown_table(['col'], [['line1\nline2']])
        self.assertIn('line1<br>line2', md)
        # 数据行不应被换行劈开
        self.assertEqual(len([ln for ln in md.splitlines() if ln.startswith('| line1')]), 1)

    def test_empty_and_none_headers(self):
        md = rows_to_markdown_table([None, ''], [['x', 'y']])
        self.assertIn('| col1 | col2 |', md)

    def test_short_row_padded(self):
        md = rows_to_markdown_table(['a', 'b', 'c'], [['x']])
        self.assertIn('| x |  |  |', md)


class ChunkMarkdownTableTest(unittest.TestCase):
    def test_empty_rows_returns_empty_list(self):
        self.assertEqual(chunk_markdown_table(['a', 'b'], []), [])

    def test_small_table_single_chunk_with_header(self):
        chunks = chunk_markdown_table(['名称', '金额'], [['现金', 100], ['应收', 200]])
        self.assertEqual(len(chunks), 1)
        self.assertIn('| 名称 | 金额 |', chunks[0])
        self.assertIn('| --- | --- |', chunks[0])
        self.assertIn('| 现金 | 100 |', chunks[0])

    def test_big_table_multiple_chunks_each_has_header_and_title(self):
        rows = [[f'行{i}', i] for i in range(100)]
        chunks = chunk_markdown_table(
            ['名称', '金额'], rows, title='大表', max_rows_per_chunk=10
        )
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn('## 大表', chunk)
            self.assertIn('| 名称 | 金额 |', chunk)
            self.assertIn('| --- | --- |', chunk)
        # 每个分块的数据行不超过 max_rows_per_chunk
        for chunk in chunks:
            data_lines = [
                ln for ln in chunk.splitlines()
                if ln.startswith('| 行')
            ]
            self.assertLessEqual(len(data_lines), 10)
        # 所有数据行加起来应覆盖全部 100 行
        total_data_lines = sum(
            len([ln for ln in chunk.splitlines() if ln.startswith('| 行')])
            for chunk in chunks
        )
        self.assertEqual(total_data_lines, 100)

    def test_char_limit_forces_split(self):
        # 单行很长，max_chars 很小 → 每个分块只能放下一行数据
        rows = [['x' * 200] for _ in range(5)]
        chunks = chunk_markdown_table(
            ['col'], rows, max_rows_per_chunk=100, max_chars_per_chunk=250
        )
        self.assertEqual(len(chunks), 5)
        for chunk in chunks:
            self.assertIn('| col |', chunk)

    def test_pipe_in_cell_escaped_in_chunk(self):
        chunks = chunk_markdown_table(['col'], [['a|b|c']])
        self.assertEqual(len(chunks), 1)
        self.assertIn('a\\|b\\|c', chunks[0])

    def test_each_chunk_is_valid_markdown_table(self):
        rows = [[f'r{i}', f'v{i}'] for i in range(50)]
        chunks = chunk_markdown_table(['k', 'v'], rows, max_rows_per_chunk=7)
        for chunk in chunks:
            lines = [ln for ln in chunk.splitlines() if ln.strip()]
            # 表头行 + 分隔行 + 至少一行数据
            self.assertGreaterEqual(len(lines), 3)
            self.assertEqual(lines[0], '| k | v |')
            self.assertEqual(lines[1], '| --- | --- |')


if __name__ == '__main__':
    unittest.main()
