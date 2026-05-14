# coding=utf-8
"""
    @project: MaxKB
    @file： zip_packager.py
    @desc: Bundle a set of selected knowledge documents into a single
    .zip file in OSS, ready for download / external sharing.

    Two entry points:
        pack_documents_grouped(item_groups, ...)
            Each group goes into its own folder. Used by MaterialsTask
            once the user has curated their selection per requirement
            item.

        pack_documents_flat(document_ids, ...)
            All documents at the zip root. Used by `zip_pack_node` (Gate
            4 Track B workflow node).

    Both:
      - tolerate missing files (write a `MISSING_<name>.txt` marker)
      - inject a `00_README.md` index that lists every file in pack order
      - return an OSS key (a File primary-key UUID, as string) for the
        produced zip; callers persist that on the task / workflow row.

    OSS layer: re-uses the same `knowledge.models.File` blob store as
    Gate 3's document_generator (see `_save_bytes` / `_load_bytes` there).
"""
from __future__ import annotations

import zipfile
from io import BytesIO
from typing import List, Optional
from uuid import UUID

from common.utils.logger import maxkb_logger

from .perf import log_slow


_ZIP_FILE_SOURCE_ID = 'FINANCE_MATERIALS_ZIP'


def _safe_filename(name: str) -> str:
    """Strip path separators and other junk so a bad doc name can't escape its folder."""
    if not name:
        return 'unnamed'
    cleaned = name.replace('\\', '_').replace('/', '_').strip()
    return cleaned or 'unnamed'


def _load_document(document_id) -> tuple[Optional[bytes], Optional[str]]:
    """
    Best-effort: load `(file_bytes, file_name)` for a knowledge.Document.

    Returns (None, None) on any failure — caller must emit a MISSING marker
    rather than aborting the whole pack.

    Wiring: a Document references one or more knowledge.File rows via
    `meta` (depending on doc type). For the Gate 4 MVP we look up the
    most recent File whose source_id matches the document id; if none,
    we fall back to a placeholder body so the zip still contains a row
    for every selected document.
    """
    try:
        from knowledge.models import Document, File
    except Exception as e:  # noqa: BLE001
        maxkb_logger.warning(f'[finance.pack] model import failed: {e}')
        return None, None

    try:
        doc = Document.objects.filter(id=document_id).first()
        if doc is None:
            return None, None
        # Prefer a File explicitly tagged with this document id; fall back
        # to anything keyed by name.
        f = File.objects.filter(source_id=str(doc.id)).order_by('-create_time').first()
        if f is None:
            return None, doc.name
        return f.get_bytes(), doc.name
    except Exception as e:  # noqa: BLE001 — log and degrade
        maxkb_logger.warning(f'[finance.pack] document load failed {document_id}: {e}')
        return None, None


def _build_readme(lines: list[str]) -> bytes:
    body = '\n'.join(['# 材料清单 / Materials Index', ''] + lines + [''])
    return body.encode('utf-8')


def _save_zip_bytes(zip_bytes: bytes, output_filename: str) -> str:
    """Persist the produced zip to OSS and return its key."""
    # Reuse Gate 3's File-based OSS helper so we have ONE blob path in the codebase.
    from .document_generator import _save_bytes

    return _save_bytes(zip_bytes, output_filename, _ZIP_FILE_SOURCE_ID)


@log_slow(threshold_ms=1000, name='finance.zip_packager.pack_documents_grouped')
def pack_documents_grouped(
    item_groups: List[dict],
    workspace_id: UUID,
    output_filename: str = 'materials.zip',
) -> str:
    """
    `item_groups` is `[{folder: str, document_ids: list[str]}, ...]`.

    Returns the OSS key of the produced zip.
    """
    _ = workspace_id  # reserved — useful for future per-workspace zip routing

    buffer = BytesIO()
    readme_lines: list[str] = []

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for group in item_groups or []:
            folder = _safe_filename(group.get('folder') or 'misc')
            readme_lines.append(f'## {folder}')
            for doc_id in group.get('document_ids') or []:
                file_bytes, doc_name = _load_document(doc_id)
                name = _safe_filename(doc_name or str(doc_id))
                if file_bytes is None:
                    marker = f'{folder}/MISSING_{name}.txt'
                    msg = (
                        f'Document {doc_id} was selected but could not be loaded.\n'
                        f'It may have been deleted or its blob is unavailable.\n'
                    )
                    zf.writestr(marker, msg.encode('utf-8'))
                    readme_lines.append(f'- [MISSING] {name} ({doc_id})')
                else:
                    zf.writestr(f'{folder}/{name}', file_bytes)
                    readme_lines.append(f'- {name}')
            readme_lines.append('')
        zf.writestr('00_README.md', _build_readme(readme_lines))

    return _save_zip_bytes(buffer.getvalue(), output_filename)


@log_slow(threshold_ms=1000, name='finance.zip_packager.pack_documents_flat')
def pack_documents_flat(
    document_ids: List[str],
    workspace_id: UUID,
    output_filename: str = 'materials.zip',
) -> str:
    """
    Flat-layout variant — every doc at the zip root, no per-item folder.
    Used by the `zip_pack_node` workflow node where there is no item grouping.
    """
    _ = workspace_id

    buffer = BytesIO()
    readme_lines: list[str] = []

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc_id in document_ids or []:
            file_bytes, doc_name = _load_document(doc_id)
            name = _safe_filename(doc_name or str(doc_id))
            if file_bytes is None:
                zf.writestr(
                    f'MISSING_{name}.txt',
                    f'Document {doc_id} could not be loaded.\n'.encode('utf-8'),
                )
                readme_lines.append(f'- [MISSING] {name} ({doc_id})')
            else:
                zf.writestr(name, file_bytes)
                readme_lines.append(f'- {name}')
        zf.writestr('00_README.md', _build_readme(readme_lines))

    return _save_zip_bytes(buffer.getvalue(), output_filename)
