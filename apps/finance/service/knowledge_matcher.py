# coding=utf-8
"""
    @project: MaxKB
    @file： knowledge_matcher.py
    @desc: Match parsed requirement items against the project's whitelisted
    knowledge bases, with a HARD SENSITIVITY GATE applied at the SQL level.

    Sensitivity gate (critical — Gate 4 acceptance criterion):
        We do NOT load all candidate documents then filter in Python.
        Instead, the SQL query restricts `sensitivity_level` to the levels
        the caller is cleared to read. This way an over-clearance bug in
        the application layer can never accidentally expose a higher-tier
        document.

    Matching algorithm (Gate 4 MVP):
        Per item, simple ORM `name__icontains=item.label` against the
        project's knowledge_base_ids. Top_k results per item.

    TODO(Gate 5+): replace the text match with a vector similarity search
    against the workspace's embedding model — same input/output contract,
    just a smarter middle.
"""
from __future__ import annotations

from typing import Iterable, List
from uuid import UUID

from common.constants.sensitivity_constants import SensitivityLevel
from common.utils.logger import maxkb_logger

from .sensitivity import levels_up_to


def _coerce_kb_ids(raw: Iterable) -> list[str]:
    """Project.knowledge_base_ids is a JSONField — values may be UUID or str."""
    out: list[str] = []
    for kid in raw or []:
        s = str(kid).strip()
        if s:
            out.append(s)
    return out


def match_documents_for_items(
    items: list[dict],
    workspace_id: UUID,
    project_id: UUID,
    user_max_sensitivity: str,
    top_k: int = 5,
) -> List[dict]:
    """
    For each item in `items`, return up to `top_k` candidate documents.

    Output rows shape:
        {item_key, document_id, document_name, sensitivity_level,
         score (placeholder 0.5), snippet}

    `user_max_sensitivity` is enforced at the ORM filter — documents whose
    `sensitivity_level` is above the caller's clearance are NEVER fetched.
    """
    if not items:
        return []

    # Local imports keep this module importable in stand-alone test contexts.
    try:
        from finance.models import FinanceProject
        from knowledge.models import Document
    except Exception as e:  # noqa: BLE001
        maxkb_logger.error(f'[finance.match] model import failed: {e}', exc_info=True)
        return []

    project = FinanceProject.objects.filter(
        id=project_id, workspace_id=workspace_id, is_deleted=False
    ).first()
    if project is None:
        return []

    kb_ids = _coerce_kb_ids(project.knowledge_base_ids)

    # Sensitivity GATE — SQL-level whitelist. Default-deny: an unknown
    # clearance string drops the user to PUBLIC-only.
    allowed_levels = levels_up_to(user_max_sensitivity) or [SensitivityLevel.PUBLIC.value]

    # Base queryset: cleared sensitivity AND alive AND active.
    base_qs = Document.objects.filter(
        sensitivity_level__in=allowed_levels,
        is_active=True,
    )
    if kb_ids:
        base_qs = base_qs.filter(knowledge_id__in=kb_ids)
    else:
        # TODO(Gate 5+): when knowledge_base_ids is empty, the spec leans
        # toward "fall back to every workspace KB". For Gate 4 we conserve
        # the same posture as Gate 2 (no whitelist → no matches) so a
        # half-configured project can't leak unrelated docs.
        return [
            {
                'item_key': it.get('key', ''),
                'document_id': '',
                'document_name': '',
                'sensitivity_level': '',
                'score': 0.0,
                'snippet': '',
            }
            for it in items
            if False  # explicit empty
        ]

    results: List[dict] = []
    for item in items:
        label = (item.get('label') or '').strip()
        key = item.get('key') or ''
        if not label:
            continue
        qs = base_qs.filter(name__icontains=label).order_by('-update_time')[:top_k]
        for doc in qs:
            results.append(
                {
                    'item_key': key,
                    'document_id': str(doc.id),
                    'document_name': doc.name,
                    'sensitivity_level': doc.sensitivity_level,
                    'score': 0.5,  # placeholder — Gate 5: vector similarity
                    'snippet': doc.name,
                }
            )
    return results
