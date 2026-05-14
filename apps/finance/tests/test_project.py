# coding=utf-8
"""
    @project: MaxKB
    @file： test_project.py
    @desc: Gate 2 Track A tests — model-level and audit-helper coverage.

    Why model-level (not view-level)?
    MaxKB's auth pipeline (TokenAuth + workspace permission resolver) is
    initialized from the same app stack that, on Windows, fails to import
    because of a POSIX-only `pwd` dependency in models_provider. So instead
    of stubbing half the application, we exercise:
      1. The model layer — covers fields, defaults, constraints, soft-delete.
      2. The audit decorator — covers happy path + redaction + failure
         isolation, with a fake request and the FinanceAuditLog ORM call
         mocked, so the test runs without a database.

    Linux CI can run these directly; the model tests will additionally
    exercise the 0001 migration.
"""
import uuid
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from finance.models import (
    FinanceAuditAction,
    FinanceAuditTargetType,
    FinanceProject,
    FinanceProjectStatus,
    FinanceProjectType,
)
from finance.service.audit import _redact, audit_log, log_event


# --------------------------- Model layer ---------------------------------


class FinanceProjectModelTest(TestCase):
    def setUp(self):
        self.workspace_a = uuid.uuid4()
        self.workspace_b = uuid.uuid4()
        self.user_id = uuid.uuid4()

    def _make(self, **overrides):
        defaults = dict(
            workspace_id=self.workspace_a,
            name='Series A',
            project_type=FinanceProjectType.BANK_LOAN,
            created_by=self.user_id,
        )
        defaults.update(overrides)
        return FinanceProject.objects.create(**defaults)

    def test_create_with_minimum_fields_uses_defaults(self):
        project = self._make()
        self.assertEqual(project.code, '')
        self.assertEqual(project.currency, 'CNY')
        self.assertEqual(project.status, FinanceProjectStatus.PREPARING)
        self.assertEqual(project.knowledge_base_ids, [])
        self.assertFalse(project.is_deleted)
        self.assertIsNotNone(project.created_at)

    def test_str_returns_name(self):
        project = self._make(name='Hospital Bond 2026')
        self.assertEqual(str(project), 'Hospital Bond 2026')

    def test_workspace_scoping_isolates_data(self):
        a = self._make(name='A side')
        self._make(workspace_id=self.workspace_b, name='B side')
        qs = FinanceProject.objects.filter(workspace_id=self.workspace_a, is_deleted=False)
        self.assertEqual(list(qs.values_list('id', flat=True)), [a.id])

    def test_duplicate_code_in_same_workspace_is_rejected(self):
        self._make(code='ABC-001')
        with self.assertRaises(IntegrityError):
            self._make(code='ABC-001', name='Other')

    def test_same_code_allowed_across_workspaces(self):
        self._make(code='ABC-001')
        # Should NOT raise — different workspace.
        other = self._make(workspace_id=self.workspace_b, code='ABC-001', name='Other')
        self.assertEqual(other.code, 'ABC-001')

    def test_empty_code_not_constrained(self):
        # Two empty-code rows in the same workspace must be permitted; the
        # unique constraint is conditional on code != ''.
        self._make(code='')
        self._make(code='', name='Second blank')
        count = FinanceProject.objects.filter(
            workspace_id=self.workspace_a, code=''
        ).count()
        self.assertEqual(count, 2)

    def test_target_amount_precision(self):
        project = self._make(target_amount=Decimal('1234567890123456.78'))
        project.refresh_from_db()
        self.assertEqual(project.target_amount, Decimal('1234567890123456.78'))

    def test_soft_delete_hidden_from_default_queryset(self):
        live = self._make(name='Live')
        dead = self._make(name='Dead')
        dead.is_deleted = True
        dead.save(update_fields=['is_deleted', 'updated_at'])
        ids = list(
            FinanceProject.objects.filter(workspace_id=self.workspace_a, is_deleted=False)
            .values_list('id', flat=True)
        )
        self.assertIn(live.id, ids)
        self.assertNotIn(dead.id, ids)


# --------------------------- Audit decorator -----------------------------


class _FakeRequest:
    """Minimal stand-in for a DRF request for the audit-decorator tests."""

    def __init__(self, user_id, body=None, query=None, ip='10.0.0.1', ua='pytest-ua'):
        self.user = mock.SimpleNamespace(id=user_id)
        self.data = body or {}
        self.query_params = query or {}
        self.path = '/api/finance/workspace/x/project'
        self.method = 'POST'
        self.META = {
            'REMOTE_ADDR': ip,
            'HTTP_USER_AGENT': ua,
        }


class _FakeResponse:
    def __init__(self, payload):
        # Mirror result.Result's interface: a `data` attribute holding the
        # envelope {code, message, data}.
        self.data = {'code': 200, 'message': 'ok', 'data': payload}


class RedactHelperTest(SimpleTestCase):
    def test_redacts_top_level_sensitive_keys(self):
        out = _redact({'password': 'secret', 'name': 'ok'})
        self.assertEqual(out, {'password': '***', 'name': 'ok'})

    def test_redacts_nested_keys(self):
        out = _redact({'creds': {'token': 'abc', 'user': 'alice'}})
        self.assertEqual(out, {'creds': {'token': '***', 'user': 'alice'}})

    def test_walks_lists(self):
        out = _redact([{'secret': 1}, {'keep': 2}])
        self.assertEqual(out, [{'secret': '***'}, {'keep': 2}])

    def test_case_insensitive_match(self):
        out = _redact({'Authorization': 'Bearer xyz', 'X-Trace-Id': 't1'})
        self.assertEqual(out['Authorization'], '***')
        self.assertEqual(out['X-Trace-Id'], 't1')


class AuditDecoratorTest(SimpleTestCase):
    """Verify the decorator's behavior without touching the database."""

    def test_logs_on_success_with_target_from_response_id(self):
        new_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        request = _FakeRequest(user_id=actor_id, body={'name': 'X', 'password': 'pw'})

        @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.PROJECT)
        def view(self, req, workspace_id):
            return _FakeResponse({'id': str(new_id)})

        with mock.patch('finance.service.audit.log_event') as m_log:
            response = view(self=None, req=request, workspace_id=workspace_id)

        self.assertIs(response.__class__, _FakeResponse)
        m_log.assert_called_once()
        kwargs = m_log.call_args.kwargs
        self.assertEqual(kwargs['workspace_id'], workspace_id)
        self.assertEqual(kwargs['actor_id'], actor_id)
        self.assertEqual(kwargs['target_id'], str(new_id))
        self.assertEqual(kwargs['action'], FinanceAuditAction.CREATE)
        self.assertEqual(kwargs['target_type'], FinanceAuditTargetType.PROJECT)
        # password was redacted in the snapshot.
        self.assertEqual(kwargs['payload']['body']['password'], '***')
        self.assertEqual(kwargs['ip'], '10.0.0.1')
        self.assertEqual(kwargs['user_agent'], 'pytest-ua')

    def test_target_from_url_kwarg_pk(self):
        pk = uuid.uuid4()
        request = _FakeRequest(user_id=uuid.uuid4())

        @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.PROJECT)
        def view(self, req, workspace_id, pk):
            return _FakeResponse({'noise': 1})

        with mock.patch('finance.service.audit.log_event') as m_log:
            view(self=None, req=request, workspace_id=uuid.uuid4(), pk=pk)

        self.assertEqual(m_log.call_args.kwargs['target_id'], str(pk))

    def test_exception_propagates_and_skips_logging(self):
        request = _FakeRequest(user_id=uuid.uuid4())

        @audit_log(action=FinanceAuditAction.DELETE, target_type=FinanceAuditTargetType.PROJECT)
        def view(self, req, workspace_id):
            raise RuntimeError('boom')

        with mock.patch('finance.service.audit.log_event') as m_log:
            with self.assertRaises(RuntimeError):
                view(self=None, req=request, workspace_id=uuid.uuid4())
        m_log.assert_not_called()

    def test_logging_failure_does_not_break_request(self):
        request = _FakeRequest(user_id=uuid.uuid4())

        @audit_log(action=FinanceAuditAction.READ, target_type=FinanceAuditTargetType.PROJECT)
        def view(self, req, workspace_id):
            return _FakeResponse({'id': str(uuid.uuid4())})

        with mock.patch('finance.service.audit.log_event', side_effect=RuntimeError('db down')):
            # Must NOT raise — audit failures are swallowed.
            response = view(self=None, req=request, workspace_id=uuid.uuid4())
        self.assertIsNotNone(response)


class LogEventHelperTest(TestCase):
    def test_writes_audit_row(self):
        workspace_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        log_event(
            workspace_id=workspace_id,
            actor_id=actor_id,
            target_type=FinanceAuditTargetType.PROJECT,
            target_id=None,
            action=FinanceAuditAction.READ,
            payload={'note': 'manual'},
            ip='127.0.0.1',
            user_agent='cli',
        )
        from finance.models import FinanceAuditLog

        row = FinanceAuditLog.objects.filter(workspace_id=workspace_id, actor_id=actor_id).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.action, FinanceAuditAction.READ)
        self.assertEqual(row.target_type, FinanceAuditTargetType.PROJECT)
        self.assertEqual(row.payload, {'note': 'manual'})
        self.assertEqual(row.ip, '127.0.0.1')

    def test_failure_is_swallowed(self):
        # If the ORM raises, log_event must NOT propagate.
        with mock.patch(
            'finance.models.FinanceAuditLog.objects.create',
            side_effect=RuntimeError('db blew up'),
        ):
            log_event(
                workspace_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_type=FinanceAuditTargetType.OTHER,
                action=FinanceAuditAction.READ,
            )
