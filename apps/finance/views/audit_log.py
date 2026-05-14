# coding=utf-8
"""
    @project: MaxKB
    @file： audit_log.py
    @desc: Read-only list view for FinanceAuditLog (Gate 5 Track C).

    This is an admin/compliance surface — it is NOT the same as the
    individual-object audit tabs that surface inside each resource's detail
    page. The endpoint is workspace-scoped because finance audit rows
    themselves are workspace-scoped (see FinanceAuditLog.workspace_id);
    cross-workspace audit views would be a system-level concern handled
    elsewhere.

    Permission contract:
        - Reads require either FINANCE_REVIEW (compliance reviewer role)
          OR WORKSPACE_MANAGE (workspace admin). The route is NOT gated on
          plain FINANCE_READ so day-to-day finance staff cannot see who
          read what.
        - There is no write path — the table is append-only via the
          ``audit_log`` decorator + ``log_event`` helper.

    Query parameters (all optional):
        - target_type   one of FinanceAuditTargetType
        - action        one of FinanceAuditAction
        - actor_id      UUID of the actor user
        - target_id     UUID of the audited row
        - date_from     ISO-8601 (inclusive lower bound on created_at)
        - date_to       ISO-8601 (exclusive upper bound on created_at)
        - keyword       substring match on the JSON payload (path field)
        - page, size    pagination
"""
from datetime import datetime

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from finance.models import FinanceAuditAction, FinanceAuditLog, FinanceAuditTargetType
from finance.serializers.audit_log import FinanceAuditLogOutputSerializer

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200

_VALID_TARGET_TYPES = {choice for choice, _label in FinanceAuditTargetType.choices}
_VALID_ACTIONS = {choice for choice, _label in FinanceAuditAction.choices}


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _parse_iso(value) -> datetime | None:
    if not value:
        return None
    try:
        return parse_datetime(str(value))
    except (TypeError, ValueError):
        return None


def _build_queryset(workspace_id, query_params):
    """
    Build a filtered FinanceAuditLog queryset.

    Unknown enum filter values are silently dropped (rather than raising),
    matching the convention used by FinanceProjectListView — the audit page
    is meant to feel forgiving when operators paste partial filters from
    URL bars.
    """
    qs = FinanceAuditLog.objects.filter(workspace_id=workspace_id)

    target_type = (query_params.get('target_type') or '').strip()
    if target_type and target_type in _VALID_TARGET_TYPES:
        qs = qs.filter(target_type=target_type)

    action = (query_params.get('action') or '').strip()
    if action and action in _VALID_ACTIONS:
        qs = qs.filter(action=action)

    actor_id = (query_params.get('actor_id') or '').strip()
    if actor_id:
        # Let an invalid UUID quietly miss rather than 500: ORM will still
        # accept the string for an indexed UUID field on PostgreSQL and
        # simply return no matches.
        qs = qs.filter(actor_id=actor_id)

    target_id = (query_params.get('target_id') or '').strip()
    if target_id:
        qs = qs.filter(target_id=target_id)

    date_from = _parse_iso(query_params.get('date_from'))
    if date_from is not None:
        qs = qs.filter(created_at__gte=date_from)
    date_to = _parse_iso(query_params.get('date_to'))
    if date_to is not None:
        qs = qs.filter(created_at__lt=date_to)

    keyword = (query_params.get('keyword') or '').strip()
    if keyword:
        # PostgreSQL JSONField casts to text for icontains — handy for the
        # path/method snapshot we store. Limit to a sensible cap so a stray
        # keyword doesn't kill the index.
        if len(keyword) <= 128:
            qs = qs.filter(Q(payload__icontains=keyword) | Q(user_agent__icontains=keyword))

    return qs.order_by('-created_at')


def _paginate(queryset, query_params):
    page = _parse_int(query_params.get('page'), _DEFAULT_PAGE)
    size = _parse_int(query_params.get('size'), _DEFAULT_SIZE)
    size = min(size, _MAX_SIZE)
    total = queryset.count()
    offset = (page - 1) * size
    records = list(queryset[offset: offset + size])
    return total, page, size, records


class FinanceAuditLogListView(APIView):
    """
    GET /finance/workspace/<workspace_id>/audit-log

    Lists audit rows for one workspace, newest first, with the filter set
    described in the module docstring. There is intentionally no detail
    view: a single row's ``payload`` is already returned inline and the
    list view is the only read surface clients need.
    """

    authentication_classes = [TokenAuth]

    @has_permissions(
        # OR semantics by default — reviewer permission OR workspace-admin
        # role is sufficient. Audit log is intentionally NOT gated on plain
        # FINANCE_READ so day-to-day finance staff can't observe each
        # other's clicks.
        PermissionConstants.FINANCE_REVIEW.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = _build_queryset(workspace_id, request.query_params)
        total, page, size, records = _paginate(qs, request.query_params)
        serializer = FinanceAuditLogOutputSerializer(records, many=True)
        return result.success(result.Page(
            total=total,
            records=serializer.data,
            current_page=page,
            page_size=size,
        ))
