# coding=utf-8
"""
    @project: MaxKB
    @file:   test_signed_url.py
    @desc:   Unit tests for the finance signed-URL service (Gate 6 Track C / C1).

    Pure-Python: exercises Django's signing machinery directly; no DB or
    HTTP layer involved.
"""
from __future__ import annotations

import time
import uuid

from django.core import signing
from django.test import SimpleTestCase

from finance.service.signed_url import (
    DEFAULT_TTL_SECONDS,
    decode_signed_token,
    make_signed_download_url,
    short_token_id,
)


class SignedUrlMintTest(SimpleTestCase):
    def test_url_is_under_expected_prefix(self):
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id=uuid.uuid4(),
            workspace_id='ws-1',
            oss_key='oss-key-1',
        )
        self.assertTrue(url.startswith('/admin/api/finance/download/'))

    def test_round_trip_recovers_payload(self):
        tid = uuid.uuid4()
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id=tid,
            workspace_id='ws-2',
            oss_key='oss-key-2',
            ttl_seconds=600,
        )
        token = url.rsplit('/', 1)[-1]
        payload = decode_signed_token(token)
        self.assertEqual(payload['target_type'], 'MATERIALS_TASK')
        self.assertEqual(payload['target_id'], str(tid))
        self.assertEqual(payload['workspace_id'], 'ws-2')
        self.assertEqual(payload['oss_key'], 'oss-key-2')
        self.assertEqual(payload['ttl'], 600)

    def test_empty_oss_key_rejected(self):
        with self.assertRaises(ValueError):
            make_signed_download_url(
                target_type='MATERIALS_TASK',
                target_id='x',
                workspace_id='ws',
                oss_key='',
            )

    def test_nonpositive_ttl_rejected(self):
        with self.assertRaises(ValueError):
            make_signed_download_url(
                target_type='MATERIALS_TASK',
                target_id='x',
                workspace_id='ws',
                oss_key='ok',
                ttl_seconds=0,
            )

    def test_base_path_without_trailing_slash_is_normalised(self):
        url = make_signed_download_url(
            target_type='MATERIALS_TASK',
            target_id='x',
            workspace_id='ws',
            oss_key='ok',
            base_path='/custom/prefix',
        )
        self.assertTrue(url.startswith('/custom/prefix/'))


class SignedUrlVerifyTest(SimpleTestCase):
    def _mint(self, **overrides):
        kwargs = dict(
            target_type='MATERIALS_TASK',
            target_id='task-1',
            workspace_id='ws',
            oss_key='blob',
        )
        kwargs.update(overrides)
        url = make_signed_download_url(**kwargs)
        return url.rsplit('/', 1)[-1]

    def test_tampered_token_rejected(self):
        token = self._mint()
        # Flip the last meaningful character; signature must fail.
        tampered = token[:-1] + ('A' if token[-1] != 'A' else 'B')
        with self.assertRaises(signing.BadSignature):
            decode_signed_token(tampered)

    def test_empty_token_rejected(self):
        with self.assertRaises(signing.BadSignature):
            decode_signed_token('')

    def test_expired_token_rejected(self):
        # Mint a token that's already past its TTL by signing with a
        # very small ttl and explicitly verifying with max_age=1 and a
        # forced sleep.
        token = self._mint(ttl_seconds=1)
        time.sleep(1.2)
        with self.assertRaises(signing.SignatureExpired):
            decode_signed_token(token, max_age=1)

    def test_explicit_max_age_overrides_embedded_ttl(self):
        # Mint with a 7d ttl; pass max_age=1 with a sleep — must expire.
        token = self._mint(ttl_seconds=DEFAULT_TTL_SECONDS)
        time.sleep(1.2)
        with self.assertRaises(signing.SignatureExpired):
            decode_signed_token(token, max_age=1)

    def test_wrong_salt_rejected(self):
        # A token signed with a DIFFERENT salt must NOT verify under
        # ours — proves the salt scoping is doing its job.
        bogus = signing.dumps(
            {'oss_key': 'x'},
            salt='not.finance.salt',
        )
        with self.assertRaises(signing.BadSignature):
            decode_signed_token(bogus)


class ShortTokenIdTest(SimpleTestCase):
    def test_short_token_id_compacts(self):
        token = 'a' * 64
        sid = short_token_id(token)
        self.assertIn('..', sid)
        self.assertLessEqual(len(sid), 16)

    def test_short_token_id_handles_short_input(self):
        self.assertEqual(short_token_id(''), '')
        sid = short_token_id('abc')
        self.assertIn('..', sid)
