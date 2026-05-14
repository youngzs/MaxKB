# coding=utf-8
"""
    @project: MaxKB
    @file:   test_audit_log_view.py
    @desc:   Unit tests for the FinanceAuditLogListView helpers (Gate 5 Track C).

    These are deliberately lightweight: the helpers (_parse_int, _parse_iso,
    _build_queryset's enum guard) are pure-Python and validated without
    touching the database, so they can run on Windows dev hosts that can't
    spin up the full Django ORM stack.
"""
from django.test import SimpleTestCase

from finance.views.audit_log import (
    _VALID_ACTIONS,
    _VALID_TARGET_TYPES,
    _parse_int,
    _parse_iso,
)


class FinanceAuditLogHelpersTest(SimpleTestCase):
    def test_parse_int_default_on_invalid(self):
        self.assertEqual(_parse_int(None, 7), 7)
        self.assertEqual(_parse_int('abc', 7), 7)
        self.assertEqual(_parse_int('-3', 7), 7)
        self.assertEqual(_parse_int('0', 7), 7)
        self.assertEqual(_parse_int('5', 7), 5)
        self.assertEqual(_parse_int(' 12 ', 7), 12)

    def test_parse_iso_handles_blank_and_invalid(self):
        self.assertIsNone(_parse_iso(None))
        self.assertIsNone(_parse_iso(''))
        self.assertIsNone(_parse_iso('not a date'))
        ts = _parse_iso('2026-05-13T08:30:00')
        self.assertIsNotNone(ts)
        self.assertEqual(ts.year, 2026)
        self.assertEqual(ts.month, 5)

    def test_enum_choice_sets_include_smtp_config(self):
        self.assertIn('PROJECT', _VALID_TARGET_TYPES)
        self.assertIn('SMTP_CONFIG', _VALID_TARGET_TYPES)
        self.assertIn('OTHER', _VALID_TARGET_TYPES)
        self.assertIn('CREATE', _VALID_ACTIONS)
        self.assertIn('SEND', _VALID_ACTIONS)
