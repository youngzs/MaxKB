# coding=utf-8
"""
    @project: MaxKB
    @file:    system_info.py
    @desc:    Admin-only system diagnostics endpoint for the finance
              workspace (Gate 7 Track A4).

    Returns a single JSON envelope summarising the deployed module
    state — version, preset workflow installation status, configuration
    counts, materials-task histogram, recent error rows, AI model
    availability, and major dependency versions.

    Surface intentions:
      - support operators triaging "what's wrong with this workspace?"
        without needing shell access
      - keep zero PII / payload data in the response (audit-log entries
        return only their action+target+timestamp; no payload)
      - never raise — diagnostics endpoints must be exactly as robust
        as healthz: an individual probe failure surfaces as null/skip
        in its field, not a 500

    Permission contract:
      - ADMIN role only. Workspace managers do NOT get this surface:
        cross-workspace dep versions and global model-configured state
        are tenant-leaking by design, so we gate on the system-level
        ADMIN role rather than the per-workspace manager role.
"""
from __future__ import annotations

from importlib import metadata as _metadata
from typing import Any

from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import RoleConstants
from common.utils.logger import maxkb_logger

# Pinned in finance.views.ping / .healthz too — keep in sync there
# (single source of truth would be nicer but the bypass middleware
# also hard-codes a version; that's deliberate so a runtime crash in
# the finance app doesn't change what the probe returns).
FINANCE_MODULE_VERSION = '0.3.0'

# Sensitivity levels we expect to see on finance-scoped documents.
# Falls back to the SensitivityLevel TextChoices values at runtime;
# pinning the list here is just for the response key order.
_SENSITIVITY_ORDER = ('public', 'internal', 'confidential', 'secret')

# Materials task statuses we report — covers the full state machine
# enumerated in finance.models.materials_task.MaterialsTaskStatus.
_MATERIALS_STATUSES = (
    'draft', 'parsing', 'matching', 'pending_review',
    'approved', 'sent', 'rejected', 'failed',
)

# Major dependency versions we surface. Empty string when the package
# isn't importable (some optional deps are platform-conditional in
# pyproject.toml — torch on macOS for example).
_DEPS_TO_REPORT = (
    'docxtpl',
    'mammoth',
    'python-docx',
    'openpyxl',
    'jinja2',
    'pdfplumber',
    'celery',
    'django',
    'djangorestframework',
)


def _safe_count(qs) -> int:
    try:
        return int(qs.count())
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.system_info] count probe failed: {exc}')
        return -1


def _dep_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in _DEPS_TO_REPORT:
        try:
            out[name] = _metadata.version(name)
        except Exception:  # noqa: BLE001
            # Not installed (or not visible to importlib.metadata in
            # this venv layout). Keep the key so the operator sees
            # which deps were probed.
            out[name] = ''
    return out


def _installed_workflows() -> list[dict[str, Any]]:
    """
    Return one entry per preset workflow that's actually present in
    the ``application`` table. Driven by the deterministic-id helper
    from the install command so we never depend on free-form name
    matching.
    """
    try:
        from application.models.application import Application
        from finance.management.commands.install_finance_workflows import (
            _deterministic_id,
            _load_workflow_files,
            _WORKFLOWS_DIR,
        )
        import os

        rows = []
        for filename, data in _load_workflow_files(os.path.normpath(_WORKFLOWS_DIR)):
            if not data:
                continue
            slug = data.get('slug') or ('__internal_' + os.path.splitext(filename)[0])
            wf_id = _deterministic_id(slug)
            row = Application.objects.filter(id=wf_id).first()
            if row is None:
                rows.append({
                    'slug': slug,
                    'id': str(wf_id),
                    'installed': False,
                    'version': data.get('version', ''),
                    'node_count': 0,
                })
                continue
            wf = row.work_flow or {}
            nodes = wf.get('nodes') if isinstance(wf, dict) else None
            rows.append({
                'slug': slug,
                'id': str(row.id),
                'installed': True,
                'name': row.name,
                'version': data.get('version', ''),
                'node_count': len(nodes or []),
                'is_publish': bool(row.is_publish),
            })
        return rows
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.system_info] workflow probe failed: {exc}')
        return []


def _materials_histogram(workspace_id: str) -> dict[str, int]:
    out = {k: 0 for k in _MATERIALS_STATUSES}
    try:
        from django.db.models import Count
        from finance.models import MaterialsTask

        rows = (
            MaterialsTask.objects
            .filter(workspace_id=workspace_id)
            .values('status')
            .annotate(n=Count('id'))
        )
        for row in rows:
            status = row.get('status') or ''
            n = int(row.get('n') or 0)
            if status in out:
                out[status] = n
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.system_info] materials histogram failed: {exc}')
    return out


def _sensitivity_histogram(workspace_id: str) -> dict[str, int]:
    out = {k: 0 for k in _SENSITIVITY_ORDER}
    try:
        from django.db.models import Count
        from knowledge.models import Document

        # Documents are scoped via their knowledge base's workspace.
        # We filter on the FK ``knowledge.workspace_id`` because the
        # Document model itself doesn't carry workspace directly.
        rows = (
            Document.objects
            .filter(knowledge__workspace_id=workspace_id)
            .values('sensitivity_level')
            .annotate(n=Count('id'))
        )
        for row in rows:
            level = row.get('sensitivity_level') or ''
            n = int(row.get('n') or 0)
            if level in out:
                out[level] = n
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.system_info] sensitivity histogram failed: {exc}')
    return out


def _recent_errors(workspace_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Return the most recent audit-log entries that look error-shaped:
      - action == FAILED, or
      - payload.status contains 'fail' (case-insensitive on the JSON
        text representation — Postgres handles this via icontains).
    """
    try:
        from django.db.models import Q
        from finance.models import FinanceAuditAction, FinanceAuditLog

        qs = (
            FinanceAuditLog.objects
            .filter(workspace_id=workspace_id)
            .filter(
                Q(action=FinanceAuditAction.FAILED)
                | Q(payload__icontains='"status": "fail')
                | Q(payload__icontains='"status":"fail')
            )
            .order_by('-created_at')[:limit]
        )

        out = []
        for row in qs:
            out.append({
                'id': str(row.id),
                'action': row.action,
                'target_type': row.target_type,
                'target_id': str(row.target_id) if row.target_id else None,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.system_info] recent_errors probe failed: {exc}')
        return []


def _ai_model_configured(workspace_id: str) -> bool:
    """True iff ``get_workspace_chat_model`` returns a non-None instance.

    Wrapped so a model-provider import failure shows as False rather
    than raising. We do NOT invoke the model — only resolve it.
    """
    try:
        from finance.service.llm import get_workspace_chat_model

        return get_workspace_chat_model(workspace_id) is not None
    except Exception as exc:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.system_info] AI model probe failed: {exc}')
        return False


class FinanceSystemInfoView(APIView):
    """
    GET /finance/workspace/<workspace_id>/system-info

    Returns the diagnostic envelope documented at the module level.
    ADMIN role required (NOT workspace manager — this surface leaks
    cross-workspace info like dep versions).
    """

    authentication_classes = [TokenAuth]

    @has_permissions(RoleConstants.ADMIN.get_workspace_role())
    def get(self, request: Request, workspace_id):
        # Lazy imports inside helpers — every individual probe is
        # already wrapped in try/except, so the overall response cannot
        # 500. Worst case we return partial info with empty lists / -1
        # counts; that's still useful for triage.
        from finance.models import (
            EmailTemplate,
            FinanceProject,
            SmtpConfig,
        )

        smtp_count = _safe_count(SmtpConfig.objects.filter(workspace_id=workspace_id))
        template_count = _safe_count(
            EmailTemplate.objects.filter(workspace_id=workspace_id)
        )
        projects_count = _safe_count(
            FinanceProject.objects.filter(workspace_id=workspace_id)
        )

        data = {
            'module_version': FINANCE_MODULE_VERSION,
            'workflows_installed': _installed_workflows(),
            'smtp_configs_count': smtp_count,
            'email_templates_count': template_count,
            'materials_tasks': _materials_histogram(workspace_id),
            'projects_count': projects_count,
            'documents_with_sensitivity': _sensitivity_histogram(workspace_id),
            'recent_errors': _recent_errors(workspace_id),
            'ai_model_configured': _ai_model_configured(workspace_id),
            'deps': _dep_versions(),
        }
        return result.success(data)
