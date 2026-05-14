# coding=utf-8
"""
    @project: MaxKB
    @file： test_generation_views.py
    @desc: View-layer tests for DocumentGeneration.

    The view methods themselves are wrapped in @has_permissions /
    @audit_log / @extend_schema, which need a full auth context to invoke.
    Rather than mock that whole pipeline, the view module exposes
    decorator-free helpers (`_do_confirm`, `_do_revoke`, `_do_ai_fill`,
    `_get_or_404`); those are what we exercise here.

    Focus:
      - state-machine guards (confirm only from PENDING_REVIEW; revoke from
        CONFIRMED/PENDING_REVIEW)
      - AI-fill stub returns the expected keyed dict
      - serializer validation
"""
import uuid
from unittest import TestCase, mock

from common.exception.app_exception import AppApiException, NotFound404
from finance.models import GenerationStatus
from finance.serializers.document_generation import (
    AIFillRequestSerializer,
    DocumentGenerationCreateSerializer,
)
from finance.views.document_generation import (
    _do_ai_fill,
    _do_confirm,
    _do_revoke,
    _get_or_404,
)


class _FakeGen:
    """Stand-in for a DocumentGeneration row that records saves."""

    def __init__(self, status, *, id_=None):
        self.id = id_ or uuid.uuid4()
        self.workspace_id = uuid.uuid4()
        self.status = status
        self.reviewer_id = None
        self.reviewed_at = None
        self.template_id = uuid.uuid4()
        self.saved_fields = None

    def save(self, update_fields=None):
        self.saved_fields = update_fields


# ----------------------- Serializer-level coverage -----------------------


class CreateSerializerTest(TestCase):
    def test_minimal_payload(self):
        s = DocumentGenerationCreateSerializer(data={
            'project_id': str(uuid.uuid4()),
            'template_id': str(uuid.uuid4()),
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['placeholder_values'], {})

    def test_accepts_placeholder_values(self):
        s = DocumentGenerationCreateSerializer(data={
            'project_id': str(uuid.uuid4()),
            'template_id': str(uuid.uuid4()),
            'placeholder_values': {'company_name': 'ACME', 'loan_amount': 1000000},
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['placeholder_values']['company_name'], 'ACME')

    def test_requires_ids(self):
        s = DocumentGenerationCreateSerializer(data={})
        self.assertFalse(s.is_valid())
        self.assertIn('project_id', s.errors)
        self.assertIn('template_id', s.errors)


class AIFillSerializerTest(TestCase):
    def test_rejects_empty_keys(self):
        s = AIFillRequestSerializer(data={
            'template_id': str(uuid.uuid4()),
            'project_id': str(uuid.uuid4()),
            'placeholder_keys': [],
        })
        self.assertFalse(s.is_valid())

    def test_accepts_payload(self):
        s = AIFillRequestSerializer(data={
            'template_id': str(uuid.uuid4()),
            'project_id': str(uuid.uuid4()),
            'placeholder_keys': ['risk_analysis', 'project_summary'],
        })
        self.assertTrue(s.is_valid(), s.errors)


# ----------------------- State-machine guards -----------------------


class ConfirmStateMachineTest(TestCase):
    def test_confirm_from_pending_review_succeeds(self):
        row = _FakeGen(GenerationStatus.PENDING_REVIEW)
        actor = uuid.uuid4()
        _do_confirm(row, actor)
        self.assertEqual(row.status, GenerationStatus.CONFIRMED)
        self.assertEqual(row.reviewer_id, actor)
        self.assertIsNotNone(row.reviewed_at)
        self.assertIn('status', row.saved_fields)
        self.assertIn('reviewer_id', row.saved_fields)

    def test_confirm_from_other_state_raises(self):
        for bad in (GenerationStatus.GENERATING, GenerationStatus.CONFIRMED,
                    GenerationStatus.REVOKED, GenerationStatus.FAILED):
            row = _FakeGen(bad)
            with self.assertRaises(AppApiException):
                _do_confirm(row, uuid.uuid4())


class RevokeStateMachineTest(TestCase):
    def test_revoke_from_pending_review(self):
        row = _FakeGen(GenerationStatus.PENDING_REVIEW)
        _do_revoke(row, uuid.uuid4())
        self.assertEqual(row.status, GenerationStatus.REVOKED)

    def test_revoke_from_confirmed(self):
        row = _FakeGen(GenerationStatus.CONFIRMED)
        _do_revoke(row, uuid.uuid4())
        self.assertEqual(row.status, GenerationStatus.REVOKED)

    def test_revoke_from_failed_raises(self):
        row = _FakeGen(GenerationStatus.FAILED)
        with self.assertRaises(AppApiException):
            _do_revoke(row, uuid.uuid4())

    def test_revoke_from_generating_raises(self):
        row = _FakeGen(GenerationStatus.GENERATING)
        with self.assertRaises(AppApiException):
            _do_revoke(row, uuid.uuid4())


class GetOr404Test(TestCase):
    def test_raises_when_missing(self):
        qs = mock.MagicMock()
        qs.filter.return_value.first.return_value = None
        with mock.patch(
            'finance.views.document_generation.DocumentGeneration.objects', qs
        ):
            with self.assertRaises(NotFound404):
                _get_or_404(uuid.uuid4(), uuid.uuid4())

    def test_returns_when_found(self):
        sentinel = object()
        qs = mock.MagicMock()
        qs.filter.return_value.first.return_value = sentinel
        with mock.patch(
            'finance.views.document_generation.DocumentGeneration.objects', qs
        ):
            self.assertIs(_get_or_404(uuid.uuid4(), uuid.uuid4()), sentinel)


# ----------------------- AI fill stub -----------------------


class AIFillStubTest(TestCase):
    def test_returns_values_for_declared_keys_only(self):
        template = mock.MagicMock(placeholders=[
            {'key': 'risk_analysis', 'label': '风险分析', 'type': 'long_text'},
            {'key': 'project_summary', 'label': '项目摘要', 'type': 'long_text'},
        ])
        project = mock.MagicMock()
        filled = _do_ai_fill(template, project,
                             ['risk_analysis', 'unknown_key'])
        self.assertIn('risk_analysis', filled)
        self.assertNotIn('unknown_key', filled)
        # Recognisable stub marker — the UI uses this to know it's not real
        # content yet.
        self.assertIn('AI', filled['risk_analysis'])
        self.assertIn('风险分析', filled['risk_analysis'])

    def test_handles_template_with_no_placeholders(self):
        template = mock.MagicMock(placeholders=None)
        project = mock.MagicMock()
        filled = _do_ai_fill(template, project, ['any_key'])
        self.assertEqual(filled, {})

    def test_falls_back_to_key_when_label_blank(self):
        template = mock.MagicMock(placeholders=[
            {'key': 'risk_analysis', 'label': '', 'type': 'long_text'},
        ])
        filled = _do_ai_fill(template, mock.MagicMock(), ['risk_analysis'])
        self.assertIn('risk_analysis', filled['risk_analysis'])
