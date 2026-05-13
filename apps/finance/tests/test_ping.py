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
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode('utf-8'))
        # Standard MaxKB envelope: {code, message, data}
        self.assertEqual(body.get('code'), 200)
        data = body.get('data') or {}
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('module'), 'finance')
        self.assertEqual(data.get('version'), '0.1.0')

    def test_ping_is_public(self):
        # No Authorization header — endpoint must still respond 200.
        response = self.client.get('/api/finance/ping')
        self.assertEqual(response.status_code, 200)
