# coding=utf-8
"""
    @project: MaxKB
    @file： test_ai_fill.py
    @desc: Unit tests for _do_ai_fill in finance.views.document_generation.

    These exercise the per-placeholder LLM loop, the fallback paths (no LLM,
    empty response, oversized response, exception mid-loop), and the
    unknown-key drop behavior. We use lightweight stand-in objects for the
    template and project rather than touching the DB.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from finance.views.document_generation import _do_ai_fill


_PATCH_TARGET = 'finance.views.document_generation.chat_completion'


def _make_template(placeholders):
    return SimpleNamespace(placeholders=placeholders)


def _make_project(**kwargs):
    defaults = {
        'name': '示例项目',
        'code': 'P001',
        'target_amount': Decimal('1000000.00'),
        'currency': 'CNY',
        'description': '一段描述',
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class DoAIFillTest(TestCase):
    def setUp(self):
        self.template = _make_template([
            {'key': 'k1', 'label': '甲方名称', 'type': 'text', 'ai_hint': '公司全称'},
            {'key': 'k2', 'label': '金额', 'type': 'number', 'ai_hint': ''},
        ])
        self.project = _make_project()

    def test_happy_path_fills_all_requested_keys(self):
        def fake(workspace_id, system, user):
            if '甲方名称' in system:
                return '示例科技有限公司'
            if '金额' in system:
                return '100,000 元'
            return None

        with patch(_PATCH_TARGET, side_effect=fake):
            result = _do_ai_fill(self.template, self.project, ['k1', 'k2'], workspace_id='ws-1')

        self.assertEqual(result, {'k1': '示例科技有限公司', 'k2': '100,000 元'})

    def test_llm_none_falls_back_to_stub_per_key(self):
        with patch(_PATCH_TARGET, return_value=None):
            result = _do_ai_fill(self.template, self.project, ['k1', 'k2'], workspace_id='ws-1')
        self.assertEqual(result['k1'], '[AI 待生成: 甲方名称]')
        self.assertEqual(result['k2'], '[AI 待生成: 金额]')

    def test_llm_empty_string_falls_back_to_stub(self):
        with patch(_PATCH_TARGET, return_value='   '):
            result = _do_ai_fill(self.template, self.project, ['k1'], workspace_id='ws-1')
        self.assertEqual(result['k1'], '[AI 待生成: 甲方名称]')

    def test_oversized_response_falls_back_to_stub(self):
        with patch(_PATCH_TARGET, return_value='x' * 5000):
            result = _do_ai_fill(self.template, self.project, ['k1'], workspace_id='ws-1')
        self.assertEqual(result['k1'], '[AI 待生成: 甲方名称]')

    def test_unknown_key_silently_dropped(self):
        with patch(_PATCH_TARGET, return_value='ok'):
            result = _do_ai_fill(self.template, self.project,
                                 ['k1', 'unknown_key'], workspace_id='ws-1')
        self.assertIn('k1', result)
        self.assertNotIn('unknown_key', result)

    def test_chat_raises_returns_stub_for_that_key(self):
        # One key raises, the other returns a value — verify the loop
        # absorbs the failure and continues.
        def fake(workspace_id, system, user):
            if '金额' in system:
                raise RuntimeError('model offline')
            return '甲方公司'

        with patch(_PATCH_TARGET, side_effect=fake):
            result = _do_ai_fill(self.template, self.project, ['k1', 'k2'], workspace_id='ws-1')
        self.assertEqual(result['k1'], '甲方公司')
        self.assertEqual(result['k2'], '[AI 待生成: 金额]')

    def test_empty_request_returns_empty_dict(self):
        with patch(_PATCH_TARGET) as m:
            result = _do_ai_fill(self.template, self.project, [], workspace_id='ws-1')
        self.assertEqual(result, {})
        m.assert_not_called()

    def test_default_workspace_id(self):
        # Signature accepts default 'default' workspace_id; verify call site
        # without an explicit workspace_id still works.
        with patch(_PATCH_TARGET, return_value='ok'):
            result = _do_ai_fill(self.template, self.project, ['k1'])
        self.assertEqual(result['k1'], 'ok')

    def test_stub_uses_key_when_label_missing(self):
        template = _make_template([{'key': 'k_only'}])
        with patch(_PATCH_TARGET, return_value=None):
            result = _do_ai_fill(template, self.project, ['k_only'], workspace_id='ws-1')
        self.assertEqual(result['k_only'], '[AI 待生成: k_only]')
