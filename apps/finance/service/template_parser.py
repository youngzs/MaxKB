# coding=utf-8
"""
    @project: MaxKB
    @file： template_parser.py
    @desc: docx → placeholder-metadata extraction.

    Uses docxtpl's DocxTemplate.get_undeclared_template_variables() to find
    every Jinja-style variable referenced in the document body, headers and
    footers. Returns a list of placeholder dicts shaped exactly like
    DocumentTemplate.placeholders:

        [{key, label, type, required, ai_hint, enum_options}, ...]

    `type` is inferred from the variable name with a small set of heuristics
    (see _infer_type) — the user can override it later from the metadata
    editor.

    Pure function; no Django or OSS dependency, so unit tests can exercise it
    by feeding raw docx bytes built with python-docx.
"""
from __future__ import annotations

from io import BytesIO
from typing import Iterable


_NUMBER_SUFFIXES = ('_amount', '_count', '_number', '_qty', '_quantity', '_total')
_DATE_SUFFIXES = ('_date', '_at', '_time', '_deadline', '_expiry')
_LONG_TEXT_SUFFIXES = (
    '_desc',
    '_description',
    '_summary',
    '_analysis',
    '_reason',
    '_notes',
    '_remark',
    '_content',
)


def _infer_type(key: str) -> str:
    """Heuristic: variable suffix → placeholder type."""
    lowered = key.lower()
    if lowered.endswith(_DATE_SUFFIXES):
        return 'date'
    if lowered.endswith(_NUMBER_SUFFIXES):
        return 'number'
    if lowered.endswith(_LONG_TEXT_SUFFIXES):
        return 'long_text'
    return 'text'


def _build_placeholder(key: str) -> dict:
    return {
        'key': key,
        'label': key,
        'type': _infer_type(key),
        'required': True,
        'ai_hint': '',
        'enum_options': [],
    }


def extract_placeholders(docx_bytes: bytes) -> list[dict]:
    """
    Scan a docx file for Jinja-style placeholders {{ var }} / {% block %}
    using docxtpl.

    Args:
        docx_bytes: full bytes of a .docx file.

    Returns:
        Stable-ordered list of placeholder dicts (one per unique variable).
    """
    # Local import: docxtpl pulls in python-docx + lxml which we don't want
    # to load on every Django boot.
    from docxtpl import DocxTemplate

    template = DocxTemplate(BytesIO(docx_bytes))
    # docxtpl returns a Python set; sort for deterministic output.
    variables: Iterable[str] = template.get_undeclared_template_variables() or set()
    seen: list[str] = sorted({str(v) for v in variables if v})
    return [_build_placeholder(key) for key in seen]
