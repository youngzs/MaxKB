# coding=utf-8
"""
    @project: MaxKB
    @file： email_send_log.py
    @desc: EmailSendLog read-only list endpoint (Gate 5 Track B).

    Workspace-scoped, paginated, filterable by `target_type`/`target_id`/
    `status`. This is the auditing surface — there is no PUT/DELETE.
"""
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from finance.models import EmailSendLog
from finance.serializers.email_send_log import EmailSendLogOutputSerializer

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


class EmailSendLogListView(APIView):
    """GET (list, paginated, filterable)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List email send logs'),
        operation_id=_('List email send logs'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = EmailSendLog.objects.filter(workspace_id=workspace_id)
        target_type = (request.query_params.get('target_type') or '').strip()
        if target_type:
            qs = qs.filter(target_type=target_type)
        target_id = (request.query_params.get('target_id') or '').strip()
        if target_id:
            qs = qs.filter(target_id=target_id)
        status = (request.query_params.get('status') or '').strip()
        if status:
            qs = qs.filter(status=status)

        page = _parse_int(request.query_params.get('page'), _DEFAULT_PAGE)
        size = min(
            _parse_int(request.query_params.get('size'), _DEFAULT_SIZE), _MAX_SIZE
        )
        total = qs.count()
        offset = (page - 1) * size
        records = list(qs[offset: offset + size])
        return result.success(
            result.Page(
                total=total,
                records=EmailSendLogOutputSerializer(records, many=True).data,
                current_page=page,
                page_size=size,
            )
        )
