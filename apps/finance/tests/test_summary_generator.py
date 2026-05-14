# coding=utf-8
"""
    @project: MaxKB
    @file： test_summary_generator.py
    @desc: Unit tests for finance.service.summary_generator.

    The DB-touching `_load_document_content` is patched so these tests run
    without any Django fixtures; we verify the LLM happy path and every
    fallback branch.
"""
from unittest import TestCase
from unittest.mock import patch

from finance.service.summary_generator import (
    _STUB_TEMPLATE,
    generate_summary_for_document,
)


_LOAD_TARGET = 'finance.service.summary_generator._load_document_content'
_LLM_TARGET = 'finance.service.summary_generator.chat_completion'


class GenerateSummaryTest(TestCase):
    def test_llm_happy_path(self):
        with patch(_LOAD_TARGET, return_value=('合同.pdf', '这是合同的全部内容。' * 10)):
            with patch(_LLM_TARGET, return_value='本合同为甲乙双方签订，金额 100 万元，期限 1 年。'):
                summary = generate_summary_for_document('doc-1', 'ws-1')
        self.assertEqual(summary, '本合同为甲乙双方签订，金额 100 万元，期限 1 年。')

    def test_summary_is_stripped(self):
        with patch(_LOAD_TARGET, return_value=('a.pdf', 'content')):
            with patch(_LLM_TARGET, return_value='  hello  \n'):
                summary = generate_summary_for_document('doc-1', 'ws-1')
        self.assertEqual(summary, 'hello')

    def test_empty_content_returns_stub(self):
        with patch(_LOAD_TARGET, return_value=('合同.pdf', '')):
            with patch(_LLM_TARGET) as llm_mock:
                summary = generate_summary_for_document('doc-1', 'ws-1')
        # When content is empty we never call the LLM.
        llm_mock.assert_not_called()
        self.assertEqual(summary, _STUB_TEMPLATE.format(name='合同.pdf'))

    def test_llm_returns_none_falls_back_to_stub(self):
        with patch(_LOAD_TARGET, return_value=('合同.pdf', 'real content')):
            with patch(_LLM_TARGET, return_value=None):
                summary = generate_summary_for_document('doc-1', 'ws-1')
        self.assertEqual(summary, _STUB_TEMPLATE.format(name='合同.pdf'))

    def test_llm_returns_blank_falls_back_to_stub(self):
        with patch(_LOAD_TARGET, return_value=('合同.pdf', 'real content')):
            with patch(_LLM_TARGET, return_value='   \n  '):
                summary = generate_summary_for_document('doc-1', 'ws-1')
        self.assertEqual(summary, _STUB_TEMPLATE.format(name='合同.pdf'))

    def test_llm_raises_falls_back_to_stub(self):
        # chat_completion is meant to swallow its own errors, but we still
        # defend in depth — verify the summary call doesn't propagate.
        with patch(_LOAD_TARGET, return_value=('合同.pdf', 'real content')):
            with patch(_LLM_TARGET, side_effect=RuntimeError('boom')):
                summary = generate_summary_for_document('doc-1', 'ws-1')
        self.assertEqual(summary, _STUB_TEMPLATE.format(name='合同.pdf'))
