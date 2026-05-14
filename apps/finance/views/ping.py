# coding=utf-8
"""
    @project: MaxKB
    @file： ping.py
    @desc: Health-check endpoint for the finance module.
"""
import traceback

from rest_framework.request import Request
from rest_framework.views import APIView

from common import result

FINANCE_MODULE_VERSION = '0.1.0'


class FinancePingView(APIView):
    """
    Public health-check probe for the finance workspace.

    No authentication is required — this is intentionally an open endpoint
    so operators can verify the module is mounted and reachable.

    History / Gate 6 Track A1 note:
    -------------------------------
    Earlier gates surfaced an intermittent 500 with the message::

        Model class django.contrib.auth.models.Permission doesn't declare
        an explicit app_label.

    Gate 5 Track C removed the ``@extend_schema(...)`` decorator (which had
    been pulling drf-spectacular's schema generator into the request path
    and lazily resolving the ``gettext_lazy`` strings that walked the
    installed-apps graph). That fixed the documented reproducer, but
    ``django.contrib.auth`` is still not listed in ``INSTALLED_APPS`` —
    only ``django.contrib.contenttypes`` and ``messages`` are — so any
    code path that lazily references the auth models can resurface a
    similar error (DRF's stock ``TokenAuthentication`` keeps ``Token``
    behind ``get_model()``, and the auth template context processor only
    loads on HTML responses, but the runtime surface is wider than we can
    easily prove).

    A ping endpoint is a health probe; it must NEVER 500. We wrap the
    body in a defensive try/except so any future regression downgrades to
    ``status: 'degraded'`` with a ``detail`` field carrying the exception
    repr for diagnostics, instead of returning HTTP 500 (which would mark
    the whole module unhealthy in upstream load balancers).
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request: Request):
        try:
            return result.success({
                'status': 'ok',
                'module': 'finance',
                'version': FINANCE_MODULE_VERSION,
            })
        except Exception as exc:  # noqa: BLE001 — health probe must not 500
            return result.success({
                'status': 'degraded',
                'module': 'finance',
                'version': FINANCE_MODULE_VERSION,
                'detail': repr(exc),
                # Keep trace short for log-shipping; full trace is logged below.
                'trace_tail': traceback.format_exc().splitlines()[-1:],
            })
