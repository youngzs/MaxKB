# coding=utf-8
"""
    @project: MaxKB
    @file:   test_signed_download_view.py
    @desc:   Tests for the finance signed-URL download view (Gate 6 Track C / C1).

    These exercise the token-verification fast paths (expired / bad sig /
    malformed) without needing the OSS blob layer or DB rows — we mock
    `_load_bytes` and `log_event` so the test stays a SimpleTestCase
    where possible.
"""
from __future__ import annotations

import time
from unittest.mock import patch

from django.core import signing
from django.test import RequestFactory, SimpleTestCase

from common.exception.app_exception import AppApiException
from finance.service.signed_url import make_signed_download_url
from finance.views.signed_download import SignedDownloadView


class SignedDownloadViewTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = SignedDownloadView.as_view()

    def _build_request(self, path: str):
        return self.factory.get(path, HTTP_USER_AGENT='pytest')

    def test_valid_token_streams_bytes(self):
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id='task-1',
            workspace_id='ws',
            oss_key='blob-1',
        )
        token = url.rsplit('/', 1)[-1]
        request = self._build_request(url)

        with patch(
            'finance.views.signed_download._load_bytes',
            return_value=b'PK\x03\x04dummy-zip-bytes',
        ), patch(
            'finance.views.signed_download.log_event'
        ) as mock_log:
            response = self.view(request, token=token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment', response['Content-Disposition'])
        # Audit row written with result=ok
        mock_log.assert_called()
        payload = mock_log.call_args.kwargs.get('payload') or {}
        self.assertEqual(payload.get('result'), 'ok')

    def test_expired_token_returns_410(self):
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id='task-2',
            workspace_id='ws',
            oss_key='blob-2',
            ttl_seconds=1,
        )
        token = url.rsplit('/', 1)[-1]
        time.sleep(1.2)
        request = self._build_request(url)

        with patch(
            'finance.views.signed_download.log_event'
        ) as mock_log, patch(
            # Verify with max_age=1 so the embedded ttl doesn't save us.
            'finance.views.signed_download.decode_signed_token',
            side_effect=signing.SignatureExpired('expired'),
        ):
            with self.assertRaises(AppApiException) as ctx:
                self.view(request, token=token)

        self.assertEqual(ctx.exception.code, 410)
        mock_log.assert_called()
        payload = mock_log.call_args.kwargs.get('payload') or {}
        self.assertEqual(payload.get('result'), 'expired')

    def test_tampered_token_returns_403(self):
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id='task-3',
            workspace_id='ws',
            oss_key='blob-3',
        )
        token = url.rsplit('/', 1)[-1]
        # Flip a character to invalidate the signature.
        tampered = token[:-1] + ('A' if token[-1] != 'A' else 'B')
        request = self._build_request('/admin/api/finance/download/' + tampered)

        with patch('finance.views.signed_download.log_event') as mock_log:
            with self.assertRaises(AppApiException) as ctx:
                self.view(request, token=tampered)

        self.assertEqual(ctx.exception.code, 403)
        mock_log.assert_called()
        payload = mock_log.call_args.kwargs.get('payload') or {}
        self.assertEqual(payload.get('result'), 'invalid_signature')

    def test_oss_lookup_failure_returns_404_envelope(self):
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id='task-4',
            workspace_id='ws',
            oss_key='blob-missing',
        )
        token = url.rsplit('/', 1)[-1]
        request = self._build_request(url)

        with patch(
            'finance.views.signed_download._load_bytes',
            side_effect=ValueError('not found'),
        ), patch(
            'finance.views.signed_download.log_event'
        ) as mock_log:
            response = self.view(request, token=token)

        self.assertEqual(response.status_code, 404)
        mock_log.assert_called()
        payload = mock_log.call_args.kwargs.get('payload') or {}
        self.assertEqual(payload.get('result'), 'oss_lookup_failed')
