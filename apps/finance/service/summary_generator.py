# coding=utf-8
"""
    @project: MaxKB
    @file： summary_generator.py
    @desc: AI-generated one-line summaries for candidate documents in a
    materials task.

    Gate 4 implementation: STUB. We return a deterministic placeholder so
    the UI can render the row, but we don't burn tokens before the workflow
    is signed off.

    TODO(Gate 5+): load the document via knowledge.models.Document +
    paragraphs, build a short context window, and call the workspace's
    default chat model with a "summarise in ≤40 chars" system prompt.
"""
from __future__ import annotations

from uuid import UUID

from common.utils.logger import maxkb_logger


def generate_summary_for_document(document_id, workspace_id: UUID) -> str:
    """
    Produce a one-line Chinese-language AI summary of `document_id`.

    Stub: returns a recognisably-placeholder string. The real Gate 5 call
    will go through the LLM and may be slow / cost tokens.
    """
    _ = workspace_id  # reserved for Gate 5 (workspace default model lookup)

    # Best-effort document-name lookup — never raises. Falls back to the
    # raw id in any failure mode.
    document_name = str(document_id)
    try:
        from knowledge.models import Document  # local import keeps this importable in tests

        doc = Document.objects.filter(id=document_id).first()
        if doc is not None and getattr(doc, 'name', ''):
            document_name = doc.name
    except Exception as e:  # noqa: BLE001 — stub must not raise
        maxkb_logger.warning(f'[finance.summary] document lookup failed: {e}')

    return f'[AI 概要：{document_name} 的内容摘要将在 Gate 5 接入真实 LLM 后生成]'
