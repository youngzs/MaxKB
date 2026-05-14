# coding=utf-8
"""
    @project: MaxKB
    @file： test_template_views.py
    @desc: Light-weight tests for DocumentTemplate view-layer behaviours
    that can be exercised without booting the full Django auth pipeline.

    Why not full HTTP-level integration tests?
    See test_project.py: on Windows the upstream auth stack fails to import
    (POSIX-only `pwd`). On Linux CI you can replace these with proper
    APITestCase runs — the assertions here are still useful unit-level
    coverage of validation, paginator, and serializer behaviours.
"""
from unittest import TestCase, mock

from common.exception.app_exception import AppApiException
from finance.serializers.document_template import (
    DocumentTemplateUpdateSerializer,
    DocumentTemplateUploadSerializer,
)
from finance.views.document_template import (
    _paginate,
    _parse_int,
    _validate_docx_upload,
)


class _UploadStub:
    """Stand-in for a Django UploadedFile."""

    def __init__(self, name, content_type='', payload=b''):
        self.name = name
        self.content_type = content_type
        self._payload = payload

    def read(self):
        return self._payload


class ValidateDocxUploadTest(TestCase):
    def test_accepts_docx_with_correct_mime(self):
        f = _UploadStub('report.docx',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        # Must not raise.
        _validate_docx_upload(f)

    def test_accepts_docx_with_octet_stream(self):
        f = _UploadStub('report.docx', 'application/octet-stream')
        _validate_docx_upload(f)

    def test_rejects_non_docx_extension(self):
        f = _UploadStub('report.pdf',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        with self.assertRaises(AppApiException):
            _validate_docx_upload(f)

    def test_rejects_missing_file(self):
        with self.assertRaises(AppApiException):
            _validate_docx_upload(None)

    def test_rejects_wrong_mime(self):
        f = _UploadStub('report.docx', 'text/html')
        with self.assertRaises(AppApiException):
            _validate_docx_upload(f)


class PaginatorHelpersTest(TestCase):
    def test_parse_int_uses_default_for_garbage(self):
        self.assertEqual(_parse_int('abc', 7), 7)
        self.assertEqual(_parse_int(None, 7), 7)
        self.assertEqual(_parse_int('-3', 7), 7)
        self.assertEqual(_parse_int('5', 7), 5)

    def test_paginate_respects_max(self):
        qs = mock.MagicMock()
        qs.count.return_value = 9999
        qs.__getitem__.return_value = ['x'] * 5
        total, page, size, records = _paginate(qs, {'page': '2', 'size': '999'})
        self.assertEqual(total, 9999)
        self.assertEqual(page, 2)
        # 200 is the cap defined in the view module.
        self.assertEqual(size, 200)


class UploadSerializerTest(TestCase):
    def test_defaults_scenario_to_other(self):
        f = _UploadStub('a.docx')
        serializer = DocumentTemplateUploadSerializer(data={'file': f, 'name': 'Hello'})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['scenario'], 'other')

    def test_rejects_unknown_scenario(self):
        f = _UploadStub('a.docx')
        serializer = DocumentTemplateUploadSerializer(
            data={'file': f, 'name': 'Hello', 'scenario': 'not-a-thing'}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('scenario', serializer.errors)


class UpdateSerializerTest(TestCase):
    def test_accepts_partial_payload(self):
        serializer = DocumentTemplateUpdateSerializer(data={'is_active': False})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_validates_placeholder_shape(self):
        good = [
            {'key': 'company_name', 'label': '公司名', 'type': 'text',
             'required': True, 'ai_hint': '', 'enum_options': []},
            {'key': 'risk_summary', 'label': '风险摘要', 'type': 'long_text',
             'required': False, 'ai_hint': '总结公司风险', 'enum_options': []},
        ]
        s = DocumentTemplateUpdateSerializer(data={'placeholders': good})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(len(s.validated_data['placeholders']), 2)

    def test_rejects_bad_placeholder_type(self):
        bad = [{'key': 'x', 'type': 'colour'}]
        s = DocumentTemplateUpdateSerializer(data={'placeholders': bad})
        self.assertFalse(s.is_valid())
