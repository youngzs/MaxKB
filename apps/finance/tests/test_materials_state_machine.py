# coding=utf-8
"""
    @project: MaxKB
    @file： test_materials_state_machine.py
    @desc: State-machine tests for the MaterialsTask views. Like
    test_generation_views, we exercise the decorator-free helpers
    (`_do_*`) so we don't need to boot a full auth context.
"""
import uuid
from unittest import TestCase, mock

from common.exception.app_exception import AppApiException
from finance.models import MaterialsTaskStatus
from finance.serializers.materials_task import (
    MaterialsTaskCreateSerializer,
    MaterialsTaskReviewSerializer,
    MaterialsTaskUpdateSelectionSerializer,
)
from finance.views.materials_task import (
    _do_pack,
    _do_review,
    _do_submit_review,
    _do_update_selection,
)


class _FakeTask:
    """Stand-in for a MaterialsTask row that records saves."""

    def __init__(self, *, status=MaterialsTaskStatus.DRAFT, zip_oss_key='',
                 selected=None, matched=None, parsed=None):
        self.id = uuid.uuid4()
        self.workspace_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.status = status
        self.zip_oss_key = zip_oss_key
        self.selected_documents = list(selected or [])
        self.matched_documents = list(matched or [])
        self.parsed_items = list(parsed or [])
        self.reviewer_id = None
        self.reviewed_at = None
        self.review_comment = ''
        self.error_message = ''
        self.saved_fields = None

    def save(self, update_fields=None):
        self.saved_fields = update_fields


# ----------------------- Serializer-level coverage -----------------------


class CreateSerializerTest(TestCase):
    def test_minimal_payload(self):
        s = MaterialsTaskCreateSerializer(data={
            'project_id': str(uuid.uuid4()),
            'title': '招商银行融资材料',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_with_text(self):
        s = MaterialsTaskCreateSerializer(data={
            'project_id': str(uuid.uuid4()),
            'title': 't',
            'requirement_text': '1. 财务报表\n2. 营业执照',
        })
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIn('财务报表', s.validated_data['requirement_text'])

    def test_missing_title(self):
        s = MaterialsTaskCreateSerializer(data={'project_id': str(uuid.uuid4())})
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)


class ReviewSerializerTest(TestCase):
    def test_pass(self):
        s = MaterialsTaskReviewSerializer(data={'action': 'pass'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_reject_with_comment(self):
        s = MaterialsTaskReviewSerializer(data={'action': 'reject', 'comment': 'missing X'})
        self.assertTrue(s.is_valid(), s.errors)

    def test_bad_action(self):
        s = MaterialsTaskReviewSerializer(data={'action': 'maybe'})
        self.assertFalse(s.is_valid())


class SelectionSerializerTest(TestCase):
    def test_empty_selection_allowed(self):
        s = MaterialsTaskUpdateSelectionSerializer(data={'selected_documents': []})
        self.assertTrue(s.is_valid(), s.errors)

    def test_uuid_only(self):
        s = MaterialsTaskUpdateSelectionSerializer(data={
            'selected_documents': [str(uuid.uuid4()), str(uuid.uuid4())],
        })
        self.assertTrue(s.is_valid(), s.errors)


# ----------------------- State-machine guards -----------------------


class SubmitReviewTest(TestCase):
    def test_submit_review_requires_zip(self):
        task = _FakeTask(status=MaterialsTaskStatus.APPROVED, zip_oss_key='')
        with self.assertRaises(AppApiException):
            _do_submit_review(task)

    def test_submit_review_from_approved(self):
        task = _FakeTask(status=MaterialsTaskStatus.APPROVED, zip_oss_key='abc')
        _do_submit_review(task)
        self.assertEqual(task.status, MaterialsTaskStatus.PENDING_REVIEW)

    def test_submit_review_from_draft_with_zip(self):
        task = _FakeTask(status=MaterialsTaskStatus.DRAFT, zip_oss_key='abc')
        _do_submit_review(task)
        self.assertEqual(task.status, MaterialsTaskStatus.PENDING_REVIEW)

    def test_submit_review_blocks_other_states(self):
        for bad in (
            MaterialsTaskStatus.PENDING_REVIEW,
            MaterialsTaskStatus.REJECTED,
            MaterialsTaskStatus.SENT,
        ):
            task = _FakeTask(status=bad, zip_oss_key='abc')
            with self.assertRaises(AppApiException):
                _do_submit_review(task)


class ReviewTest(TestCase):
    def test_pass_moves_to_approved(self):
        task = _FakeTask(status=MaterialsTaskStatus.PENDING_REVIEW)
        reviewer = uuid.uuid4()
        _do_review(task, action='pass', comment='', reviewer_id=reviewer)
        self.assertEqual(task.status, MaterialsTaskStatus.APPROVED)
        self.assertEqual(task.reviewer_id, reviewer)
        self.assertIsNotNone(task.reviewed_at)

    def test_reject_moves_to_rejected(self):
        task = _FakeTask(status=MaterialsTaskStatus.PENDING_REVIEW)
        _do_review(task, action='reject', comment='missing X', reviewer_id=uuid.uuid4())
        self.assertEqual(task.status, MaterialsTaskStatus.REJECTED)
        self.assertEqual(task.review_comment, 'missing X')

    def test_review_blocks_non_pending(self):
        for bad in (MaterialsTaskStatus.DRAFT, MaterialsTaskStatus.APPROVED, MaterialsTaskStatus.REJECTED):
            task = _FakeTask(status=bad)
            with self.assertRaises(AppApiException):
                _do_review(task, action='pass', comment='', reviewer_id=uuid.uuid4())

    def test_unknown_action(self):
        task = _FakeTask(status=MaterialsTaskStatus.PENDING_REVIEW)
        with self.assertRaises(AppApiException):
            _do_review(task, action='delete', comment='', reviewer_id=uuid.uuid4())


class PackTest(TestCase):
    def test_pack_requires_selection(self):
        task = _FakeTask(status=MaterialsTaskStatus.DRAFT, selected=[])
        with self.assertRaises(AppApiException):
            _do_pack(task, workspace_id=task.workspace_id)

    def test_pack_with_override_groups(self):
        task = _FakeTask(
            status=MaterialsTaskStatus.DRAFT,
            selected=[str(uuid.uuid4())],
        )
        groups = [{'folder': '01_财务', 'document_ids': task.selected_documents}]
        with mock.patch(
            'finance.views.materials_task.pack_documents_grouped',
            return_value='fake-oss-key',
        ):
            _do_pack(task, workspace_id=task.workspace_id, override_groups=groups)
        self.assertEqual(task.status, MaterialsTaskStatus.APPROVED)
        self.assertEqual(task.zip_oss_key, 'fake-oss-key')

    def test_pack_blocks_when_groups_underivable(self):
        # No parsed_items and no matched_documents — pack can't derive groups.
        task = _FakeTask(
            status=MaterialsTaskStatus.DRAFT,
            selected=[str(uuid.uuid4())],
            matched=[],
            parsed=[],
        )
        with self.assertRaises(AppApiException):
            _do_pack(task, workspace_id=task.workspace_id)


class SelectionUpdateTest(TestCase):
    def test_update_selection_coerces_to_strings(self):
        task = _FakeTask()
        a, b = uuid.uuid4(), uuid.uuid4()
        _do_update_selection(task, selected_documents=[a, b])
        self.assertEqual(task.selected_documents, [str(a), str(b)])

    def test_update_selection_can_replace_matched(self):
        task = _FakeTask(matched=[{'item_key': 'x', 'document_id': 'y'}])
        new_matched = [{'item_key': 'z', 'document_id': 'w'}]
        _do_update_selection(task, selected_documents=[], matched_documents=new_matched)
        self.assertEqual(task.matched_documents, new_matched)
