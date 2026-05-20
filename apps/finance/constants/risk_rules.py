# coding=utf-8
"""
    @project: MaxKB
    @file： risk_rules.py
    @desc: P2「进度归集」Gate 4 — 风险评分阈值常量（见设计文档 §七）。

    阈值本期 hardcode，可配化留待后续。改阈值 = 改本文件。
"""

RISK_NONE = 'none'
RISK_YELLOW = 'yellow'
RISK_RED = 'red'

# 风险等级排序 —— 取最高级用。
RISK_ORDER = {RISK_NONE: 0, RISK_YELLOW: 1, RISK_RED: 2}

# 信号1 阶段停留时长：now-entered_at 超过「计划时长」的倍数。
DWELL_YELLOW_MULTIPLIER = 1.0
DWELL_RED_MULTIPLIER = 1.5

# 信号2 临近 deadline：距 planned_at 不足该天数即黄（已过则红）。
DEADLINE_YELLOW_DAYS = 3


def higher_risk(a: str, b: str) -> str:
    """返回两个风险等级里的较高者。"""
    return a if RISK_ORDER.get(a, 0) >= RISK_ORDER.get(b, 0) else b
