# coding=utf-8
"""
    @project: MaxKB
    @file： healthz.py
    @desc: Real health endpoint for the finance module (Gate 6 Track C / C3).

    Unlike ``/ping`` (which proves only that the URL is mounted), this
    endpoint round-trips the database and cache to surface degraded
    states. Always returns HTTP 200 — monitoring systems use the JSON
    body's ``overall`` field to distinguish "service running, but
    something downstream is sick" from "service unreachable" (which
    will give them a transport-level error, not a 200).
"""
from __future__ import annotations

from django.core.cache import cache
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result

FINANCE_MODULE_VERSION = '0.2.0'


def _probe_db() -> bool:
    """Touch the finance DB connection. Returns True on a clean round-trip."""
    try:
        # Local import: keeps this module importable even if the app
        # registry hasn't finished loading the finance models yet.
        from finance.models import FinanceProject

        # `.exists()` issues a `SELECT EXISTS (...)` — it doesn't need
        # any rows; we just want the round-trip and the conn dial.
        FinanceProject.objects.using('default').exists()
        return True
    except Exception:  # noqa: BLE001 — degraded, not exceptional
        return False


_CACHE_PROBE_KEY = 'finance:healthz:probe'
_CACHE_PROBE_TTL = 5  # seconds — short, so this never lingers in Redis


def _probe_cache() -> bool:
    """Round-trip the default Django cache. Returns True iff get==set."""
    try:
        cache.set(_CACHE_PROBE_KEY, '1', _CACHE_PROBE_TTL)
        return cache.get(_CACHE_PROBE_KEY) == '1'
    except Exception:  # noqa: BLE001
        return False


class FinanceHealthzView(APIView):
    """
    GET /admin/api/finance/healthz

    Real health check: DB + cache probes. Always 200 (with
    ``overall: 'degraded'`` when any check fails) so monitoring tools
    can distinguish degraded-but-running from unreachable.

    Skipped intentionally:
      * LLM provider availability — we don't want to spend a token on
        every healthz hit, and providers have their own reachability
        checks elsewhere.
      * OSS write probes — the bytea store is co-located with the DB
        check, so the DB probe is sufficient signal.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request: Request):
        db_ok = _probe_db()
        cache_ok = _probe_cache()
        overall = 'ok' if (db_ok and cache_ok) else 'degraded'
        return result.success({
            'db': 'ok' if db_ok else 'fail',
            'cache': 'ok' if cache_ok else 'fail',
            'overall': overall,
            'module': 'finance',
            'version': FINANCE_MODULE_VERSION,
        })
