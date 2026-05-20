# coding=utf-8
"""
    @project: MaxKB
    @file： test_stage_progression.py
    @desc: P2「进度归集」Gate 2 测试 —— 阶段流转服务层
    （finance.service.stage_progression）。

    服务层 TestCase（需 DB）：覆盖预生成、推进、回退、边界与状态派生。
    视图层因 MaxKB 鉴权栈在 Windows dev 无法 import（见 test_project.py），
    与既有 finance 测试一致地只测服务层 —— Linux CI 可直接跑。
"""
import uuid

from django.test import TestCase
from django.utils import timezone

from common.exception.app_exception import AppApiException
from finance.constants.stage_templates import get_template, resolve_current_stage_key
from finance.models import (
    FinanceProject,
    FinanceProjectStatus,
    FinanceProjectType,
    ProjectStageRecord,
    ProjectStageStatus,
)
from finance.service.stage_progression import (
    advance_project_stage,
    pregenerate_stage_records,
    rollback_project_stage,
)


def _make_project_with_stages(*, project_type=FinanceProjectType.BANK_LOAN,
                               status=FinanceProjectStatus.PREPARING, **overrides):
    """复现创建视图：建项目 + 派生 current_stage_key + 预生成阶段行。"""
    # stage_plans 不是 FinanceProject 字段 —— 必须在 create() 之前摘出来。
    stage_plans = overrides.pop('stage_plans', None)
    project = FinanceProject.objects.create(
        workspace_id=overrides.pop('workspace_id', 'default'),
        name=overrides.pop('name', 'Stage Progression Project'),
        project_type=project_type,
        status=status,
        current_stage_key=resolve_current_stage_key(project_type, status),
        created_by=overrides.pop('created_by', uuid.uuid4()),
        **overrides,
    )
    pregenerate_stage_records(project, stage_plans=stage_plans)
    return project


def _rows(project):
    return list(
        ProjectStageRecord.objects.filter(project_id=project.id).order_by('stage_order')
    )


def _row(project, stage_key):
    return ProjectStageRecord.objects.get(project_id=project.id, stage_key=stage_key)


# --------------------------- pregenerate ---------------------------------


class PregenerateStageRecordsTest(TestCase):
    def test_creates_full_template_in_order(self):
        project = _make_project_with_stages(project_type=FinanceProjectType.ABS)
        rows = _rows(project)
        template = get_template('abs')
        self.assertEqual(len(rows), len(template))
        self.assertEqual(
            [r.stage_key for r in rows], [s.key for s in template]
        )
        self.assertEqual([r.stage_order for r in rows], list(range(len(template))))

    def test_preparing_project_has_intake_active_with_entered_at(self):
        project = _make_project_with_stages(status=FinanceProjectStatus.PREPARING)
        intake = _row(project, 'intake')
        self.assertEqual(intake.status, ProjectStageStatus.ACTIVE)
        self.assertIsNotNone(intake.entered_at)
        # 其余阶段 pending 且无 entered_at
        for row in _rows(project):
            if row.stage_key != 'intake':
                self.assertEqual(row.status, ProjectStageStatus.PENDING)
                self.assertIsNone(row.entered_at)

    def test_stage_plans_populate_planned_at(self):
        when = timezone.now()
        project = _make_project_with_stages(stage_plans={'due_diligence': when})
        self.assertEqual(_row(project, 'due_diligence').planned_at, when)
        self.assertIsNone(_row(project, 'intake').planned_at)

    def test_terminated_project_pregenerates_all_pending(self):
        project = _make_project_with_stages(status=FinanceProjectStatus.TERMINATED)
        rows = _rows(project)
        self.assertTrue(all(r.status == ProjectStageStatus.PENDING for r in rows))


# ----------------------------- advance -----------------------------------


class AdvanceProjectStageTest(TestCase):
    def test_advance_moves_current_and_next_rows(self):
        project = _make_project_with_stages()
        updated = advance_project_stage(project)
        # 项目层
        self.assertEqual(updated.current_stage_key, 'due_diligence')
        self.assertEqual(updated.status, FinanceProjectStatus.MATERIALS)
        # 阶段行
        intake = _row(project, 'intake')
        self.assertEqual(intake.status, ProjectStageStatus.DONE)
        self.assertIsNotNone(intake.actual_at)
        dd = _row(project, 'due_diligence')
        self.assertEqual(dd.status, ProjectStageStatus.ACTIVE)
        self.assertIsNotNone(dd.entered_at)

    def test_advance_derives_big_status_from_template(self):
        project = _make_project_with_stages()
        # intake(preparing) -> due_diligence(materials) -> materials_prep(materials)
        #   -> credit_committee(engaging)
        advance_project_stage(project)
        advance_project_stage(project)
        updated = advance_project_stage(project)
        self.assertEqual(updated.current_stage_key, 'credit_committee')
        self.assertEqual(updated.status, FinanceProjectStatus.ENGAGING)

    def test_advance_keeps_exactly_one_active_stage(self):
        project = _make_project_with_stages()
        advance_project_stage(project)
        advance_project_stage(project)
        active = ProjectStageRecord.objects.filter(
            project_id=project.id, status=ProjectStageStatus.ACTIVE
        )
        self.assertEqual(active.count(), 1)

    def test_advance_to_final_then_one_more_raises(self):
        project = _make_project_with_stages()
        # bank_loan 有 7 阶段（order 0..6）—— 6 次推进到末阶段。
        for _ in range(len(get_template('bank_loan')) - 1):
            project = advance_project_stage(project)
        self.assertEqual(project.current_stage_key, 'post_loan')
        with self.assertRaises(AppApiException):
            advance_project_stage(project)

    def test_advance_terminated_project_raises(self):
        project = _make_project_with_stages(status=FinanceProjectStatus.TERMINATED)
        with self.assertRaises(AppApiException):
            advance_project_stage(project)


# ----------------------------- rollback ----------------------------------


class RollbackProjectStageTest(TestCase):
    def test_rollback_returns_to_previous_stage(self):
        project = _make_project_with_stages()
        advance_project_stage(project)  # -> due_diligence
        updated = rollback_project_stage(project)
        self.assertEqual(updated.current_stage_key, 'intake')
        self.assertEqual(updated.status, FinanceProjectStatus.PREPARING)
        # due_diligence 退回未开始
        dd = _row(project, 'due_diligence')
        self.assertEqual(dd.status, ProjectStageStatus.PENDING)
        self.assertIsNone(dd.entered_at)
        # intake 重新进行中，actual_at 清空
        intake = _row(project, 'intake')
        self.assertEqual(intake.status, ProjectStageStatus.ACTIVE)
        self.assertIsNone(intake.actual_at)
        self.assertIsNotNone(intake.entered_at)

    def test_rollback_writes_note_onto_reactivated_stage(self):
        project = _make_project_with_stages()
        advance_project_stage(project)
        rollback_project_stage(project, note='材料被打回，需补充')
        self.assertEqual(_row(project, 'intake').note, '材料被打回，需补充')

    def test_rollback_at_first_stage_raises(self):
        project = _make_project_with_stages()
        with self.assertRaises(AppApiException):
            rollback_project_stage(project)

    def test_rollback_terminated_project_raises(self):
        project = _make_project_with_stages(status=FinanceProjectStatus.TERMINATED)
        with self.assertRaises(AppApiException):
            rollback_project_stage(project)


# --------------------------- round trip ----------------------------------


class StageRoundTripTest(TestCase):
    def test_advance_then_rollback_restores_status_and_pointer(self):
        project = _make_project_with_stages(project_type=FinanceProjectType.BOND)
        original_key = project.current_stage_key
        original_status = project.status
        advanced = advance_project_stage(project)
        self.assertNotEqual(advanced.current_stage_key, original_key)
        restored = rollback_project_stage(advanced)
        self.assertEqual(restored.current_stage_key, original_key)
        self.assertEqual(restored.status, original_status)
        # 仍恰有一个 active 阶段
        active = ProjectStageRecord.objects.filter(
            project_id=project.id, status=ProjectStageStatus.ACTIVE
        )
        self.assertEqual(active.count(), 1)
