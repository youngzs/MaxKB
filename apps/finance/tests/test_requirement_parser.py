# coding=utf-8
"""
    @project: MaxKB
    @file： test_requirement_parser.py
    @desc: Unit tests for finance.service.requirement_parser.

    Pure-Python tests — no Django db needed. The LLM call is mocked via
    unittest.mock.patch on the module-local `chat_completion` symbol that
    requirement_parser imported, so we exercise the LLM-first path and the
    heuristic fallback path independently.
"""
from unittest import TestCase
from unittest.mock import patch

from finance.service.requirement_parser import (
    _heuristic_parse,
    _strip_code_fence,
    parse_requirement_list,
)


_PATCH_TARGET = 'finance.service.requirement_parser.chat_completion'


class StripCodeFenceTest(TestCase):
    def test_no_fence_returned_as_is(self):
        self.assertEqual(_strip_code_fence('[]'), '[]')

    def test_plain_fence(self):
        self.assertEqual(_strip_code_fence('```\n[1,2]\n```'), '[1,2]')

    def test_json_tagged_fence(self):
        self.assertEqual(_strip_code_fence('```json\n[1,2]\n```'), '[1,2]')

    def test_uppercase_fence_tag(self):
        self.assertEqual(_strip_code_fence('```JSON\n[]\n```'), '[]')

    def test_empty(self):
        self.assertEqual(_strip_code_fence(''), '')


class HeuristicParseTest(TestCase):
    def test_empty_text(self):
        self.assertEqual(_heuristic_parse(''), [])

    def test_numbered_list(self):
        text = '1. 财务报表\n2、营业执照\n3) 公司章程'
        items = _heuristic_parse(text)
        self.assertEqual(len(items), 3)
        labels = [i['label'] for i in items]
        self.assertEqual(labels, ['财务报表', '营业执照', '公司章程'])
        for item in items:
            self.assertTrue(item['required'])
            self.assertIsInstance(item['key'], str)

    def test_colon_split_extracts_description(self):
        text = '财务报表：近三年合并报表'
        items = _heuristic_parse(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['label'], '财务报表')
        self.assertEqual(items[0]['description'], '近三年合并报表')


class ParseRequirementListLLMPathTest(TestCase):
    def test_llm_returns_valid_json_array(self):
        llm_text = (
            '[{"key":"financial_report","label":"财务报表（近三年）",'
            '"description":"合并报表+审计报告","required":true},'
            '{"key":"license","label":"营业执照","description":"","required":true}]'
        )
        with patch(_PATCH_TARGET, return_value=llm_text) as m:
            result = parse_requirement_list('whatever input', 'ws-1')
        m.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['key'], 'financial_report')
        self.assertEqual(result[0]['label'], '财务报表（近三年）')
        self.assertEqual(result[0]['description'], '合并报表+审计报告')
        self.assertTrue(result[0]['required'])
        self.assertEqual(result[1]['key'], 'license')

    def test_llm_response_wrapped_in_code_fence(self):
        llm_text = '```json\n[{"key":"k","label":"L","description":"","required":true}]\n```'
        with patch(_PATCH_TARGET, return_value=llm_text):
            result = parse_requirement_list('x', 'ws-1')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['label'], 'L')

    def test_llm_returns_invalid_json_falls_back_to_heuristic(self):
        text = '1. 财务报表\n2. 营业执照'
        with patch(_PATCH_TARGET, return_value='this is not json at all'):
            result = parse_requirement_list(text, 'ws-1')
        # Heuristic took over → two items derived from the line-split path.
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['label'], '财务报表')
        self.assertEqual(result[1]['label'], '营业执照')

    def test_llm_returns_empty_list_falls_back_to_heuristic(self):
        text = '1. A\n2. B'
        with patch(_PATCH_TARGET, return_value='[]'):
            result = parse_requirement_list(text, 'ws-1')
        self.assertEqual(len(result), 2)

    def test_llm_returns_non_array_falls_back(self):
        text = '1. 报表'
        with patch(_PATCH_TARGET, return_value='{"not":"an array"}'):
            result = parse_requirement_list(text, 'ws-1')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['label'], '报表')

    def test_llm_returns_none_falls_back_to_heuristic(self):
        text = '1. 报表\n2. 章程'
        with patch(_PATCH_TARGET, return_value=None):
            result = parse_requirement_list(text, 'ws-1')
        self.assertEqual(len(result), 2)

    def test_malformed_items_are_dropped(self):
        llm_text = (
            '[{"key":"a","label":"A","description":"","required":true},'
            '{"label":""},'              # empty label → drop
            '"not a dict",'              # non-dict → drop
            '{"key":"c","label":"C"}]'    # required defaults to True
        )
        with patch(_PATCH_TARGET, return_value=llm_text):
            result = parse_requirement_list('x', 'ws-1')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['label'], 'A')
        self.assertEqual(result[1]['label'], 'C')
        self.assertTrue(result[1]['required'])

    def test_empty_text_short_circuits(self):
        # Should never call the LLM for empty input.
        with patch(_PATCH_TARGET) as m:
            result = parse_requirement_list('', 'ws-1')
        self.assertEqual(result, [])
        m.assert_not_called()
