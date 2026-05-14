# coding=utf-8
"""
    @project: MaxKB
    @file:    test_install_workflows.py
    @desc:    Coverage for the ``install_finance_workflows`` management
              command and its post_migrate signal wrapper (Gate 7 A3).

    The full install path needs a real database with the ``application``
    table available, which we can't assume in unit tests here. Instead
    we cover:

      - ``--dry-run`` short-circuits before any ORM write
      - command discovers exactly the workflows shipped in
        ``data/internal_workflows/``
      - signal handler bails gracefully when the DB / table isn't ready
      - signal handler swallows command failures into a warning log
"""
import io
import os
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

from finance.management.commands.install_finance_workflows import (
    _WORKFLOWS_DIR,
    _deterministic_id,
    _load_workflow_files,
)
from finance.signals import install_workflows_on_migrate


_WORKFLOWS_DIR_ABS = os.path.normpath(_WORKFLOWS_DIR)


class DryRunTest(SimpleTestCase):
    def test_dry_run_does_not_import_application_model(self):
        """
        ``--dry-run`` should be a pure-discovery walk: it must NOT pull in
        the ``application`` model (which would require the DB during a
        plain SimpleTestCase run). We patch ``update_or_create`` to make
        sure it's never called.
        """
        from application.models import application as application_mod

        with mock.patch.object(
            application_mod.Application.objects,
            'update_or_create',
        ) as upsert:
            buf = io.StringIO()
            call_command('install_finance_workflows', '--dry-run', stdout=buf)
            self.assertEqual(upsert.call_count, 0)

        out = buf.getvalue()
        self.assertIn('[dry-run]', out)
        # Discovered file names appear in the output.
        self.assertIn('document_generator.json', out)
        self.assertIn('materials_packager.json', out)


class DiscoveryTest(SimpleTestCase):
    def test_workflows_directory_contains_both_presets(self):
        files = _load_workflow_files(_WORKFLOWS_DIR_ABS)
        slugs = {(data or {}).get('slug') for _name, data in files if data}
        # Names not pinned (slug is part of the JSON itself), but both
        # filenames map to a slug.
        self.assertEqual(len(files), 2)
        self.assertTrue(all(s for s in slugs), f'all slugs non-empty: got {slugs}')

    def test_deterministic_id_stable_across_runs(self):
        a = _deterministic_id('finance-document-generator')
        b = _deterministic_id('finance-document-generator')
        self.assertEqual(a, b)


class SignalHandlerResilienceTest(SimpleTestCase):
    """
    The post_migrate signal must NEVER raise. These tests stub the
    Django connection / call_command boundary to exercise each
    failure path.
    """

    def test_handler_skips_when_db_introspection_fails(self):
        """
        If ``connection.introspection.table_names`` raises (DB not yet
        ready, or replica lag) the handler must short-circuit without
        calling ``call_command``.
        """
        # Patch the connection module access. Easiest: patch table_names
        # on the introspection object via the connection import path
        # used inside the handler.
        with mock.patch('django.db.connection.introspection') as introspection:
            introspection.table_names.side_effect = RuntimeError('db down')
            with mock.patch(
                'finance.signals.call_command'
            ) as cc:
                # Should NOT raise.
                install_workflows_on_migrate(sender=None)
                self.assertEqual(cc.call_count, 0)

    def test_handler_skips_when_application_table_missing(self):
        with mock.patch('django.db.connection.introspection') as introspection:
            introspection.table_names.return_value = ['users', 'finance_project']
            with mock.patch('finance.signals.call_command') as cc:
                install_workflows_on_migrate(sender=None)
                self.assertEqual(cc.call_count, 0)

    def test_handler_swallows_command_exception(self):
        """If the management command itself raises, we WARN — not fatal."""
        with mock.patch('django.db.connection.introspection') as introspection:
            introspection.table_names.return_value = ['application', 'users']
            with mock.patch('finance.signals.call_command') as cc:
                cc.side_effect = RuntimeError('boom')
                # Must not propagate.
                try:
                    install_workflows_on_migrate(sender=None)
                except Exception:  # pragma: no cover
                    self.fail('signal handler must not raise')

    def test_handler_invokes_command_when_table_present(self):
        with mock.patch('django.db.connection.introspection') as introspection:
            introspection.table_names.return_value = ['application', 'users']
            with mock.patch('finance.signals.call_command') as cc:
                install_workflows_on_migrate(sender=None)
                self.assertEqual(cc.call_count, 1)
                # Called with verbosity=0 (quiet)
                args, kwargs = cc.call_args
                self.assertEqual(args[0], 'install_finance_workflows')
                self.assertEqual(kwargs.get('verbosity'), 0)
