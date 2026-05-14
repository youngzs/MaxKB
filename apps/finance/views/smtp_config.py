# coding=utf-8
"""
    @project: MaxKB
    @file： smtp_config.py
    @desc: SmtpConfig REST endpoints (Gate 5 Track B).

    Permission model:
      * list/detail   → FINANCE_READ
      * create/update/delete/test → FINANCE_SEND
    Workspace-manage roles fall through everywhere.
"""
from django.db import transaction
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
from finance.models import FinanceAuditAction, FinanceAuditTargetType, SmtpConfig
from finance.serializers.smtp_config import (
    SmtpConfigCreateSerializer,
    SmtpConfigOutputSerializer,
    SmtpConfigTestSerializer,
    SmtpConfigUpdateSerializer,
)
from finance.service.audit import audit_log
from finance.service.email_sender import send_test_email
from finance.service.encryption import encrypt_secret

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


def _get_or_404(workspace_id, pk) -> SmtpConfig:
    instance = SmtpConfig.objects.filter(
        id=pk, workspace_id=workspace_id, is_deleted=False
    ).first()
    if instance is None:
        raise NotFound404(404, _('SMTP config not found'))
    return instance


def _ensure_single_default(workspace_id, *, current_id=None) -> None:
    """
    The DB has a partial unique constraint, but Postgres serializes that as
    a constraint violation. Pre-clear the prior default at the ORM layer so
    we surface a clean operation rather than a 500.
    """
    qs = SmtpConfig.objects.filter(
        workspace_id=workspace_id, is_default=True, is_deleted=False
    )
    if current_id is not None:
        qs = qs.exclude(id=current_id)
    qs.update(is_default=False)


class SmtpConfigListView(APIView):
    """GET (list, paginated) + POST (create)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List SMTP configs'),
        operation_id=_('List SMTP configs'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        qs = SmtpConfig.objects.filter(workspace_id=workspace_id, is_deleted=False)
        keyword = (request.query_params.get('keyword') or '').strip()
        if keyword:
            qs = qs.filter(
                Q(name__icontains=keyword) | Q(from_email__icontains=keyword)
            )
        total, page, size, records = _paginate(qs, request.query_params)
        return result.success(
            result.Page(
                total=total,
                records=SmtpConfigOutputSerializer(records, many=True).data,
                current_page=page,
                page_size=size,
            )
        )

    @extend_schema(
        methods=['POST'],
        summary=_('Create SMTP config'),
        request=SmtpConfigCreateSerializer,
        responses=SmtpConfigOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Create SMTP config'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.CREATE, target_type=FinanceAuditTargetType.OTHER)
    def post(self, request: Request, workspace_id):
        body = SmtpConfigCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        with transaction.atomic():
            if payload.get('is_default'):
                _ensure_single_default(workspace_id)
            try:
                ciphertext = encrypt_secret(payload['password'])
            except Exception as e:  # noqa: BLE001
                raise AppApiException(400, _('Failed to encrypt password')) from e
            instance = SmtpConfig.objects.create(
                workspace_id=workspace_id,
                name=payload['name'],
                host=payload['host'],
                port=payload['port'],
                username=payload['username'],
                password_encrypted=ciphertext,
                from_email=payload['from_email'],
                from_name=payload.get('from_name') or '',
                use_tls=payload.get('use_tls', True),
                use_ssl=payload.get('use_ssl', False),
                is_default=payload.get('is_default', False),
                created_by=request.user.id,
            )
        return result.success(SmtpConfigOutputSerializer(instance).data)


class SmtpConfigDetailView(APIView):
    """GET (detail) + PUT (partial update) + DELETE (soft)."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Get SMTP config'),
        operation_id=_('Get SMTP config'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        return result.success(SmtpConfigOutputSerializer(instance).data)

    @extend_schema(
        methods=['PUT'],
        summary=_('Update SMTP config'),
        request=SmtpConfigUpdateSerializer,
        responses=SmtpConfigOutputSerializer,
        tags=[_('Finance')],  # type: ignore
        operation_id=_('Update SMTP config'),  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.OTHER)
    def put(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        body = SmtpConfigUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        updates: list[str] = []
        with transaction.atomic():
            for field in (
                'name', 'host', 'port', 'username',
                'from_email', 'from_name', 'use_tls', 'use_ssl',
            ):
                if field in payload:
                    setattr(instance, field, payload[field])
                    updates.append(field)
            # Password: blank/omitted → keep existing.
            new_password = payload.get('password')
            if new_password:
                try:
                    instance.password_encrypted = encrypt_secret(new_password)
                except Exception as e:  # noqa: BLE001
                    raise AppApiException(
                        400, _('Failed to encrypt password')
                    ) from e
                updates.append('password_encrypted')
            if 'is_default' in payload:
                instance.is_default = payload['is_default']
                updates.append('is_default')
                if payload['is_default']:
                    _ensure_single_default(workspace_id, current_id=instance.id)
            if updates:
                updates.append('updated_at')
                instance.save(update_fields=updates)
        return result.success(SmtpConfigOutputSerializer(instance).data)

    @extend_schema(
        methods=['DELETE'],
        summary=_('Delete SMTP config'),
        operation_id=_('Delete SMTP config'),  # type: ignore
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
        # Strip the default flag so the partial unique constraint releases
        # the workspace slot for a new default.
        instance.is_default = False
        instance.save(update_fields=['is_deleted', 'is_default', 'updated_at'])
        return result.success({'id': str(instance.id)})


class SmtpConfigTestView(APIView):
    """POST /<pk>/test — send a probe email to verify credentials."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Send SMTP test email'),
        request=SmtpConfigTestSerializer,
        operation_id=_('Send SMTP test email'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def post(self, request: Request, workspace_id, pk):
        instance = _get_or_404(workspace_id, pk)
        body = SmtpConfigTestSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        payload = body.validated_data
        outcome = send_test_email(
            smtp_config=instance, to_address=payload['to_address']
        )
        return result.success(outcome)
