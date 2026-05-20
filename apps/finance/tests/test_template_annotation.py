# coding=utf-8
from unittest import TestCase
from unittest.mock import patch

from finance.service.template_annotation import suggest_placeholder_annotations


class SuggestPlaceholderAnnotationsTest(TestCase):
    def test_uses_ai_json_to_generate_chinese_label_and_hint(self):
        placeholders = [
            {
                "key": "borrower_name",
                "label": "borrower_name",
                "type": "text",
                "required": True,
                "ai_hint": "",
                "enum_options": [],
            },
            {
                "key": "loan_amount",
                "label": "loan_amount",
                "type": "number",
                "required": True,
                "ai_hint": "",
                "enum_options": [],
            },
        ]
        ai_json = (
            '{"borrower_name": {"label": "借款人名称", "ai_hint": "请填写借款人全称。"}, '
            '"loan_amount": {"label": "贷款金额", "ai_hint": "请填写本次贷款金额。"}}'
        )

        with patch("finance.service.template_annotation.chat_completion", return_value=ai_json):
            suggested = suggest_placeholder_annotations(
                placeholders,
                workspace_id="ws-1",
                template_name="融资方案",
                template_text="借款人名称：{{ borrower_name }}，贷款金额：{{ loan_amount }}",
            )

        by_key = {p["key"]: p for p in suggested}
        self.assertEqual(by_key["borrower_name"]["label"], "借款人名称")
        self.assertEqual(by_key["borrower_name"]["ai_hint"], "请填写借款人全称。")
        self.assertEqual(by_key["loan_amount"]["label"], "贷款金额")
        self.assertEqual(by_key["loan_amount"]["ai_hint"], "请填写本次贷款金额。")
        self.assertFalse(by_key["borrower_name"]["required"])
        self.assertFalse(by_key["loan_amount"]["required"])

    def test_falls_back_to_local_chinese_label_and_simple_hint(self):
        placeholders = [
            {
                "key": "risk_analysis",
                "label": "risk_analysis",
                "type": "long_text",
                "required": True,
                "ai_hint": "",
                "enum_options": [],
            },
        ]

        with patch("finance.service.template_annotation.chat_completion", return_value=None):
            suggested = suggest_placeholder_annotations(placeholders, workspace_id="ws-1")

        self.assertEqual(suggested[0]["label"], "风险分析")
        self.assertEqual(suggested[0]["ai_hint"], "请填写风险分析，保持与模板上下文一致。")
        self.assertFalse(suggested[0]["required"])
