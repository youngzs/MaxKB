# coding=utf-8
"""
    @project: MaxKB
    @file:   document_sensitivity.py
    @desc:   Document sensitivity PATCH endpoint (Gate 6 Track A3).

    Why this lives in ``finance`` rather than ``knowledge``:
    -------------------------------------------------------
    The sensitivity classification was added to ``knowledge.Document`` in
    Gate 2 Track C, but the *policy* (which roles may change it, what
    workflow it gates) belongs to the finance/compliance domain. Materials
    packaging, send-eligibility checks, and the audit trail are all
    finance-owned, so the write surface lives here. A future refactor
    could split this out cleanly — for now the boundary is "knowledge
    stores the value, finance owns the lifecycle".

    Contract:
        PATCH /finance/workspace/<workspace_id>/document-sensitivity/<document_id>
        Body:  {"sensitivity_level": "public"|"internal"|"confidential"|"secret"}
        Perms: FINANCE_TEMPLATE_MANAGE  OR  ADMIN/WORKSPACE_MANAGE role
        Audit: every successful update writes a FinanceAuditLog row
               (action=UPDATE, target_type=OTHER, target_id=document.id)

    Workspace scoping is enforced via the document's owning Knowledge
    (``Document.knowledge.workspace_id``) — a document whose knowledge
    lives in a different workspace returns 404, never 403, to avoid
    leaking the existence of cross-workspace rows.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.constants.sensitivity_constants import SensitivityLevel
from common.exception.app_exception import AppApiException, NotFound404
from finance.models import FinanceAuditAction, FinanceAuditTargetType
from finance.service.audit import audit_log

_VALID_LEVELS = {choice for choice, _label in SensitivityLevel.choices}


class DocumentSensitivityView(APIView):
    """
    PATCH-only endpoint for updating a document's sensitivity level.

    There is intentionally no GET — the value is already returned by
    the knowledge document detail endpoint; duplicating the read path
    here would only invite drift.
    """

    authentication_classes = [TokenAuth]

    @has_permissions(
        PermissionConstants.FINANCE_TEMPLATE_MANAGE.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(
        action=FinanceAuditAction.UPDATE,
        target_type=FinanceAuditTargetType.OTHER,
    )
    def patch(self, request: Request, workspace_id, document_id):
        # Local import: keeps the finance views module importable even
        # when the knowledge app's model graph isn't fully loaded
        # (mirrors the pattern used in finance/service/zip_packager.py).
        from knowledge.models import Document

        body = request.data if isinstance(request.data, dict) else {}
        new_level = (body.get('sensitivity_level') or '').strip()
        if not new_level:
            raise AppApiException(400, _('sensitivity_level is required'))
        if new_level not in _VALID_LEVELS:
            raise AppApiException(
                400,
                _('Invalid sensitivity_level; expected one of: %(valid)s') % {
                    'valid': ', '.join(sorted(_VALID_LEVELS)),
                },
            )

        # Workspace check is via the owning Knowledge — a 404 here covers
        # both "no such document" and "document in a different workspace"
        # so we don't leak cross-workspace existence.
        try:
            document = Document.objects.select_related('knowledge').get(id=document_id)
        except Document.DoesNotExist:
            raise NotFound404(404, _('Document not found'))

        if str(document.knowledge.workspace_id) != str(workspace_id):
            raise NotFound404(404, _('Document not found'))

        old_level = document.sensitivity_level
        if old_level == new_level:
            # Idempotent no-op — still return 200 with the current value so
            # clients can blind-PATCH without checking first.
            return result.success({
                'id': str(document.id),
                'sensitivity_level': document.sensitivity_level,
                'previous_sensitivity_level': old_level,
                'changed': False,
            })

        document.sensitivity_level = new_level
        document.save(update_fields=['sensitivity_level'])

        return result.success({
            'id': str(document.id),
            'sensitivity_level': document.sensitivity_level,
            'previous_sensitivity_level': old_level,
            'changed': True,
        })
