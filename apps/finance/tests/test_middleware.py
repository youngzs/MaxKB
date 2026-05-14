# coding=utf-8
"""
    @project: MaxKB
    @file:    test_middleware.py
    @desc:    Unit tests for the public-endpoint bypass middleware
              (Gate 7 Track A1).

    These tests use Django's RequestFactory to construct fake requests
    and call the middleware directly, so they avoid:
      - the DRF auth chain (the whole reason the middleware exists)
      - the database (we stub the model probe via monkeypatching)
      - the cache backend (same — stub)

    Coverage goals:
      - GET on /ping suffix returns 200 + standard envelope
      - GET on /healthz suffix returns 200 + db/cache booleans
      - non-GET on a probe path falls through (returns whatever the
        downstream handler returns)
      - non-probe path is passed through untouched
      - The middleware never raises, even when probes fail
"""
import json

from django.test import SimpleTestCase
from django.test import RequestFactory

from finance.middleware import PublicEndpointBypassMiddleware


def _make_app(response_payload=b'downstream'):
    """Return a fake ``get_response`` callable that returns a marker
    response — letting us tell whether the middleware short-circuited
    or fell through to the rest of the stack."""

    def _app(request):
        # Return a plain bytes payload distinct from the bypass JSON
        # so the tests can detect fall-through.
        from django.http import HttpResponse
        return HttpResponse(response_payload, content_type='text/plain')

    return _app


class BypassPingTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_ping_short_circuits(self):
        mw = PublicEndpointBypassMiddleware(_make_app())
        request = self.factory.get('/api/finance/ping')
        response = mw(request)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode('utf-8'))
        self.assertEqual(body.get('code'), 200)
        data = body.get('data') or {}
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('module'), 'finance')
        self.assertIn('version', data)
        self.assertTrue(data.get('bypass'))

    def test_admin_prefixed_ping_also_short_circuits(self):
        # Some reverse-proxy deployments mount under /admin/api/finance.
        # Suffix matching handles both.
        mw = PublicEndpointBypassMiddleware(_make_app())
        request = self.factory.get('/admin/api/finance/ping')
        response = mw(request)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content.decode('utf-8'))
        self.assertEqual(body.get('code'), 200)

    def test_post_ping_falls_through(self):
        # POST is not a probe method; let the normal stack 405 it.
        mw = PublicEndpointBypassMiddleware(_make_app(b'downstream-405'))
        request = self.factory.post('/api/finance/ping')
        response = mw(request)
        self.assertEqual(response.content, b'downstream-405')


class BypassHealthzTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _patch_probes(self, db_result, cache_result):
        # Patch BOTH staticmethods on the class so neither probe touches
        # the real DB/cache during the unit test.
        PublicEndpointBypassMiddleware._probe_db = staticmethod(lambda: db_result)
        PublicEndpointBypassMiddleware._probe_cache = staticmethod(lambda: cache_result)

    def tearDown(self):
        # Restore class defaults by reloading the middleware module.
        from importlib import reload
        from finance import middleware as _m
        reload(_m)

    def test_get_healthz_healthy(self):
        self._patch_probes(True, True)
        mw = PublicEndpointBypassMiddleware(_make_app())
        request = self.factory.get('/api/finance/healthz')
        response = mw(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content.decode('utf-8'))['data']
        self.assertEqual(data['overall'], 'ok')
        self.assertEqual(data['db'], 'ok')
        self.assertEqual(data['cache'], 'ok')

    def test_get_healthz_db_down(self):
        self._patch_probes(False, True)
        mw = PublicEndpointBypassMiddleware(_make_app())
        request = self.factory.get('/api/finance/healthz')
        response = mw(request)
        data = json.loads(response.content.decode('utf-8'))['data']
        self.assertEqual(data['overall'], 'degraded')
        self.assertEqual(data['db'], 'fail')


class BypassPassThroughTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_unrelated_path_passes_through(self):
        mw = PublicEndpointBypassMiddleware(_make_app(b'normal-response'))
        request = self.factory.get('/api/finance/workspace/default/project')
        response = mw(request)
        self.assertEqual(response.content, b'normal-response')

    def test_root_passes_through(self):
        mw = PublicEndpointBypassMiddleware(_make_app(b'root-response'))
        request = self.factory.get('/')
        response = mw(request)
        self.assertEqual(response.content, b'root-response')
