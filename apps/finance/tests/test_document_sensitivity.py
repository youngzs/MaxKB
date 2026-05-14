# coding=utf-8
"""
    @project: MaxKB
    @file:   test_document_sensitivity.py
    @desc:   Unit tests for DocumentSensitivityView helpers (Gate 6 Track A3).

    These run as SimpleTestCase — they exercise the validation logic
    (allowed enum values) without standing up the full ORM, mirroring
    the lightweight style of test_audit_log_view.py.
"""
from django.test import SimpleTestCase

from common.constants.sensitivity_constants import SensitivityLevel
from finance.views.document_sensitivity import _VALID_LEVELS


class SensitivityLevelEnumTest(SimpleTestCase):
    def test_valid_levels_match_constants(self):
        # Every choice declared on the SensitivityLevel TextChoices
        # must be accepted by the PATCH endpoint — otherwise the
        # client and server enums would drift silently.
        for value, _label in SensitivityLevel.choices:
            self.assertIn(
                value,
                _VALID_LEVELS,
                f'SensitivityLevel value {value!r} not in view _VALID_LEVELS',
            )

    def test_valid_levels_is_the_full_set(self):
        # Defensive: catch any future addition that forgets to update
        # both sides.
        declared = {value for value, _label in SensitivityLevel.choices}
        self.assertEqual(_VALID_LEVELS, declared)

    def test_known_levels_present(self):
        for expected in ('public', 'internal', 'confidential', 'secret'):
            self.assertIn(expected, _VALID_LEVELS)


class DocumentSensitivityRouteRegistrationTest(SimpleTestCase):
    def test_url_resolves_with_workspace_and_document_id(self):
        # Spot-check the route is wired into the finance URL conf.
        from django.urls import reverse

        url = reverse(
            'finance:document_sensitivity',
            kwargs={
                'workspace_id': 'default',
                'document_id': '00000000-0000-0000-0000-000000000000',
            },
        )
        self.assertEqual(
            url,
            '/api/finance/workspace/default/document-sensitivity/'
            '00000000-0000-0000-0000-000000000000',
        )
