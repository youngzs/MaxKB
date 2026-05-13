# coding=utf-8
"""
    @project: maxkb
    @file:    base_zip_pack_node.py
    @desc:    Default implementation of the ZIP-pack workflow node.

    Downloads each document referenced by ``document_oss_keys`` from
    MaxKB's File store and writes them into a single zip archive. Files
    can be optionally grouped into sub-folders via ``item_folders``. An
    auto-generated ``00_README.md`` index is added at the archive root.
    Files that could not be retrieved are recorded in the ``missing``
    output and a placeholder ``MISSING_<name>.txt`` is added so the
    archive itself documents the gap.

    Failure handling: any exception during download / packaging / upload
    is captured and surfaced as ``error`` in the node output rather than
    propagated, mirroring the contract of docx_render_node.
"""
from __future__ import annotations

import datetime as _dt
import uuid as _uuid
import zipfile
from io import BytesIO

import uuid_utils.compat as uuid

from application.flow.i_step_node import NodeResult
from application.flow.step_node.zip_pack_node.i_zip_pack_node import IZipPackNode

# Keep these in sync with apps/finance/service/document_generator.py — finance
# templates and generations are stored under these source markers so they
# escape TEMPORARY_* sweeps. Duplicated here (not imported) to keep the node
# module free of a hard dependency on the finance app.
_FILE_SOURCE_TYPE = 'SYSTEM'
_FILE_SOURCE_ID_GENERATION = 'FINANCE_GENERATION'


def _load_bytes(oss_key: str):
    """Fetch raw bytes for an OSS key (== File.id) or return None if missing."""
    from knowledge.models import File

    try:
        file_id = _uuid.UUID(str(oss_key))
    except (ValueError, AttributeError, TypeError):
        return None
    f = File.objects.filter(id=file_id).first()
    if f is None:
        return None
    try:
        return f.get_bytes()
    except Exception:  # noqa: BLE001 — treat any read failure as 'missing'
        return None


def _save_bytes(file_bytes: bytes, file_name: str) -> str:
    """Persist ``file_bytes`` as a File row and return its id (as str)."""
    from knowledge.models import File

    file_id = uuid.uuid7()
    f = File(
        id=file_id,
        file_name=file_name,
        meta={'finance': True, 'source_id': _FILE_SOURCE_ID_GENERATION,
              'node_type': IZipPackNode.type},
        source_id=_FILE_SOURCE_ID_GENERATION,
        source_type=_FILE_SOURCE_TYPE,
    )
    f.save(file_bytes)
    return str(file_id)


def _pad(lst, n, fill=''):
    """Return ``lst`` padded to length ``n`` with ``fill``."""
    if lst is None:
        lst = []
    if len(lst) >= n:
        return list(lst)
    return list(lst) + [fill] * (n - len(lst))


def _safe_segment(value: str, fallback: str = '') -> str:
    """Strip path traversal and separators from a path segment."""
    s = (value or '').strip().replace('\\', '/').strip('/')
    # collapse '..' segments and stray separators
    parts = [p for p in s.split('/') if p and p not in ('.', '..')]
    cleaned = '/'.join(parts).strip()
    return cleaned or fallback


def _build_zip(oss_keys, names, folders):
    """
    Build the archive in-memory.

    Returns a tuple of (zip_bytes, included_count, missing_names, entries)
    where ``entries`` is a list of dicts describing each archive member
    (used to render the README).
    """
    buf = BytesIO()
    included = 0
    missing: list[str] = []
    entries: list[dict] = []
    seen_paths: set[str] = set()

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, key in enumerate(oss_keys):
            raw_name = names[idx] if idx < len(names) and names[idx] else f'file_{idx}.bin'
            folder = _safe_segment(folders[idx] if idx < len(folders) else '')
            name = _safe_segment(raw_name, fallback=f'file_{idx}.bin')

            arcname = f'{folder}/{name}' if folder else name
            # Ensure uniqueness within the archive — append a counter if needed.
            unique_arcname = arcname
            dup = 1
            while unique_arcname in seen_paths:
                base, dot, ext = name.rpartition('.')
                stem = base if dot else name
                suffix = f'.{ext}' if dot else ''
                candidate = f'{stem}_{dup}{suffix}'
                unique_arcname = f'{folder}/{candidate}' if folder else candidate
                dup += 1
            seen_paths.add(unique_arcname)

            payload = _load_bytes(key)
            if payload is None:
                marker_name = f'MISSING_{name}.txt' if folder == '' else f'{folder}/MISSING_{name}.txt'
                # MISSING markers also need to dedupe in their own right.
                m_arc = marker_name
                m_dup = 1
                while m_arc in seen_paths:
                    m_arc = f'{marker_name}.{m_dup}'
                    m_dup += 1
                seen_paths.add(m_arc)
                zf.writestr(m_arc, f'Source OSS key {key!r} could not be retrieved.\n')
                missing.append(name)
                entries.append({
                    'index': idx,
                    'oss_key': key,
                    'name': name,
                    'folder': folder,
                    'arcname': m_arc,
                    'status': 'missing',
                })
                continue

            zf.writestr(unique_arcname, payload)
            included += 1
            entries.append({
                'index': idx,
                'oss_key': key,
                'name': name,
                'folder': folder,
                'arcname': unique_arcname,
                'status': 'included',
                'size': len(payload),
            })

        # Render the auto-generated index last so it sees the final layout.
        readme = _render_readme(entries, included, missing)
        zf.writestr('00_README.md', readme)

    return buf.getvalue(), included, missing, entries


def _render_readme(entries, included, missing) -> str:
    now = _dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [
        '# Archive index',
        '',
        f'Generated: {now}',
        f'Included files: {included}',
        f'Missing files: {len(missing)}',
        '',
        '## Entries',
        '',
        '| # | Status | Path | Source OSS key |',
        '| - | ------ | ---- | -------------- |',
    ]
    for e in entries:
        lines.append(
            f"| {e['index']} | {e['status']} | {e['arcname']} | {e['oss_key']} |"
        )
    lines.append('')
    return '\n'.join(lines)


class BaseZipPackNode(IZipPackNode):
    """Default in-process implementation of the zip-pack node."""

    def save_context(self, details, workflow_manage):
        self.context['output_oss_key'] = details.get('output_oss_key', '')
        self.context['included_count'] = details.get('included_count', 0)
        self.context['missing'] = details.get('missing') or []
        self.context['error'] = details.get('error')
        self.context['exception_message'] = details.get('error')

    def execute(self, document_oss_keys, document_names, item_folders, archive_name, **kwargs) -> NodeResult:
        # Surface inputs in run details for debugging / replay.
        oss_keys = list(document_oss_keys or [])
        self.context['document_oss_keys'] = oss_keys
        self.context['document_names'] = list(document_names or [])
        self.context['item_folders'] = list(item_folders or [])
        self.context['archive_name'] = archive_name

        try:
            if not oss_keys:
                return NodeResult({
                    'output_oss_key': '',
                    'included_count': 0,
                    'missing': [],
                    'error': 'document_oss_keys is empty',
                }, {})

            n = len(oss_keys)
            names = _pad(document_names, n, fill='')
            # Fill in default names for blank slots.
            names = [
                (names[i] if names[i] else f'file_{i}.bin') for i in range(n)
            ]
            folders = _pad(item_folders, n, fill='')

            zip_bytes, included, missing, _entries = _build_zip(oss_keys, names, folders)
            output_oss_key = _save_bytes(zip_bytes, archive_name or 'materials.zip')

            return NodeResult({
                'output_oss_key': output_oss_key,
                'included_count': included,
                'missing': missing,
                'error': None,
            }, {})
        except Exception as e:  # noqa: BLE001 — node must not crash the workflow
            return NodeResult({
                'output_oss_key': '',
                'included_count': 0,
                'missing': [],
                'error': str(e),
            }, {})

    def get_details(self, index: int, **kwargs):
        return {
            'name': self.node.properties.get('stepName'),
            'index': index,
            'run_time': self.context.get('run_time'),
            'type': self.node.type,
            'status': self.status,
            'err_message': self.err_message,
            'document_oss_keys': self.context.get('document_oss_keys'),
            'document_names': self.context.get('document_names'),
            'item_folders': self.context.get('item_folders'),
            'archive_name': self.context.get('archive_name'),
            'output_oss_key': self.context.get('output_oss_key', ''),
            'included_count': self.context.get('included_count', 0),
            'missing': self.context.get('missing') or [],
            'error': self.context.get('error'),
            'enableException': self.node.properties.get('enableException'),
        }
