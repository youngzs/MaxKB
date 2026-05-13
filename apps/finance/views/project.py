# coding=utf-8
"""
    @project: MaxKB
    @file： project.py
    @desc: DRF views for FinanceProject — workspace-scoped CRUD.

    Permission model: every action below is gated on a finance permission
    that is *additionally* scoped to the requested workspace via
    PermissionConstants.FINANCE_*.get_workspace_permission(). The `has_permissions`
    decorator reuses the project-wide RBAC pipeline used by Application/Knowledge.
    USER and WORKSPACE_MANAGE roles fall through as alternative authorizations,
    matching the convention in apps/application/views/application.py.
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
from common.exception.app_exception import AppApiException, NotFound404
from finance.models import FinanceAuditAction, FinanceAuditTargetType, FinanceProject
from finance.serializers.project import (
    FinanceProjectInputSerializer,
    FinanceProjectOutputSerializer,
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


def _build_queryset(workspace_id, query_params):
    qs = FinanceProject.objects.filter(workspace_id=workspace_id, is_deleted=False)
    keyword = (query_params.get('keyword') or '').strip()
    if keyword:
        qs = qs.filter(Q(name__icontains=keyword) | Q(code__icontains=keyword))
    status_filter = (query_params.get('status') or '').strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    project_type = (query_params.get('project_type') or '').strip()
    if project_type:
        qs = qs.filter(project_type=project_type)
    return qs


def _paginate(queryset, query_params):
    page = _parse_int(query_params.get('page'), _DEFAULT_PAGE)
    size = _parse_int(query_params.get('size'), _DEFAULT_SIZE)
    size = min(size, _MAX_SIZE)
    total = queryset.count()
    offset = (page - 1) * size
    records = list(queryset[offset: offset + size])
    return total, page, size, records


class FinanceProjectListView(APIView):
    """Collection endpoint: list (GET) and create (POST)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List finance projects'),
        description=_('List finance projects in a workspace, with keyword and status filters.'),
        operation_id=_('List finance projects'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = _build_queryset(workspace_id, request.query_params)
        total, page, size, records = _paginate(qs, request.query_params)
        serializer = FinanceProjectOutputSerializer(records, many=True)
        return result.success(result.Page(total=total, records=serializer.data,
                                          current_page=page, page_size=size))

    @extend_schema(
        methods=['POST'],
        summary=_('Create finance project'),
        description=_('Create a new finance project in the given workspace.'),
        operation_id=_('Create finance project'),  # type: ignore
        request=FinanceProjectInputSerializer,
        responses=FinanceProjectOutputSerializer,
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.PROJECT)
    def post(self, request: Request, workspace_id):
        body = FinanceProjectInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        code = (payload.get('code') or '').strip()
        if code and FinanceProject.objects.filter(
            workspace_id=workspace_id, code=code, is_deleted=False
        ).exists():
            raise AppApiException(400, _('Project code already exists in this workspace'))
        # knowledge_base_ids may arrive as a list of UUID objects — coerce
        # to strings so JSONField stores a stable, JSON-native shape.
        kb_ids = [str(kid) for kid in payload.get('knowledge_base_ids') or []]
        project = FinanceProject.objects.create(
            workspace_id=workspace_id,
            name=payload['name'],
            code=code,
            project_type=payload['project_type'],
            target_amount=payload.get('target_amount'),
            currency=payload.get('currency') or 'CNY',
            status=payload.get('status') or 'preparing',
            region=payload.get('region') or '',
            industry_code=payload.get('industry_code') or '',
            knowledge_base_ids=kb_ids,
            description=payload.get('description') or '',
            created_by=request.user.id,
        )
        return result.success(FinanceProjectOutputSerializer(project).data)


class FinanceProjectDetailView(APIView):
    """Single-resource endpoint: get, update, soft-delete."""

    authentication_classes = [TokenAuth]

    @staticmethod
    def _get_or_404(workspace_id, pk):
        instance = FinanceProject.objects.filter(
            id=pk, workspace_id=workspace_id, is_deleted=False
        ).first()
        if instance is None:
            raise NotFound404(404, _('Project not found'))
        return instance

    @extend_schema(
        methods=['GET'],
        summary=_('Get finance project'),
        description=_('Get a single finance project by id.'),
        operation_id=_('Get finance project'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = self._get_or_404(workspace_id, pk)
        return result.success(FinanceProjectOutputSerializer(instance).data)

    @extend_schema(
        methods=['PUT'],
        summary=_('Update finance project'),
        description=_('Update an existing finance project.'),
        operation_id=_('Update finance project'),  # type: ignore
        request=FinanceProjectInputSerializer,
        responses=FinanceProjectOutputSerializer,
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.PROJECT)
    def put(self, request: Request, workspace_id, pk):
        instance = self._get_or_404(workspace_id, pk)
        body = FinanceProjectInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        new_code = (payload.get('code') or '').strip()
        if new_code and new_code != instance.code and FinanceProject.objects.filter(
            workspace_id=workspace_id, code=new_code, is_deleted=False
        ).exclude(id=instance.id).exists():
            raise AppApiException(400, _('Project code already exists in this workspace'))
        instance.name = payload['name']
        instance.code = new_code
        instance.project_type = payload['project_type']
        instance.target_amount = payload.get('target_amount')
        instance.currency = payload.get('currency') or instance.currency
        instance.status = payload.get('status') or instance.status
        instance.region = payload.get('region') or ''
        instance.industry_code = payload.get('industry_code') or ''
        instance.knowledge_base_ids = [
            str(kid) for kid in (payload.get('knowledge_base_ids') or [])
        ]
        instance.description = payload.get('description') or ''
        instance.save()
        return result.success(FinanceProjectOutputSerializer(instance).data)

    @extend_schema(
        methods=['DELETE'],
        summary=_('Delete finance project'),
        description=_('Soft-delete a finance project.'),
        operation_id=_('Delete finance project'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.DELETE, target_type=FinanceAuditTargetType.PROJECT)
    def delete(self, request: Request, workspace_id, pk):
        instance = self._get_or_404(workspace_id, pk)
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted', 'updated_at'])
        return result.success({'id': str(instance.id)})
