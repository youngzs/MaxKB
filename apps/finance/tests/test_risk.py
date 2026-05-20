# coding=utf-8
"""
    @project: MaxKB
    @file： test_risk.py
    @desc: P2「进度归集」Gate 4 测试 — 运行时风险评分（finance.service.risk）。

    SimpleTestCase：`compute_project_risk` 只读 stage 对象的属性，用
    SimpleNamespace 充当 ProjectStageRecord 即可，无需数据库。
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from finance.service.risk import compute_project_risk

NOW = datetime(2026, 5, 20, 12, 0, 0, tzinfo=dt_timezone.utc)


def _stage(order, status, *, entered_at=None, planned_at=None, actual_at=None):
    return SimpleNamespace(
        stage_order=order,
        status=status,
        entered_at=entered_at,
        planned_at=planned_at,
        actual_at=actual_at,
    )


class RiskScoringTest(SimpleTestCase):
    def test_no_active_stage_is_none(self):
        stages = [_stage(0, 'done'), _stage(1, 'pending')]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'none')
        self.assertEqual(risk['reasons'], [])

    def test_active_stage_without_dates_is_none(self):
        # 当前阶段、无 planned_at / entered_at —— 两个时间信号都跳过。
        stages = [_stage(0, 'done'), _stage(1, 'active')]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'none')

    def test_approaching_deadline_is_yellow(self):
        # planned_at 在 2 天后、无 dwell 数据 —— 仅临期信号 → 黄。
        stages = [
            _stage(0, 'done'),
            _stage(1, 'active', planned_at=NOW + timedelta(days=2)),
        ]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'yellow')
        self.assertIn('deadline_yellow', risk['reasons'])

    def test_far_future_deadline_is_none(self):
        stages = [
            _stage(0, 'done'),
            _stage(1, 'active', planned_at=NOW + timedelta(days=30)),
        ]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'none')

    def test_overdue_stage_is_red(self):
        stages = [
            _stage(0, 'done'),
            _stage(1, 'active', planned_at=NOW - timedelta(days=1)),
        ]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'red')
        self.assertIn('deadline_red', risk['reasons'])

    def test_dwell_red_when_far_over_planned_duration(self):
        # 上一阶段 20 天前完成，本阶段同时进入；计划时长 5 天，已停留 20 天
        # → 比值 4.0 > 1.5 → dwell_red（planned 也已过期 → deadline_red）。
        prev_done = NOW - timedelta(days=20)
        stages = [
            _stage(0, 'done', actual_at=prev_done),
            _stage(
                1,
                'active',
                entered_at=prev_done,
                planned_at=prev_done + timedelta(days=5),
            ),
        ]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'red')
        self.assertIn('dwell_red', risk['reasons'])

    def test_dwell_skipped_without_previous_actual(self):
        # 首阶段（无上一阶段 actual_at）—— dwell 信号跳过；planned 远期 → none。
        stages = [
            _stage(
                0,
                'active',
                entered_at=NOW - timedelta(days=99),
                planned_at=NOW + timedelta(days=30),
            ),
        ]
        risk = compute_project_risk(stages, now=NOW)
        self.assertEqual(risk['level'], 'none')

    def test_failed_materials_forces_red(self):
        stages = [_stage(0, 'done'), _stage(1, 'active')]
        risk = compute_project_risk(stages, has_failed_materials=True, now=NOW)
        self.assertEqual(risk['level'], 'red')
        self.assertIn('materials_failed', risk['reasons'])

    def test_higher_risk_wins_across_signals(self):
        # 临期黄 + 材料失败红 → 取红。
        stages = [
            _stage(0, 'done'),
            _stage(1, 'active', planned_at=NOW + timedelta(days=2)),
        ]
        risk = compute_project_risk(stages, has_failed_materials=True, now=NOW)
        self.assertEqual(risk['level'], 'red')
        self.assertIn('deadline_yellow', risk['reasons'])
        self.assertIn('materials_failed', risk['reasons'])
