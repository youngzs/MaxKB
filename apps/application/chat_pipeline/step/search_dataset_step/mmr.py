# coding=utf-8
"""
    @project: maxkb
    @file： mmr.py
    @desc: MMR（Maximal Marginal Relevance）重排 —— 纯函数，无 Django 依赖，可独立单测。

    用途：知识库检索召回后，在"与问题相关性"和"结果多样性"之间做平衡，抑制单一
    文档的雷同段落霸占 top-N。典型场景：一份征信报告几十个高度近似的段落把其他
    文档（执照、财报、简历）的相关段落挤出召回。

    算法：每步选使 MMR(d) = λ·rel(d) − (1−λ)·max_{s∈已选} sim(d,s) 最大的候选。
    λ 越大越偏相关性，越小越偏多样性。
"""
from __future__ import annotations

from typing import List

import numpy as np


def _coerce(v) -> np.ndarray:
    """把 embedding 统一成 1-D float32 ndarray —— 兼容 list / ndarray / '[...]' 字符串。"""
    if isinstance(v, str):
        return np.fromstring(v.strip().strip('[]'), sep=',', dtype=np.float32)
    return np.asarray(v, dtype=np.float32)


def mmr_rerank(query_embedding, candidates: List[dict], k: int,
               lambda_: float = 0.5) -> List[dict]:
    """
    对 candidates 做 MMR 重排，返回前 k 个（按 MMR 选取顺序）。

    Args:
        query_embedding: 查询向量（list / ndarray / 字符串）。
        candidates: 每项是 dict，**必须含 'embedding' 键**（list/ndarray/str）；
                    其余键原样保留，调用方靠它们关联回检索结果。
        k: 最终保留数量。
        lambda_: 相关性权重 0~1，越大越偏相关、越小越偏多样。默认 0.5 ——
                 对"单文档几十个雷同段落"这类病态冗余库去重力度足够；
                 0.7 偏相关、去重偏弱。

    候选数 ≤ k 时原样返回（无需重排）。函数不抛异常前提是入参形状合法 ——
    调用方负责 try/except 兜底（向量缺失等）。
    """
    if k <= 0:
        return []
    if len(candidates) <= k:
        return list(candidates)

    q = _coerce(query_embedding)
    qn = np.linalg.norm(q)
    if qn:
        q = q / qn

    # 候选矩阵行归一化 —— 归一后点积即余弦相似度
    mat = np.vstack([_coerce(c['embedding']) for c in candidates])
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms

    relevance = mat @ q  # shape (N,) —— 每个候选与查询的余弦相似度

    selected: List[int] = []
    remaining: List[int] = list(range(len(candidates)))

    while len(selected) < k and remaining:
        if not selected:
            # 第一个：纯取相关性最高 —— 保证最相关结果不被多样性惩罚掉
            pick = max(remaining, key=lambda i: relevance[i])
        else:
            sel = mat[selected]  # (S, D)
            best_pick, best_mmr = remaining[0], -1e18
            for i in remaining:
                # redundancy = 与已选集合里最像的那个的相似度
                redundancy = float(np.max(sel @ mat[i]))
                score = lambda_ * float(relevance[i]) - (1.0 - lambda_) * redundancy
                if score > best_mmr:
                    best_mmr, best_pick = score, i
            pick = best_pick
        selected.append(pick)
        remaining.remove(pick)

    return [candidates[i] for i in selected]
