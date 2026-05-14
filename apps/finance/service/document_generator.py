# coding=utf-8
"""
    @project: MaxKB
    @file： document_generator.py
    @desc: Render a DocumentTemplate against a placeholder-value dict, store
    the resulting docx in OSS, and (separately) convert it to HTML for
    preview via `mammoth`.

    `trigger_generation` is intentionally synchronous in Gate 3 — it runs in
    the same process as the POST request. Gate 5 will wrap it in a Celery
    task; the function signature already takes only an id so it can become
    `@shared_task` later without callsite changes.

    OSS layer: re-uses `knowledge.models.File` as the durable blob store.
    File.save(bytea) creates a Postgres large object, `get_bytes()` reads it
    back. The "OSS key" we persist on DocumentTemplate / DocumentGeneration
    is the File primary-key UUID (as string).
"""
from __future__ import annotations

import uuid as _uuid
from io import BytesIO
from typing import Optional
from uuid import UUID

import uuid_utils.compat as uuid

from common.utils.logger import maxkb_logger

from .perf import log_slow


_FILE_SOURCE_TYPE = 'SYSTEM'  # keeps finance docs from being garbage-collected by TEMPORARY_* sweeps
_FILE_SOURCE_ID_TEMPLATE = 'FINANCE_TEMPLATE'
_FILE_SOURCE_ID_GENERATION = 'FINANCE_GENERATION'


# --------------------------------------------------------------------------
# OSS helpers (thin wrappers — File model is the source of truth for storage).
# --------------------------------------------------------------------------


def _save_bytes(file_bytes: bytes, file_name: str, source_id: str) -> str:
    """
    Store `file_bytes` as a knowledge.models.File and return its id (as the
    OSS key we persist on the template / generation row).
    """
    from knowledge.models import File

    file_id = uuid.uuid7()
    f = File(
        id=file_id,
        file_name=file_name,
        meta={'finance': True, 'source_id': source_id},
        source_id=source_id,
        source_type=_FILE_SOURCE_TYPE,
    )
    f.save(file_bytes)
    return str(file_id)


def _load_bytes(oss_key: str) -> bytes:
    """Fetch bytes by OSS key. Raises ValueError on a missing key."""
    from knowledge.models import File

    try:
        # File.id is a UUID — coerce explicitly so a stray string format works.
        file_id = _uuid.UUID(str(oss_key))
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f'invalid oss key: {oss_key!r}') from e
    f = File.objects.filter(id=file_id).first()
    if f is None:
        raise ValueError(f'oss key not found: {oss_key}')
    return f.get_bytes()


# --------------------------------------------------------------------------
# Public service surface
# --------------------------------------------------------------------------


def store_template_bytes(file_bytes: bytes, file_name: str) -> str:
    """Persist a freshly uploaded template docx. Returns its OSS key."""
    return _save_bytes(file_bytes, file_name, _FILE_SOURCE_ID_TEMPLATE)


@log_slow(threshold_ms=1000, name='finance.document_generator.render_template')
def render_template(template_oss_key: str, values: dict, output_filename: str) -> str:
    """
    Render the template at `template_oss_key` against `values` and store the
    resulting docx as a new File. Returns the new OSS key.
    """
    from docxtpl import DocxTemplate

    template_bytes = _load_bytes(template_oss_key)
    doc = DocxTemplate(BytesIO(template_bytes))
    # docxtpl tolerates unknown placeholders → renders them as empty.
    doc.render(values or {})

    out = BytesIO()
    doc.save(out)
    return _save_bytes(out.getvalue(), output_filename, _FILE_SOURCE_ID_GENERATION)


@log_slow(threshold_ms=1000, name='finance.document_generator.render_to_html')
def render_to_html(output_oss_key: str) -> str:
    """
    Convert a rendered docx (already in OSS) to an HTML fragment for preview.
    Returns just the body HTML — caller is expected to wrap it in their own
    page/iframe.
    """
    import mammoth

    docx_bytes = _load_bytes(output_oss_key)
    with BytesIO(docx_bytes) as buf:
        result = mammoth.convert_to_html(buf)
    return result.value or ''


@log_slow(threshold_ms=1000, name='finance.document_generator.trigger_generation')
def trigger_generation(generation_id: UUID) -> None:
    """
    Process one DocumentGeneration row through the state machine.

    Background-friendly: takes only an id, looks the row up itself, never
    raises. On success: status=PENDING_REVIEW, output_oss_key=<key>.
    On failure: status=FAILED, error_message=<repr(exception)>.

    Idempotency: caller is expected to invoke this exactly once per row
    while the row is in GENERATING. The function refuses to re-process rows
    in any other state.
    """
    from finance.models import DocumentGeneration, DocumentTemplate, GenerationStatus

    gen: Optional[DocumentGeneration] = DocumentGeneration.objects.filter(
        id=generation_id
    ).first()
    if gen is None:
        maxkb_logger.error(f'[finance.gen] generation {generation_id} not found')
        return
    if gen.status != GenerationStatus.GENERATING:
        maxkb_logger.warning(
            f'[finance.gen] skip {generation_id}: status={gen.status} (expected generating)'
        )
        return

    template = DocumentTemplate.objects.filter(id=gen.template_id, is_deleted=False).first()
    if template is None:
        gen.status = GenerationStatus.FAILED
        gen.error_message = f'template {gen.template_id} not found or deleted'
        gen.save(update_fields=['status', 'error_message', 'updated_at'])
        return

    try:
        output_filename = f'finance-{gen.id}.docx'
        output_key = render_template(
            template_oss_key=template.docx_oss_key,
            values=gen.placeholder_values or {},
            output_filename=output_filename,
        )
        gen.output_oss_key = output_key
        gen.status = GenerationStatus.PENDING_REVIEW
        gen.error_message = ''
        gen.save(
            update_fields=['output_oss_key', 'status', 'error_message', 'updated_at']
        )
    except Exception as e:  # noqa: BLE001 — surface anything as a FAILED row
        maxkb_logger.error(
            f'[finance.gen] render failed for {generation_id}: {e}', exc_info=True
        )
        gen.status = GenerationStatus.FAILED
        gen.error_message = repr(e)[:8000]
        gen.save(update_fields=['status', 'error_message', 'updated_at'])
