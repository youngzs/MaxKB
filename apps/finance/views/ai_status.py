# coding=utf-8
"""
    @project: MaxKB
    @file:    ai_status.py
    @desc:    Lightweight LLM-availability probe for the finance workspace
              (Gate 8 Track C — C1).

    The finance AI features (requirement parsing, summary generation,
    document ai-fill) all gracefully fall back to deterministic stubs
    when no LLM model is configured for the workspace. The user, however,
    gets no signal that this happened — the stub output just looks like a
    (poor) result. This endpoint lets the frontend surface a banner so
    operators know the workspace is running degraded.

    Contract:
      GET /finance/workspace/<workspace_id>/ai-status
      {
        "llm_configured": bool,
        "llm_model_name": str | null,
        "embedding_configured": bool,   # for knowledge matching
        "degraded_features": ["requirement_parsing",
                              "summary_generation", "ai_fill"] | []
      }

    Permission: FINANCE_READ — any finance user should be able to see
    whether the workspace is degraded. Mirrors workflow_run.py's gate
    (USER / WORKSPACE_MANAGE fall through as alternatives).

    Robustness: like healthz / system-info this endpoint must never 500.
    Each probe is wrapped so a model-provider import failure surfaces as
    a conservative ``False`` rather than an exception.
"""
from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.utils.logger import maxkb_logger

# Features that degrade to deterministic stubs when no LLM is configured.
# Order matters only for response stability — keep alphabetical-ish but
# grouped by user-facing flow.
_LLM_DEPENDENT_FEATURES = (
    'requirement_parsing',
    'summary_generation',
    'ai_fill',
)


def _resolve_llm_model_name(workspace_id: str):
    """Return the workspace's default LLM model_name, or None.

    Resolution mirrors ``finance.service.llm.get_workspace_chat_model``:
    first a workspace-scoped LLM row, then the global ('default') one.
    We look up the Model row (cheap) rather than instantiating the chat
    model — this endpoint should be fast and side-effect free.

    Never raises: a provider/registry import failure returns None.
    """
    try:
        from django.db.models import QuerySet
        from models_provider.models import Model

        model_row = QuerySet(Model).filter(
            workspace_id=workspace_id, model_type='LLM', status='SUCCESS',
        ).order_by('create_time').first()
        if model_row is None and workspace_id != 'default':
            model_row = QuerySet(Model).filter(
                workspace_id='default', model_type='LLM', status='SUCCESS',
            ).order_by('create_time').first()
        if model_row is None:
            return None
        # Prefer the human-friendly display name; fall back to model_name.
        return model_row.name or model_row.model_name or None
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        maxkb_logger.warning(f'[finance.ai_status] LLM probe failed: {exc}')
        return None


def _llm_configured(workspace_id: str) -> bool:
    """True iff ``get_workspace_chat_model`` resolves a usable instance.

    We use the real resolver (not just a Model row check) so credential
    or instantiation failures count as "not configured" — that matches
    what the AI services actually experience at call time.
    """
    try:
        from finance.service.llm import get_workspace_chat_model

        return get_workspace_chat_model(workspace_id) is not None
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        maxkb_logger.warning(f'[finance.ai_status] LLM resolve probe failed: {exc}')
        return False


def _embedding_configured(workspace_id: str) -> bool:
    """True iff an EMBEDDING-type Model row exists for the workspace.

    Used for knowledge-matching quality. Resolution falls back to the
    global ('default') workspace, same as the LLM lookup.
    """
    try:
        from django.db.models import QuerySet
        from models_provider.models import Model

        qs = QuerySet(Model).filter(
            workspace_id=workspace_id, model_type='EMBEDDING', status='SUCCESS',
        )
        if qs.exists():
            return True
        if workspace_id != 'default':
            return QuerySet(Model).filter(
                workspace_id='default', model_type='EMBEDDING', status='SUCCESS',
            ).exists()
        return False
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        maxkb_logger.warning(f'[finance.ai_status] embedding probe failed: {exc}')
        return False


class FinanceAiStatusView(APIView):
    """
    GET /finance/workspace/<workspace_id>/ai-status

    Returns whether the finance AI features will run for real or fall
    back to stubs. See the module docstring for the response contract.
    """

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Finance AI status'),
        description=_(
            'Report whether the workspace has an LLM / embedding model '
            'configured; lists which AI features will degrade to stubs.'
        ),
        operation_id=_('Finance AI status'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        llm_configured = _llm_configured(workspace_id)
        # Only resolve the display name when the LLM is actually usable —
        # a stale Model row with bad credentials shouldn't be advertised.
        llm_model_name = (
            _resolve_llm_model_name(workspace_id) if llm_configured else None
        )
        embedding_configured = _embedding_configured(workspace_id)

        # Every LLM-dependent feature degrades together — they all share
        # the same chat-model resolver. Embedding being absent does not
        # by itself flag a "degraded feature": it only lowers match
        # quality, the feature still runs.
        degraded_features = (
            [] if llm_configured else list(_LLM_DEPENDENT_FEATURES)
        )

        return result.success({
            'llm_configured': llm_configured,
            'llm_model_name': llm_model_name,
            'embedding_configured': embedding_configured,
            'degraded_features': degraded_features,
        })
