# coding=utf-8
"""
    @project: MaxKB
    @file： risk.py
    @desc: P2「进度归集」Gate 4 — 运行时风险评分（见设计文档 §七）。

    对项目的「当前 active 阶段」算 none / yellow / red：
      - 信号1 阶段停留时长：now − entered_at vs 计划时长（planned_at − 上一阶段
        actual_at）。超 ×1.0 黄、超 ×1.5 红；缺数据则跳过此信号。
      - 信号2 临近 deadline：距 planned_at ≤3 天黄、已过 planned_at 未完成红。
      - 信号3 材料完整度：项目关联的材料任务存在 failed → 红。
    项目级风险 = 各 active 阶段信号取最高级。

    本期暂缓（设计文档 §七 列出但本 Gate 不实现，留作 fast-follow）：
      - 信号4「关键文件缺失」—— 缺「阶段 → 必备流程文档」映射配置，需新 DR。
      - 信号3 的「required 项无匹配文档 → 黄」子规则 —— 草稿态材料任务天然
        无匹配、误报噪声大；本期只保留 failed → 红。

    风险不落表 —— 每次查询实时算（设计文档 §5.3）。reasons 返回**代码**，
    由前端 i18n 成文案。
"""
from datetime import timedelta

from django.utils import timezone

from finance.constants.risk_rules import (
    DEADLINE_YELLOW_DAYS,
    DWELL_RED_MULTIPLIER,
    DWELL_YELLOW_MULTIPLIER,
    RISK_NONE,
    RISK_RED,
    RISK_YELLOW,
    higher_risk,
)
from finance.models import ProjectStageStatus


def _dwell_risk(active_stage, prev_actual_at, now):
    """信号1：阶段停留时长。返回 (level, reason_code|None)。"""
    entered = active_stage.entered_at
    planned = active_stage.planned_at
    if not entered or not planned or not prev_actual_at:
        return RISK_NONE, None
    planned_seconds = (planned - prev_actual_at).total_seconds()
    if planned_seconds <= 0:
        return RISK_NONE, None
    ratio = (now - entered).total_seconds() / planned_seconds
    if ratio > DWELL_RED_MULTIPLIER:
        return RISK_RED, 'dwell_red'
    if ratio > DWELL_YELLOW_MULTIPLIER:
        return RISK_YELLOW, 'dwell_yellow'
    return RISK_NONE, None


def _deadline_risk(active_stage, now):
    """信号2：临近/超过 deadline。返回 (level, reason_code|None)。"""
    planned = active_stage.planned_at
    if not planned:
        return RISK_NONE, None
    if now > planned:
        return RISK_RED, 'deadline_red'
    if now + timedelta(days=DEADLINE_YELLOW_DAYS) >= planned:
        return RISK_YELLOW, 'deadline_yellow'
    return RISK_NONE, None


def compute_project_risk(stages, *, has_failed_materials=False, now=None):
    """
    运行时风险评分。`stages` = 该项目的 ProjectStageRecord 列表（任意顺序）。
    返回 `{'level': 'none'|'yellow'|'red', 'reasons': [code, ...]}`。
    """
    now = now or timezone.now()
    level = RISK_NONE
    reasons: list[str] = []

    by_order = {s.stage_order: s for s in stages}
    for stage in stages:
        if stage.status != ProjectStageStatus.ACTIVE:
            continue
        prev = by_order.get(stage.stage_order - 1)
        prev_actual = prev.actual_at if prev else None
        for lvl, code in (
            _dwell_risk(stage, prev_actual, now),
            _deadline_risk(stage, now),
        ):
            level = higher_risk(level, lvl)
            if code:
                reasons.append(code)

    if has_failed_materials:
        level = higher_risk(level, RISK_RED)
        reasons.append('materials_failed')

    return {'level': level, 'reasons': reasons}
