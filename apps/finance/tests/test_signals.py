# coding=utf-8
"""
    @project: MaxKB
    @file:   test_signals.py
    @desc:   Unit tests for the finance post_migrate auto-install hook
             (Gate 6 Track A2).

    These tests use SimpleTestCase + mock so they run without touching
    the database. We're only validating that the receiver invokes the
    management command (idempotency itself is covered by the install
    command's UUID-5 derivation logic, see test_internal_workflows.py).
"""
from unittest import mock

from django.test import SimpleTestCase

from finance.signals import install_workflows_on_migrate


class InstallWorkflowsOnMigrateTest(SimpleTestCase):
    def test_calls_management_command_once(self):
        with mock.patch('finance.signals.call_command') as mocked:
            install_workflows_on_migrate(sender=None)
            mocked.assert_called_once_with('install_finance_workflows', verbosity=0)

    def test_swallows_exceptions(self):
        """
        Migration must NEVER fail just because the workflow install
        hit a transient problem. The receiver logs and returns ``None``.
        """
        with mock.patch('finance.signals.call_command', side_effect=RuntimeError('boom')):
            # Should not raise.
            result = install_workflows_on_migrate(sender=None)
            self.assertIsNone(result)

    def test_accepts_post_migrate_keyword_arguments(self):
        """
        Django's post_migrate signal passes ``app_config``, ``verbosity``,
        ``using``, ``plan``, ``apps`` — the receiver must accept all of
        them via **kwargs without raising.
        """
        with mock.patch('finance.signals.call_command') as mocked:
            install_workflows_on_migrate(
                sender=None,
                app_config=None,
                verbosity=1,
                using='default',
                plan=[],
                apps=None,
            )
            mocked.assert_called_once()

    def test_app_config_ready_connects_signal(self):
        """
        FinanceConfig.ready() must connect the receiver to post_migrate.
        Use the apps registry to find the config and assert that calling
        ready() registers a receiver for the ``finance`` sender.
        """
        from django.apps import apps as django_apps
        from django.db.models.signals import post_migrate

        config = django_apps.get_app_config('finance')
        # Receiver count for our sender — should be at least 1 because
        # ready() runs at app load; we don't assert an exact number to
        # avoid coupling to other Django builtins that also subscribe.
        receivers = post_migrate._live_receivers(sender=config)
        # Look for our specific receiver by reference.
        self.assertTrue(
            any(r is install_workflows_on_migrate for r in receivers),
            'install_workflows_on_migrate is not registered on post_migrate',
        )
