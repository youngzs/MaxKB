# coding=utf-8
"""
    @project: MaxKB
    @file： requirement_parser.py
    @desc: Parse the free-form "材料清单" text pasted by a project manager
    (usually copied from an email or extracted from a docx attachment) into
    a structured list of requirement items.

    Gate 4 implementation: pure heuristic — split by lines, strip bullet
    markers / leading numbering, treat each non-empty line as ONE item.
    Good enough for the common case where investors send a numbered list.

    TODO(Gate 5+): route the same text through the workspace's default
    chat model when the heuristic looks weak (e.g. paragraphs, nested
    sub-items, mixed Chinese/English bullets). The signature below is
    designed to absorb that without changing callers.
"""
from __future__ import annotations

import re
from typing import List
from uuid import UUID


# Strip leading bullet markers / Chinese & English ordinals / brackets.
# Examples this kills: "1.", "1、", "1)", "(1)", "①", "一、", "- ", "* ", "• ".
_LEADING_NUMBERING_RE = re.compile(
    r"""^\s*(?:
          [\(\[（【]\s*\d+\s*[\)\]）】]   # (1) [1] （1） 【1】
        | \d+\s*[.、)\.]               # 1.  1、 1)
        | [①-⑳⓪⓵-⓾⑴-⒇]              # circled / parenthesised numerals
        | [一二三四五六七八九十]+\s*[、.\)]?  # 一、 二. 三)
        | [\-\*•●◦▪]                  # bullets
    )\s*""",
    re.VERBOSE,
)

# Slugify Chinese / English to ASCII-ish keys. Keeps a–z 0–9; replaces
# everything else with `_`. Truncates to 60 chars (with an index suffix
# when needed) so JSON storage stays compact.
_NON_KEY_CHAR = re.compile(r'[^A-Za-z0-9]+')


def _slugify(label: str, fallback_index: int) -> str:
    """Produce a stable, json-safe `key` for an item label."""
    cleaned = _NON_KEY_CHAR.sub('_', label.strip().lower()).strip('_')
    if not cleaned:
        return f'item_{fallback_index}'
    if len(cleaned) > 60:
        cleaned = cleaned[:60].rstrip('_')
    return cleaned or f'item_{fallback_index}'


def parse_requirement_list(text: str, workspace_id: UUID) -> List[dict]:
    """
    Turn `text` into a list of `{key, label, description, required}` dicts.

    `workspace_id` is currently unused but reserved for the Gate 5 LLM path,
    where the workspace's default model + locale will be needed.
    """
    _ = workspace_id  # reserved for Gate 5
    if not text:
        return []

    items: List[dict] = []
    seen_keys: dict[str, int] = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        stripped = _LEADING_NUMBERING_RE.sub('', line).strip()
        if not stripped:
            continue

        # Heuristic: if a colon (Chinese or English) appears, treat the
        # left side as the canonical label and the right as a description.
        label = stripped
        description = ''
        for sep in ('：', ':'):
            if sep in stripped:
                left, _, right = stripped.partition(sep)
                left_s = left.strip()
                if left_s:
                    label = left_s
                    description = right.strip()
                break

        key = _slugify(label, fallback_index=len(items) + 1)
        # Ensure uniqueness within this batch.
        if key in seen_keys:
            seen_keys[key] += 1
            key = f'{key}_{seen_keys[key]}'
        else:
            seen_keys[key] = 1

        items.append(
            {
                'key': key,
                'label': label,
                'description': description,
                'required': True,
            }
        )

    return items
