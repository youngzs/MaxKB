# coding=utf-8
"""
    @project: MaxKB
    @file： email_template.py
    @desc: EmailTemplate REST endpoints (Gate 5 Track B).

    Permission model:
      * list/detail   → FINANCE_READ
      * create/update/delete → FINANCE_SEND
    Workspace-manage roles fall through everywhere.
"""
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.exception.app_exception import NotFound404
from finance.models import EmailTemplate, FinanceAuditAction, FinanceAuditTargetType
from finance.serializers.email_template import (
    EmailTemplateCreateSerializer,
    EmailTemplateOutputSerializer,
    EmailTemplateUpdateSerializer,
)
from finance.service.audit import audit_log

_DEFAULT_PAGE = 1
_DEFAULT_SIZE = 20
_MAX_SIZE = 200


def _parse_int(value, default):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _paginate(queryset, query_params):
    page = _parse_int(query_params.get('page'), _DEFAULT_PAGE)
    size = min(_parse_int(query_params.get('size'), _DEFAULT_SIZE), _MAX_SIZE)
    total = queryset.count()
    offset = (page - 1) * size
    records = list(queryset[offset: offset + size])
    return total, page, size, records


def _get_or_404(workspace_id, pk) -> EmailTemplate:
    instance = EmailTemplate.objects.filter(
        id=pk, workspace_id=workspace_id, is_deleted=False
    ).first()
    if instance is None:
        raise NotFound404(404, _('Email template not found'))
    return instance


class EmailTemplateListView(APIView):
    """GET (list, paginated) + POST (create)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List email templates'),
        operation_id=_('List email templates'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = EmailTemplate.objects.filter(
            workspace_id=workspace_id, is_deleted=False
        )
        scenario = (request.query_params.get('scenario') or '').strip()
        if scenario:
            qs = qs.filter(scenario=scenario)
        keyword = (request.query_params.get('keyword') or '').strip()
        if keyword:
            qs = qs.filter(Q(name__icontains=keyword) | Q(subject__icontains=keyword))
        total, page, size, records = _paginate(qs, request.query_params)
        return result.success(
            result.Page(
                total=total,
                records=EmailTemplateOutputSerializer(records, many=True).data,
                current_page=page,
                page_size=size,
            )
        )

    @extend_schema(
        methods=['POST'],
        summary=_('Create email template'),
        request=EmailTemplateCreateSerializer,
        responses=EmailTemplateOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Create email template'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.OTHER)
    def post(self, request: Request, workspace_id):
        body = EmailTemplateCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        instance = EmailTemplate.objects.create(
            workspace_id=workspace_id,
            name=payload['name'],
            subject=payload['subject'],
            body_text=payload['body_text'],
            body_html=payload.get('body_html') or '',
            scenario=payload.get('scenario'),
            is_active=payload.get('is_active', True),
            created_by=request.user.id,
        )
        return result.success(EmailTemplateOutputSerializer(instance).data)


class EmailTemplateDetailView(APIView):
    """GET (detail) + PUT (partial update) + DELETE (soft)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Get email template'),
        operation_id=_('Get email template'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        return result.success(EmailTemplateOutputSerializer(instance).data)

    @extend_schema(
        methods=['PUT'],
        summary=_('Update email template'),
        request=EmailTemplateUpdateSerializer,
        responses=EmailTemplateOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Update email template'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.OTHER)
    def put(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        body = EmailTemplateUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        updates: list[str] = []
        for field in (
            'name', 'subject', 'body_text', 'body_html', 'scenario', 'is_active',
        ):
            if field in payload:
                setattr(instance, field, payload[field])
                updates.append(field)
        if updates:
            updates.append('updated_at')
            instance.save(update_fields=updates)
        return result.success(EmailTemplateOutputSerializer(instance).data)

    @extend_schema(
        methods=['DELETE'],
        summary=_('Delete email template'),
        operation_id=_('Delete email template'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DELETE, target_type=FinanceAuditTargetType.OTHER)
    def delete(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        return result.success({'id': str(instance.id)})
