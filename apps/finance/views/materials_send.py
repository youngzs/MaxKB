# coding=utf-8
"""
    @project: MaxKB
    @file： materials_send.py
    @desc: MaterialsTaskSendView — closes the materials workflow with an
    outbound email (Gate 5 Track B).

    State guard: only `approved` tasks may be sent. The send pipeline
    itself audits via `finance.service.email_sender` (writes EmailSendLog
    and FinanceAuditLog row with `action=SEND`).
"""
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.exception.app_exception import AppApiException, NotFound404
from finance.models import MaterialsTask, MaterialsTaskStatus
from finance.serializers.email_send_log import (
    EmailSendLogOutputSerializer,
    MaterialsTaskSendSerializer,
)
from finance.service.audit import _get_ip, _get_ua, _safe_request_snapshot
from finance.service.email_sender import send_materials_task_email


class MaterialsTaskSendView(APIView):
    """POST /materials-task/<pk>/send — deliver the materials zip by email."""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Send materials task email'),
        request=MaterialsTaskSendSerializer,
        responses=EmailSendLogOutputSerializer,
        operation_id=_('Send materials task email'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_SEND.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def post(self, request: Request, workspace_id, pk):
        # Load + state-gate the task BEFORE handing off to the sender. The
        # sender will also re-load it, but doing the guard here lets us
        # return a clean 400 without writing a noisy EmailSendLog row.
        task = MaterialsTask.objects.filter(
            id=pk, workspace_id=workspace_id, is_deleted=False
        ).first()
        if task is None:
            raise NotFound404(404, _('Materials task not found'))
        if task.status != MaterialsTaskStatus.APPROVED:
            raise AppApiException(
                400, _('Only approved materials tasks can be sent')
            )

        body = MaterialsTaskSendSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        outcome = send_materials_task_email(
            task_id=task.id,
            workspace_id=workspace_id,
            smtp_config_id=payload['smtp_config_id'],
            email_template_id=payload['email_template_id'],
            to_addresses=payload['to_addresses'],
            cc_addresses=payload.get('cc_addresses') or [],
            extra_context=payload.get('extra_context') or {},
            attach_zip=payload.get('attach_zip', True),
            sent_by=request.user.id,
            request_snapshot=_safe_request_snapshot(request),
            ip=_get_ip(request),
            user_agent=_get_ua(request),
        )
        # Pull the just-written log row for serialization back to the UI.
        from finance.models import EmailSendLog
        log = EmailSendLog.objects.filter(id=outcome['log_id']).first()
        if log is None:
            # Shouldn't happen — sender always writes a row first.
            return result.success(outcome)
        return result.success(EmailSendLogOutputSerializer(log).data)
