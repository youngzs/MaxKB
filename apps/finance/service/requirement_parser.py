# coding=utf-8
"""
    @project: MaxKB
    @file： requirement_parser.py
    @desc: Parse the free-form "材料清单" text pasted by a project manager
    (usually copied from an email or extracted from a docx attachment) into
    a structured list of requirement items.

    Gate 5 implementation: LLM-first JSON extraction via the workspace's
    default chat model, with the Gate 4 line-split heuristic preserved as
    `_heuristic_parse` and used as a fallback whenever:

      * the workspace has no LLM configured,
      * the LLM call fails / times out,
      * the LLM response cannot be parsed into a valid item list.
"""
from __future__ import annotations

import json
import re
from typing import List
from uuid import UUID

from common.utils.logger import maxkb_logger

from finance.service.llm import chat_completion


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


_LLM_SYSTEM_PROMPT = (
    '你是一个融资材料分类专家。请把下面的清单拆解为结构化的需求项列表。\n'
    '每项需要：\n'
    "  - key: 英文小写下划线短标识，例如 'financial_report'\n"
    "  - label: 简洁的中文短名，例如 '财务报表（近三年）'\n"
    '  - description: 一句话补充说明（若清单原文有附注）\n'
    '  - required: 是否必备（默认 true）\n'
    '严格输出 JSON 数组，不要有任何额外文字。例如：\n'
    '[{"key":"financial_report","label":"财务报表（近三年）",'
    '"description":"合并报表+审计报告","required":true}]'
)

# Matches an opening fenced code block, optionally tagged ```json / ```JSON.
_CODE_FENCE_OPEN_RE = re.compile(r'^\s*```[a-zA-Z0-9_-]*\s*', re.MULTILINE)
_CODE_FENCE_CLOSE_RE = re.compile(r'\s*```\s*$', re.MULTILINE)


def _slugify(label: str, fallback_index: int) -> str:
    """Produce a stable, json-safe `key` for an item label."""
    cleaned = _NON_KEY_CHAR.sub('_', label.strip().lower()).strip('_')
    if not cleaned:
        return f'item_{fallback_index}'
    if len(cleaned) > 60:
        cleaned = cleaned[:60].rstrip('_')
    return cleaned or f'item_{fallback_index}'


def _strip_code_fence(text: str) -> str:
    """
    Strip leading ``` / ```json / ```JSON fences and trailing ``` from `text`.
    Defensive for the common case where instruction-tuned models wrap JSON in
    a code fence despite being told not to.
    """
    if not text:
        return text
    cleaned = text.strip()
    cleaned = _CODE_FENCE_OPEN_RE.sub('', cleaned, count=1).strip()
    cleaned = _CODE_FENCE_CLOSE_RE.sub('', cleaned, count=1).strip()
    return cleaned


def _coerce_item(raw: object, fallback_index: int) -> dict | None:
    """Validate one LLM-returned item; return None if it's not usable."""
    if not isinstance(raw, dict):
        return None
    label = raw.get('label')
    if not isinstance(label, str) or not label.strip():
        return None
    key = raw.get('key')
    if not isinstance(key, str) or not key.strip():
        key = _slugify(label, fallback_index)
    else:
        key = _slugify(key, fallback_index)
    description = raw.get('description')
    if not isinstance(description, str):
        description = ''
    required = raw.get('required')
    if not isinstance(required, bool):
        required = True
    return {
        'key': key,
        'label': label.strip(),
        'description': description.strip(),
        'required': required,
    }


def _parse_llm_response(text: str) -> List[dict]:
    """Decode an LLM JSON response into a list of valid items. [] on any error."""
    if not text:
        return []
    stripped = _strip_code_fence(text)
    try:
        data = json.loads(stripped)
    except (ValueError, TypeError) as e:
        maxkb_logger.warning(f'[finance.requirement_parser] LLM JSON decode failed: {e}')
        return []
    if not isinstance(data, list):
        return []
    items: List[dict] = []
    seen_keys: dict[str, int] = {}
    for idx, raw in enumerate(data, start=1):
        item = _coerce_item(raw, fallback_index=idx)
        if item is None:
            continue
        key = item['key']
        if key in seen_keys:
            seen_keys[key] += 1
            item['key'] = f'{key}_{seen_keys[key]}'
        else:
            seen_keys[key] = 1
        items.append(item)
    return items


def _heuristic_parse(text: str) -> List[dict]:
    """
    Deterministic line-split fallback used when the LLM is unavailable or
    returns an unusable response. Preserves the Gate 4 behavior exactly.
    """
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


def parse_requirement_list(text: str, workspace_id: UUID) -> List[dict]:
    """
    Turn `text` into a list of `{key, label, description, required}` dicts.

    LLM-first: tries the workspace's default chat model for structured JSON
    extraction. Falls back to the line-split heuristic when the model is
    unavailable or its response is unusable.
    """
    if not text:
        return []

    ws_id = str(workspace_id) if workspace_id is not None else 'default'
    llm_text = chat_completion(ws_id, _LLM_SYSTEM_PROMPT, text)
    if llm_text:
        items = _parse_llm_response(llm_text)
        if items:
            return items
        maxkb_logger.info('[finance.requirement_parser] LLM result unusable; falling back to heuristic')

    return _heuristic_parse(text)
