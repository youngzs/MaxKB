# coding=utf-8
"""
    @project: MaxKB
    @file:   test_healthz.py
    @desc:   Tests for the finance real-health endpoint (Gate 6 Track C / C3).

    Verifies:
      * the route is mounted at /admin/api/finance/healthz and returns 200
      * DB failure flips the overall verdict to 'degraded' but the HTTP
        status remains 200 so monitoring tools can still scrape it.
"""
from __future__ import annotations

from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from finance.views.healthz import FinanceHealthzView


class FinanceHealthzViewTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = FinanceHealthzView.as_view()

    def test_all_ok_returns_overall_ok(self):
        request = self.factory.get('/admin/api/finance/healthz')
        with patch('finance.views.healthz._probe_db', return_value=True), patch(
            'finance.views.healthz._probe_cache', return_value=True
        ):
            response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = response.data.get('data') or {}
        self.assertEqual(data.get('overall'), 'ok')
        self.assertEqual(data.get('db'), 'ok')
        self.assertEqual(data.get('cache'), 'ok')
        self.assertEqual(data.get('module'), 'finance')

    def test_db_failure_yields_degraded_but_still_200(self):
        request = self.factory.get('/admin/api/finance/healthz')
        with patch('finance.views.healthz._probe_db', return_value=False), patch(
            'finance.views.healthz._probe_cache', return_value=True
        ):
            response = self.view(request)
        # Critical: 200 even on degradation so probes don't see "down"
        # when the service is reachable but a dependency is sick.
        self.assertEqual(response.status_code, 200)
        data = response.data.get('data') or {}
        self.assertEqual(data.get('overall'), 'degraded')
        self.assertEqual(data.get('db'), 'fail')

    def test_cache_failure_yields_degraded(self):
        request = self.factory.get('/admin/api/finance/healthz')
        with patch('finance.views.healthz._probe_db', return_value=True), patch(
            'finance.views.healthz._probe_cache', return_value=False
        ):
            response = self.view(request)
        self.assertEqual(response.status_code, 200)
        data = response.data.get('data') or {}
        self.assertEqual(data.get('overall'), 'degraded')
        self.assertEqual(data.get('cache'), 'fail')
