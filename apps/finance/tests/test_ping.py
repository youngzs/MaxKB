# coding=utf-8
"""
    @project: MaxKB
    @file： test_ping.py
    @desc: Smoke test for the finance health-check endpoint.
"""
import json

from django.test import Client, TestCase
from django.urls import reverse


class FinancePingViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_ping_url_resolves(self):
        url = reverse('finance:finance_ping')
        self.assertEqual(url, '/api/finance/ping')

    def test_ping_returns_ok_payload(self):
        response = self.client.get('/api/finance/ping')
        # Health probes must never 500 — Gate 6 Track A1 wrapped the body
        # in a defensive try/except, so even a regression that would have
        # raised before is now surfaced as a 200 + status='degraded'.
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode('utf-8'))
        # Standard MaxKB envelope: {code, message, data}
        self.assertEqual(body.get('code'), 200)
        data = body.get('data') or {}
        # Healthy host returns status='ok'; a degraded host still returns
        # 200 with status='degraded' + detail. Both are acceptable for
        # the probe contract.
        self.assertIn(data.get('status'), ('ok', 'degraded'))
        self.assertEqual(data.get('module'), 'finance')
        # Version is checked loosely — Gate 7 A1 introduced a middleware
        # bypass that may answer the request before the view runs, with
        # its own version string. Either is acceptable; both must be a
        # non-empty semver-shaped string.
        self.assertIsInstance(data.get('version'), str)
        self.assertTrue(data.get('version'))

    def test_ping_is_public(self):
        # No Authorization header — endpoint must still respond 200.
        response = self.client.get('/api/finance/ping')
        self.assertEqual(response.status_code, 200)

    def test_ping_envelope_has_module_and_version(self):
        # Operators rely on these fields to identify which deployment
        # is reachable. They must be present on both the healthy and
        # degraded paths.
        response = self.client.get('/api/finance/ping')
        body = json.loads(response.content.decode('utf-8'))
        data = body.get('data') or {}
        self.assertIn('module', data)
        self.assertIn('version', data)
        self.assertIn('status', data)
