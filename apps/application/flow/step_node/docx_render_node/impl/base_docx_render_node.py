# coding=utf-8
"""
    @project: maxkb
    @file:    base_docx_render_node.py
    @desc:    Default implementation of the DOCX-render workflow node.

    Reads a docx blob out of MaxKB's File store (keyed by ``template_oss_key``),
    renders it with ``docxtpl.DocxTemplate`` against ``placeholder_values``,
    and writes the result back as a new File whose id is returned as the
    output OSS key.

    Failure handling: any exception during download / render / upload is
    captured and surfaced as ``error`` in the node output rather than
    propagated. This lets the workflow continue and the downstream
    consumer (Track A's document generator) inspect the result.
"""
from __future__ import annotations

import uuid as _uuid
from io import BytesIO

import uuid_utils.compat as uuid

from application.flow.i_step_node import NodeResult
from application.flow.step_node.docx_render_node.i_docx_render_node import IDocxRenderNode


# Keep these in sync with apps/finance/service/document_generator.py — finance
# templates and generations are stored under these source markers so they
# escape TEMPORARY_* sweeps. Duplicated here (not imported) to keep the node
# module free of a hard dependency on the finance app.
_FILE_SOURCE_TYPE = 'SYSTEM'
_FILE_SOURCE_ID_GENERATION = 'FINANCE_GENERATION'


def _load_bytes(oss_key: str) -> bytes:
    """Fetch the raw bytes for an OSS key (== File.id) or raise ValueError."""
    from knowledge.models import File

    try:
        file_id = _uuid.UUID(str(oss_key))
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f'invalid oss key: {oss_key!r}') from e
    f = File.objects.filter(id=file_id).first()
    if f is None:
        raise ValueError(f'oss key not found: {oss_key}')
    return f.get_bytes()


def _save_bytes(file_bytes: bytes, file_name: str) -> str:
    """Persist ``file_bytes`` as a File row and return its id (as str)."""
    from knowledge.models import File

    file_id = uuid.uuid7()
    f = File(
        id=file_id,
        file_name=file_name,
        meta={'finance': True, 'source_id': _FILE_SOURCE_ID_GENERATION,
              'node_type': IDocxRenderNode.type},
        source_id=_FILE_SOURCE_ID_GENERATION,
        source_type=_FILE_SOURCE_TYPE,
    )
    f.save(file_bytes)
    return str(file_id)


class BaseDocxRenderNode(IDocxRenderNode):
    """Default in-process implementation of the docx-render node."""

    def save_context(self, details, workflow_manage):
        self.context['output_oss_key'] = details.get('output_oss_key', '')
        self.context['error'] = details.get('error')
        self.context['exception_message'] = details.get('error')

    def execute(self, template_oss_key, placeholder_values, output_filename, **kwargs) -> NodeResult:
        # Inputs surface in run details for debugging / replay.
        self.context['template_oss_key'] = template_oss_key
        self.context['placeholder_values'] = placeholder_values
        self.context['output_filename'] = output_filename

        try:
            from docxtpl import DocxTemplate

            template_bytes = _load_bytes(template_oss_key)
            doc = DocxTemplate(BytesIO(template_bytes))
            # docxtpl tolerates unknown placeholders: they render as empty.
            doc.render(placeholder_values or {})

            out = BytesIO()
            doc.save(out)
            output_oss_key = _save_bytes(out.getvalue(), output_filename or 'output.docx')
            return NodeResult({'output_oss_key': output_oss_key, 'error': None}, {})
        except Exception as e:  # noqa: BLE001 — node must not crash the workflow
            return NodeResult({'output_oss_key': '', 'error': str(e)}, {})

    def get_details(self, index: int, **kwargs):
        return {
            'name': self.node.properties.get('stepName'),
            'index': index,
            'run_time': self.context.get('run_time'),
            'type': self.node.type,
            'status': self.status,
            'err_message': self.err_message,
            'template_oss_key': self.context.get('template_oss_key'),
            'output_filename': self.context.get('output_filename'),
            'output_oss_key': self.context.get('output_oss_key', ''),
            'error': self.context.get('error'),
            'enableException': self.node.properties.get('enableException'),
        }
