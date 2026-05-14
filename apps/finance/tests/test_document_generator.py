# coding=utf-8
"""
    @project: MaxKB
    @file： test_document_generator.py
    @desc: Tests for finance.service.document_generator.

    We exercise the trigger_generation state machine by mocking the OSS layer
    (`_save_bytes`, `_load_bytes`) and the docxtpl render call, so the test
    runs without a database or docx stack.
"""
import uuid
from unittest import TestCase, mock

from finance.service import document_generator as gen


class _FakeGen:
    """Stand-in for DocumentGeneration model row."""

    def __init__(self, *, status, template_id, placeholder_values=None, output_oss_key='',
                 error_message='', id_=None):
        self.id = id_ or uuid.uuid4()
        self.status = status
        self.template_id = template_id
        self.placeholder_values = placeholder_values or {}
        self.output_oss_key = output_oss_key
        self.error_message = error_message
        self.saved_fields = None

    def save(self, update_fields=None):
        # Capture the last set of update_fields so the test can assert what
        # the service touched (a stand-in for a real ORM save).
        self.saved_fields = update_fields


class _FakeTemplate:
    def __init__(self, oss_key='tpl-key', is_deleted=False):
        self.docx_oss_key = oss_key
        self.version = 1
        self.is_deleted = is_deleted


class TriggerGenerationTest(TestCase):
    def test_happy_path_moves_to_pending_review(self):
        gen_row = _FakeGen(status='generating', template_id=uuid.uuid4())
        tpl = _FakeTemplate()

        gen_qs = mock.MagicMock()
        gen_qs.filter.return_value.first.return_value = gen_row
        tpl_qs = mock.MagicMock()
        tpl_qs.filter.return_value.first.return_value = tpl

        with mock.patch('finance.models.DocumentGeneration.objects', gen_qs), \
             mock.patch('finance.models.DocumentTemplate.objects', tpl_qs), \
             mock.patch.object(gen, 'render_template', return_value='out-key-123') as render:
            gen.trigger_generation(gen_row.id)

        render.assert_called_once()
        self.assertEqual(gen_row.status, 'pending_review')
        self.assertEqual(gen_row.output_oss_key, 'out-key-123')
        self.assertEqual(gen_row.error_message, '')
        self.assertIn('output_oss_key', gen_row.saved_fields)
        self.assertIn('status', gen_row.saved_fields)

    def test_render_failure_sets_failed(self):
        gen_row = _FakeGen(status='generating', template_id=uuid.uuid4())
        tpl = _FakeTemplate()
        gen_qs = mock.MagicMock()
        gen_qs.filter.return_value.first.return_value = gen_row
        tpl_qs = mock.MagicMock()
        tpl_qs.filter.return_value.first.return_value = tpl

        with mock.patch('finance.models.DocumentGeneration.objects', gen_qs), \
             mock.patch('finance.models.DocumentTemplate.objects', tpl_qs), \
             mock.patch.object(gen, 'render_template',
                               side_effect=RuntimeError('boom')):
            gen.trigger_generation(gen_row.id)

        self.assertEqual(gen_row.status, 'failed')
        self.assertIn('boom', gen_row.error_message)
        self.assertIn('status', gen_row.saved_fields)

    def test_missing_template_sets_failed(self):
        gen_row = _FakeGen(status='generating', template_id=uuid.uuid4())
        gen_qs = mock.MagicMock()
        gen_qs.filter.return_value.first.return_value = gen_row
        tpl_qs = mock.MagicMock()
        tpl_qs.filter.return_value.first.return_value = None

        with mock.patch('finance.models.DocumentGeneration.objects', gen_qs), \
             mock.patch('finance.models.DocumentTemplate.objects', tpl_qs):
            gen.trigger_generation(gen_row.id)

        self.assertEqual(gen_row.status, 'failed')
        self.assertIn('not found', gen_row.error_message)

    def test_wrong_status_is_no_op(self):
        gen_row = _FakeGen(status='confirmed', template_id=uuid.uuid4())
        gen_qs = mock.MagicMock()
        gen_qs.filter.return_value.first.return_value = gen_row
        tpl_qs = mock.MagicMock()

        with mock.patch('finance.models.DocumentGeneration.objects', gen_qs), \
             mock.patch('finance.models.DocumentTemplate.objects', tpl_qs):
            gen.trigger_generation(gen_row.id)

        # Row not touched; tpl lookup not even attempted.
        self.assertEqual(gen_row.status, 'confirmed')
        self.assertIsNone(gen_row.saved_fields)
        tpl_qs.filter.assert_not_called()

    def test_missing_generation_is_silent(self):
        gen_qs = mock.MagicMock()
        gen_qs.filter.return_value.first.return_value = None
        with mock.patch('finance.models.DocumentGeneration.objects', gen_qs), \
             mock.patch('finance.models.DocumentTemplate.objects', mock.MagicMock()):
            # Must not raise.
            gen.trigger_generation(uuid.uuid4())
