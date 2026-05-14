# coding=utf-8
"""
    @project: MaxKB
    @file： ping.py
    @desc: Health-check endpoint for the finance module.
"""
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result

FINANCE_MODULE_VERSION = '0.1.0'


class FinancePingView(APIView):
    """
    Public health-check probe for the finance workspace.

    No authentication is required — this is intentionally an open endpoint
    so operators can verify the module is mounted and reachable.

    Note (Gate 5 Track C): the previous version used ``@extend_schema(...)``
    with ``gettext_lazy`` strings for the OpenAPI metadata. At request time
    drf-spectacular's schema introspection eagerly resolved the lazy strings
    and walked the installed-apps graph, which in turn tried to load
    ``django.contrib.auth.models.Permission`` before its app was registered
    — surfacing as a 500 "doesn't declare an explicit app_label" error on
    the otherwise-trivial ping route. Removing the decorator keeps the
    endpoint dependency-light; the docstring still serves as the API
    description for casual schema consumers.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request: Request):
        return result.success({
            'status': 'ok',
            'module': 'finance',
            'version': FINANCE_MODULE_VERSION,
        })
