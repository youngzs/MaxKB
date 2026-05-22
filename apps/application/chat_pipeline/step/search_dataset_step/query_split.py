# coding=utf-8
"""
    @project: maxkb
    @file： query_split.py
    @desc: C 档 —— 查询拆解。把宽泛、跨多意图的问题拆成多个聚焦子查询。

    背景：宽泛查询（"生成完整尽调报告：概况+股权+管理+征信+财务"）的 embedding 是
    多个意图的"平均向量"，对任何单一意图都不强匹配，财务/股权这类窄主题会被稀释出
    召回。把宽问题拆成多个聚焦子查询，每个子查询单独检索，可从根上消除平均向量稀释。

    本模块只含「prompt 常量」与「LLM 输出解析」两个无 Django 依赖的部分，可独立单测。
    实际的 LLM 调用在 base_search_dataset_step.split_query() 里（需要 Django 模型层）。

    裁判门：是否拆、拆几个，全交给 LLM 自身判断 —— 简单问题它会原样返回 1 个子查询
    （等于不拆），一次调用兼任「判断 + 拆解」，不另做启发式。
"""
from __future__ import annotations

import json
from typing import List

# {max} / {question} 由调用方替换。要求模型只输出 JSON 字符串数组。
SPLIT_PROMPT = """你是知识库检索的查询拆解器。给定用户问题，判断它是否包含多个相对独立的信息意图。

- 若问题聚焦单一意图（例如"注册资本是多少"），直接返回只含原问题的数组：["原问题"]。
- 若问题宽泛、跨多个主题（例如"生成完整尽调报告：企业概况、股权结构、管理团队、征信、财务"），
  把它拆成 2~{max} 个彼此聚焦、可独立检索的子查询。每个子查询只针对一个主题，
  用完整、具体的检索短句表达，确保单独拿去做向量检索能精确命中该主题的段落。

只输出一个 JSON 数组（字符串数组），不要输出任何解释文字，不要用 markdown 代码块包裹。

用户问题：{question}"""


def _extract_json_array(text: str) -> str | None:
    """从模型输出里抠出 JSON 数组片段。

    兼容模型不听话的常见情况：用 ```json``` 代码块包裹、数组前后有解释文字。
    取第一个 '[' 到最后一个 ']' 之间的内容。找不到返回 None。
    """
    if not text:
        return None
    start = text.find('[')
    end = text.rfind(']')
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1]


def parse_sub_queries(raw: str, original_query: str, max_sub_queries: int = 6) -> List[str]:
    """解析拆解器 LLM 的输出为子查询列表。

    Args:
        raw: LLM 原始输出文本。
        original_query: 用户原问题 —— 任何解析失败都退化为 [original_query]。
        max_sub_queries: 子查询数上限，超出部分截断。

    Returns:
        1~max_sub_queries 个非空子查询。**绝不返回空列表** —— 退化时返回
        [original_query]，保证下游检索至少有一条查询可用。

    退化保护：raw 为空 / 抠不出 JSON / json 解析失败 / 不是数组 / 数组里没有
    任何非空字符串 —— 一律退回 [original_query]。拆解失败不能阻断检索。
    """
    original = (original_query or '').strip()
    fallback = [original] if original else []

    snippet = _extract_json_array(raw)
    if snippet is None:
        return fallback
    try:
        arr = json.loads(snippet)
    except (ValueError, TypeError):
        return fallback
    if not isinstance(arr, list):
        return fallback

    out: List[str] = []
    seen = set()
    for item in arr:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:  # 去重 —— 模型偶尔吐重复子查询
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_sub_queries:
            break

    return out if out else fallback
