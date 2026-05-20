# coding=utf-8
"""AI-assisted placeholder metadata suggestions for finance templates."""

from __future__ import annotations

import json
import re
from typing import Iterable

from .llm import chat_completion
from .template_parser import build_ai_hint, infer_label_from_key


_ANNOTATION_SYSTEM_PROMPT = (
    "你是融资文档模板助手。请根据模板名称、模板正文片段和占位符 key，"
    "为每个占位符生成简体中文显示标签和一句简短 AI 填充提示语。\n\n"
    "【模板名称】\n{template_name}\n\n"
    "【模板正文片段】\n{template_text}\n\n"
    "【占位符】\n{fields_block}\n\n"
    "【输出要求】\n"
    "1. 严格返回 JSON 对象；key 为占位符 key；value 为对象，包含 label 与 ai_hint；\n"
    "2. label 使用简体中文，尽量取模板正文中占位符附近的字段名；\n"
    "3. ai_hint 用一句话说明 AI 填充该字段时应写什么，控制在 80 字以内；\n"
    "4. 不要返回 markdown、解释或额外字段。"
)


def _normalise_type(value: str | None, key: str) -> str:
    allowed = {"text", "long_text", "number", "date", "enum"}
    return value if value in allowed else "text"


def _normalise_enum_options(value) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    return [str(v) for v in value if str(v).strip()]


def _fallback_placeholder(meta: dict) -> dict:
    key = str(meta.get("key") or "").strip()
    label = str(meta.get("label") or "").strip()
    if not label or label == key:
        label = infer_label_from_key(key)
    ai_hint = str(meta.get("ai_hint") or "").strip() or build_ai_hint(label)
    return {
        "key": key,
        "label": label,
        "type": _normalise_type(meta.get("type"), key),
        "required": False,
        "ai_hint": ai_hint,
        "enum_options": _normalise_enum_options(meta.get("enum_options")),
    }


def _parse_ai_json(text: str | None) -> dict:
    if not text:
        return {}
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except Exception:  # noqa: BLE001
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fields_block(placeholders: list[dict]) -> str:
    lines = []
    for item in placeholders:
        lines.append(f"- key: {item['key']}; 当前标签: {item['label']}; 类型: {item['type']}")
    return "\n".join(lines)


def suggest_placeholder_annotations(
    placeholders: list[dict],
    *,
    workspace_id: str = "default",
    template_name: str = "",
    template_text: str = "",
) -> list[dict]:
    """Return suggested placeholder metadata without mutating the template."""
    base = [_fallback_placeholder(p) for p in placeholders if p.get("key")]
    if not base:
        return []

    system_prompt = _ANNOTATION_SYSTEM_PROMPT.format(
        template_name=template_name or "未命名模板",
        template_text=(template_text or "")[:6000] or "（无正文片段）",
        fields_block=_fields_block(base),
    )
    ai_map = _parse_ai_json(chat_completion(workspace_id, system_prompt, "请生成占位符元数据 JSON。"))

    for item in base:
        candidate = ai_map.get(item["key"])
        if not isinstance(candidate, dict):
            continue
        label = str(candidate.get("label") or "").strip()
        hint = str(candidate.get("ai_hint") or "").strip()
        if label and len(label) <= 60:
            item["label"] = label
        if hint and len(hint) <= 200:
            item["ai_hint"] = hint
    return base
