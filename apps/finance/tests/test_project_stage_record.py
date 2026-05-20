# coding=utf-8
"""
    @project: MaxKB
    @file： test_project_stage_record.py
    @desc: P2「进度归集」Gate 1 测试 —— ProjectStageRecord 模型层 +
    迁移 0009 回填逻辑的端到端验证。

    Why model-level (not view-level)? 同 test_project.py：Windows dev 无法 import
    完整 app 栈（models_provider 依赖 POSIX-only `pwd`）。Linux CI 可直接跑，
    并会额外验证 0009 迁移本身。

    回填本身是 RunPython，难以脱离迁移框架直接调；本文件用相同的纯函数
    （build_initial_stage_plan / resolve_current_stage_key）+ ORM 复现迁移行为，
    确保「项目 → 阶段记录」的回填结果一致、可在 CI 跑。
"""
import uuid

from django.test import TestCase

from finance.constants.stage_templates import (
    build_initial_stage_plan,
    get_template,
    resolve_current_stage_key,
)
from finance.models import (
    FinanceProject,
    FinanceProjectStatus,
    FinanceProjectType,
    ProjectStageRecord,
    ProjectStageStatus,
)


# --------------------------- Model layer ---------------------------------


class ProjectStageRecordModelTest(TestCase):
    def setUp(self):
        self.workspace_id = 'default'
        self.project_id = uuid.uuid4()

    def _make(self, **overrides):
        defaults = dict(
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            stage_key='intake',
            stage_order=0,
        )
        defaults.update(overrides)
        return ProjectStageRecord.objects.create(**defaults)

    def test_create_with_minimum_fields_uses_defaults(self):
        record = self._make()
        self.assertEqual(record.status, ProjectStageStatus.PENDING)
        self.assertIsNone(record.planned_at)
        self.assertIsNone(record.actual_at)
        self.assertIsNone(record.owner_id)
        self.assertIsNone(record.entered_at)
        self.assertEqual(record.note, '')
        self.assertIsNotNone(record.created_at)
        self.assertIsNotNone(record.updated_at)

    def test_default_ordering_by_project_then_stage_order(self):
        self._make(stage_key='c', stage_order=2)
        self._make(stage_key='a', stage_order=0)
        self._make(stage_key='b', stage_order=1)
        orders = list(
            ProjectStageRecord.objects.filter(project_id=self.project_id).values_list(
                'stage_order', flat=True
            )
        )
        self.assertEqual(orders, [0, 1, 2])

    def test_rollback_history_allows_repeated_stage_key(self):
        # 回退会追加同一 stage_key 的新记录留痕 —— 不应有唯一约束阻止。
        self._make(stage_key='due_diligence', stage_order=1, status='active')
        self._make(stage_key='due_diligence', stage_order=1, status='active')
        count = ProjectStageRecord.objects.filter(
            project_id=self.project_id, stage_key='due_diligence'
        ).count()
        self.assertEqual(count, 2)

    def test_str_includes_stage_and_status(self):
        record = self._make(stage_key='approval', status='done')
        self.assertIn('approval', str(record))
        self.assertIn('done', str(record))


# --------------------- FinanceProject progress fields --------------------


class FinanceProjectProgressFieldsTest(TestCase):
    def test_new_progress_fields_have_expected_defaults(self):
        project = FinanceProject.objects.create(
            workspace_id='default',
            name='进度字段默认值',
            project_type=FinanceProjectType.BOND,
            created_by=uuid.uuid4(),
        )
        self.assertIsNone(project.owner_id)
        self.assertEqual(project.counterparty, '')
        self.assertEqual(project.current_stage_key, '')


# ----------------------- Backfill behavior (0009) ------------------------


class StageBackfillBehaviorTest(TestCase):
    """复现迁移 0009 的回填：项目进度字段 + 预生成阶段行。"""

    def _make_project(self, **overrides):
        defaults = dict(
            workspace_id='default',
            name='Backfill 项目',
            project_type=FinanceProjectType.BANK_LOAN,
            status=FinanceProjectStatus.PREPARING,
            created_by=uuid.uuid4(),
        )
        defaults.update(overrides)
        return FinanceProject.objects.create(**defaults)

    def _backfill(self, project):
        """与迁移 0009 _backfill_progress 等价的单项目回填。"""
        entered_estimate = project.updated_at
        if project.owner_id is None:
            project.owner_id = project.created_by
        project.current_stage_key = resolve_current_stage_key(
            project.project_type, project.status
        )
        project.save(update_fields=['owner_id', 'current_stage_key'])

        records = []
        for item in build_initial_stage_plan(project.project_type, project.status):
            is_active = item['stage_status'] == 'active'
            records.append(
                ProjectStageRecord(
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    stage_key=item['stage_key'],
                    stage_order=item['stage_order'],
                    entered_at=entered_estimate if is_active else None,
                    status=item['stage_status'],
                )
            )
        ProjectStageRecord.objects.bulk_create(records)

    def test_backfill_sets_owner_to_created_by(self):
        project = self._make_project()
        self._backfill(project)
        project.refresh_from_db()
        self.assertEqual(project.owner_id, project.created_by)

    def test_backfill_does_not_override_existing_owner(self):
        explicit_owner = uuid.uuid4()
        project = self._make_project(owner_id=explicit_owner)
        self._backfill(project)
        project.refresh_from_db()
        self.assertEqual(project.owner_id, explicit_owner)

    def test_backfill_derives_current_stage_key_from_status(self):
        project = self._make_project(status=FinanceProjectStatus.ENGAGING)
        self._backfill(project)
        project.refresh_from_db()
        self.assertEqual(project.current_stage_key, 'credit_committee')

    def test_backfill_terminated_project_has_blank_stage_key(self):
        project = self._make_project(status=FinanceProjectStatus.TERMINATED)
        self._backfill(project)
        project.refresh_from_db()
        self.assertEqual(project.current_stage_key, '')

    def test_backfill_pregenerates_full_template(self):
        project = self._make_project(project_type=FinanceProjectType.ABS)
        self._backfill(project)
        records = ProjectStageRecord.objects.filter(project_id=project.id)
        self.assertEqual(records.count(), len(get_template('abs')))
        self.assertEqual(
            list(records.values_list('stage_key', flat=True)),
            [stage.key for stage in get_template('abs')],
        )

    def test_backfill_active_stage_matches_current_stage_key(self):
        project = self._make_project(status=FinanceProjectStatus.MATERIALS)
        self._backfill(project)
        project.refresh_from_db()
        active = ProjectStageRecord.objects.filter(
            project_id=project.id, status=ProjectStageStatus.ACTIVE
        )
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().stage_key, project.current_stage_key)

    def test_backfill_active_stage_gets_entered_at_others_null(self):
        project = self._make_project(status=FinanceProjectStatus.ENGAGING)
        self._backfill(project)
        for record in ProjectStageRecord.objects.filter(project_id=project.id):
            if record.status == ProjectStageStatus.ACTIVE:
                self.assertIsNotNone(record.entered_at)
            else:
                self.assertIsNone(record.entered_at)

    def test_backfill_stage_records_carry_workspace(self):
        project = self._make_project(workspace_id='ws-xyz')
        self._backfill(project)
        records = ProjectStageRecord.objects.filter(project_id=project.id)
        self.assertTrue(all(r.workspace_id == 'ws-xyz' for r in records))

    def test_backfill_pregenerated_owner_is_null_inherits_project(self):
        # 阶段级 owner_id 留空 —— 运行时继承项目 owner（DR-P2-03）。
        project = self._make_project()
        self._backfill(project)
        records = ProjectStageRecord.objects.filter(project_id=project.id)
        self.assertTrue(all(r.owner_id is None for r in records))
