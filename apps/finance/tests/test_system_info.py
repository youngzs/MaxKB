# coding=utf-8
"""
    @project: MaxKB
    @file:    test_system_info.py
    @desc:    Unit tests for the admin system-info endpoint
              (Gate 7 Track A4).

    These tests avoid the database: they cover the pure helpers
    (``_dep_versions``, the histogram constants, the URL wire-up,
    and the import surface). Full integration is left to the
    once-per-deploy smoke check operators run after a release.
"""
from django.test import SimpleTestCase

from finance.views.system_info import (
    FINANCE_MODULE_VERSION,
    _DEPS_TO_REPORT,
    _MATERIALS_STATUSES,
    _SENSITIVITY_ORDER,
    _dep_versions,
)


class DepVersionsTest(SimpleTestCase):
    def test_dep_versions_returns_a_dict_with_all_keys(self):
        deps = _dep_versions()
        self.assertIsInstance(deps, dict)
        for name in _DEPS_TO_REPORT:
            self.assertIn(name, deps, f'{name!r} missing from deps report')

    def test_known_deps_have_non_empty_versions(self):
        """
        ``django`` and ``djangorestframework`` are guaranteed to be
        installed in any environment that runs the tests at all, so
        they MUST report a non-empty version string. Other deps may
        be optional in some platform-conditional layouts.
        """
        deps = _dep_versions()
        self.assertTrue(deps.get('django'), 'django version must be non-empty')
        self.assertTrue(
            deps.get('djangorestframework'),
            'djangorestframework version must be non-empty',
        )


class ConstantsTest(SimpleTestCase):
    def test_module_version_is_semver_shape(self):
        # Don't pin exact value — Track A5/A6 may bump it. Just sanity.
        parts = FINANCE_MODULE_VERSION.split('.')
        self.assertEqual(len(parts), 3)
        for p in parts:
            self.assertTrue(p.isdigit(), f'non-numeric part in version: {p!r}')

    def test_materials_statuses_match_state_machine(self):
        # Mirrors MaterialsTaskStatus.choices — keep these in lockstep.
        from finance.models import MaterialsTaskStatus

        model_values = {value for value, _label in MaterialsTaskStatus.choices}
        # _MATERIALS_STATUSES must be a SUBSET of the model values; if
        # the model adds a new status the constant should be updated.
        self.assertTrue(set(_MATERIALS_STATUSES).issubset(model_values))

    def test_sensitivity_order_matches_levels(self):
        from common.constants.sensitivity_constants import SensitivityLevel

        model_values = {value for value, _label in SensitivityLevel.choices}
        self.assertTrue(set(_SENSITIVITY_ORDER).issubset(model_values))


class SystemInfoUrlTest(SimpleTestCase):
    def test_system_info_url_resolves(self):
        from django.urls import reverse

        url = reverse(
            'finance:system_info',
            kwargs={'workspace_id': 'default'},
        )
        self.assertEqual(url, '/api/finance/workspace/default/system-info')


class SystemInfoImportTest(SimpleTestCase):
    def test_view_is_exported_from_views_module(self):
        from finance import views as finance_views

        self.assertTrue(hasattr(finance_views, 'FinanceSystemInfoView'))
        # Listed in __all__
        self.assertIn('FinanceSystemInfoView', finance_views.__all__)
