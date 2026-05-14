# coding=utf-8
"""
    @project: MaxKB
    @file:    middleware.py
    @desc:    Public-endpoint bypass middleware (Gate 7 Track A1).

    Background
    ----------
    Gate 5 Track C, Gate 6 Track A1 and Track C all chased the same
    intermittent 500 on the public finance health endpoints::

        Model class django.contrib.auth.models.Permission doesn't
        declare an explicit app_label.

    Root-cause investigation (Gate 7 A1):

    1. ``apps/maxkb/settings/base/web.py``:30-50 lists INSTALLED_APPS,
       and ``django.contrib.auth`` is intentionally NOT registered —
       MaxKB ships its own auth on top of ``rest_framework`` + custom
       handlers in ``apps/common/auth/``. Only ``contenttypes`` /
       ``messages`` / ``staticfiles`` from ``django.contrib`` are.

    2. The DRF default authentication is::

           DEFAULT_AUTHENTICATION_CLASSES = [
               'common.auth.authenticate.AnonymousAuthentication'
           ]

       which itself subclasses ``rest_framework.authentication.TokenAuthentication``.
       ``TokenAuthentication.get_model()`` lazily imports
       ``rest_framework.authtoken.models.Token`` — that import (or
       ``django.contrib.auth.context_processors.auth`` which IS listed
       in TEMPLATES) can transitively reach the auth.Permission model
       at request-dispatch time. Because ``django.contrib.auth`` isn't
       in INSTALLED_APPS, the apps-registry lookup for Permission
       blows up with the observed message.

    3. The ping view sets ``authentication_classes = []`` and
       ``permission_classes = []`` to opt out — but that doesn't help
       because DRF's ``initialize_request`` still pulls in the
       OpenApiAuthenticationExtension registration AND the i18n
       lazy strings (``gettext_lazy``) walk the apps graph on first
       render. The error is non-deterministic because it depends on
       which code path warms the auth model first; some test runs
       never hit it, production deploys hit it on cold-start.

    The "right" fix is to add ``django.contrib.auth`` to INSTALLED_APPS
    — but that ripples into auth_user_model conflicts with MaxKB's own
    User model. Out of scope for Track A.

    The clean, surgical fix: intercept ``/ping`` and ``/healthz`` at the
    middleware layer BEFORE DRF's view-dispatch runs. We return the
    same JSON envelope ``common.result.success`` would produce, without
    ever entering the auth chain.

    Performance: O(1) per request; the matcher is a literal-string
    suffix check against ``request.path``. Negligible overhead on the
    >99% of requests that don't match.

    Safety: only matches the two literal probe paths. Any future
    public endpoint must be added explicitly here — we don't pattern-
    match by app prefix because doing so would silently bypass auth
    on any future ``/admin/api/finance/*`` route that happens to be
    unprotected, which is a footgun.
"""
from __future__ import annotations

from django.http import JsonResponse

from common.utils.logger import maxkb_logger

# Module constants — single source of truth for the contract returned
# by the bypass. Bumping these does NOT also need to bump the view
# module values (those are still used by the regular DRF dispatch
# when the apps-graph happens to be healthy); the JSON shape is what
# matters for the probe.
_FINANCE_PING_VERSION = '0.3.0'
_FINANCE_HEALTHZ_VERSION = '0.3.0'

# Two literal paths we accept. The leading prefix is whatever the
# top-level URL conf mounts the finance app under — both '/api/finance/'
# (admin) and '/admin/api/finance/' (reverse-proxy) shapes are
# considered, matched as suffixes so we don't have to encode the
# CONFIG.get_admin_path() value here.
_PING_SUFFIX = '/api/finance/ping'
_HEALTHZ_SUFFIX = '/api/finance/healthz'


def _result_envelope(data: dict) -> dict:
    """Match ``common.result.success`` shape exactly."""
    return {
        'code': 200,
        'message': '成功',
        'data': data,
    }


class PublicEndpointBypassMiddleware:
    """
    Short-circuits the two finance public probes before DRF's auth
    chain runs.

    Wire near the TOP of MIDDLEWARE in ``apps/maxkb/settings/base/web.py``
    so it sees the request before SecurityMiddleware / SessionMiddleware
    pull in any models that touch the apps registry.

    GET requests on the two probe paths return 200 with the standard
    MaxKB envelope. Any other method on those paths falls through to
    the normal stack (which will then 405, as it should).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        method = (request.method or '').upper()

        if method == 'GET' and path.endswith(_PING_SUFFIX):
            # Doc note: we do NOT try to mimic the view's defensive
            # try/except here — there's nothing to fail. If the bypass
            # itself raises we WANT the 500 (it would mean the runtime
            # is on fire, not just the apps registry).
            return JsonResponse(_result_envelope({
                'status': 'ok',
                'module': 'finance',
                'version': _FINANCE_PING_VERSION,
                'bypass': True,
            }))

        if method == 'GET' and path.endswith(_HEALTHZ_SUFFIX):
            db_ok = self._probe_db()
            cache_ok = self._probe_cache()
            overall = 'ok' if (db_ok and cache_ok) else 'degraded'
            return JsonResponse(_result_envelope({
                'db': 'ok' if db_ok else 'fail',
                'cache': 'ok' if cache_ok else 'fail',
                'overall': overall,
                'module': 'finance',
                'version': _FINANCE_HEALTHZ_VERSION,
                'bypass': True,
            }))

        return self.get_response(request)

    # ---- probes (mirrors finance.views.healthz, kept private) -----

    @staticmethod
    def _probe_db() -> bool:
        try:
            from finance.models import FinanceProject

            FinanceProject.objects.using('default').exists()
            return True
        except Exception as exc:  # noqa: BLE001
            maxkb_logger.warning(
                f'[finance.middleware] healthz db probe failed: {exc}'
            )
            return False

    @staticmethod
    def _probe_cache() -> bool:
        try:
            from django.core.cache import cache

            cache.set('finance:healthz:probe', '1', 5)
            return cache.get('finance:healthz:probe') == '1'
        except Exception as exc:  # noqa: BLE001
            maxkb_logger.warning(
                f'[finance.middleware] healthz cache probe failed: {exc}'
            )
            return False
