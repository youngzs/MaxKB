# coding=utf-8
"""
    @project: MaxKB
    @file:   workflow_run.py
    @desc:   Read-only list endpoint for WorkflowRun rows (Gate 7 Track B).

    Filterable by target_type / target_id / status. Paginated like the
    other finance list endpoints. Permission: FINANCE_READ so any
    workspace member can see the runtime trail of their own tasks; the
    rows do not contain secrets.
"""
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from finance.models import WorkflowRun

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _to_dict(row: WorkflowRun) -> dict:
    return {
        'id': str(row.id),
        'workspace_id': row.workspace_id,
        'target_type': row.target_type,
        'target_id': str(row.target_id),
        'task_name': row.task_name,
        'celery_task_id': row.celery_task_id,
        'status': row.status,
        'started_at': row.started_at.isoformat() if row.started_at else None,
        'finished_at': row.finished_at.isoformat() if row.finished_at else None,
        'duration_ms': row.duration_ms,
        'error_message': row.error_message or '',
        'payload': row.payload or {},
        'retry_count': row.retry_count,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


class FinanceWorkflowRunListView(APIView):
    """GET /workspace/<wid>/workflow-run?target_type=&target_id=&status=&page=&size="""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List workflow runs'),
        operation_id=_('List workflow runs'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = WorkflowRun.objects.filter(workspace_id=workspace_id)
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
        size = min(_parse_int(request.query_params.get('size'), _DEFAULT_SIZE), _MAX_SIZE)
        total = qs.count()
        offset = (page - 1) * size
        records = [_to_dict(r) for r in qs[offset: offset + size]]
        return result.success(
            result.Page(
                total=total,
                records=records,
                current_page=page,
                page_size=size,
            )
        )
