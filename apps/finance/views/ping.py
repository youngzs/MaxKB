# coding=utf-8
"""
    @project: MaxKB
    @file： ping.py
    @desc: Health-check endpoint for the finance module.
"""
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result

FINANCE_MODULE_VERSION = '0.1.0'


class FinancePingView(APIView):
    """
    Public health-check probe for the finance workspace.

    No authentication is required — this is intentionally an open endpoint
    so operators can verify the module is mounted and reachable.
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        methods=['GET'],
        summary=_('Finance health check'),
        description=_('Returns a static health-check payload for the finance module.'),
        operation_id=_('Finance health check'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    def get(self, request: Request):
        return result.success({
            'status': 'ok',
            'module': 'finance',
            'version': FINANCE_MODULE_VERSION,
        })
