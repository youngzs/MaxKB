# coding=utf-8
"""
    @project: MaxKB
    @file： test_stage_templates.py
    @desc: P2「进度归集」Gate 1 测试 —— 阶段模板常量完整性 + 回填逻辑纯函数。

    全部为 SimpleTestCase（不碰数据库）：被测对象是 finance.constants.stage_templates
    里的纯数据与纯函数。迁移 0009 的 RunPython 回填直接复用这些函数，因此本文件
    即覆盖了「迁移回填逻辑」。
"""
from django.test import SimpleTestCase

from finance.constants.stage_templates import (
    STAGE_TEMPLATES,
    build_initial_stage_plan,
    get_stage,
    get_template,
    resolve_current_stage_key,
)
from finance.models import FinanceProjectStatus, FinanceProjectType, ProjectStageStatus

# 设计文档 §四锁定的每类型子阶段数。
_EXPECTED_STAGE_COUNT = {
    'bank_loan': 7,
    'bond': 7,
    'trust': 7,
    'abs': 7,
    'other': 5,
}
# maps_to_status 合法取值 —— 横切态 terminated 不会作为映射目标出现。
_VALID_MAPPED_STATUSES = {
    s for s in FinanceProjectStatus.values if s != FinanceProjectStatus.TERMINATED
}
_VALID_STAGE_STATUSES = set(ProjectStageStatus.values)


class StageTemplateIntegrityTest(SimpleTestCase):
    """模板结构完整性 —— 锁定设计文档 §四的五套模板。"""

    def test_covers_every_project_type(self):
        self.assertEqual(
            set(STAGE_TEMPLATES.keys()), set(FinanceProjectType.values)
        )

    def test_stage_counts_match_spec(self):
        for project_type, expected in _EXPECTED_STAGE_COUNT.items():
            self.assertEqual(
                len(STAGE_TEMPLATES[project_type]),
                expected,
                msg=f'{project_type} 子阶段数应为 {expected}',
            )

    def test_orders_are_zero_based_and_sequential(self):
        for project_type, template in STAGE_TEMPLATES.items():
            orders = [stage.order for stage in template]
            self.assertEqual(
                orders,
                list(range(len(template))),
                msg=f'{project_type} 的 order 应为 0..n-1 连续序列',
            )

    def test_stage_keys_unique_within_template(self):
        for project_type, template in STAGE_TEMPLATES.items():
            keys = [stage.key for stage in template]
            self.assertEqual(
                len(keys), len(set(keys)), msg=f'{project_type} 内 stage_key 不可重复'
            )

    def test_first_stage_is_intake(self):
        for project_type, template in STAGE_TEMPLATES.items():
            self.assertEqual(
                template[0].key, 'intake', msg=f'{project_type} 首阶段应为 intake'
            )

    def test_maps_to_status_are_valid_non_terminated(self):
        for project_type, template in STAGE_TEMPLATES.items():
            for stage in template:
                self.assertIn(
                    stage.maps_to_status,
                    _VALID_MAPPED_STATUSES,
                    msg=f'{project_type}/{stage.key} 的 maps_to_status 非法',
                )

    def test_maps_to_status_is_monotonic(self):
        # 子阶段顺序前进时，对应大状态不应「倒退」—— 保证 status 派生单调。
        status_rank = {
            FinanceProjectStatus.PREPARING: 0,
            FinanceProjectStatus.MATERIALS: 1,
            FinanceProjectStatus.ENGAGING: 2,
            FinanceProjectStatus.LANDED: 3,
        }
        for project_type, template in STAGE_TEMPLATES.items():
            ranks = [status_rank[stage.maps_to_status] for stage in template]
            self.assertEqual(
                ranks,
                sorted(ranks),
                msg=f'{project_type} 的 maps_to_status 应随阶段顺序单调不减',
            )

    def test_labels_non_empty(self):
        for template in STAGE_TEMPLATES.values():
            for stage in template:
                self.assertTrue(stage.label.strip())


class TemplateHelperTest(SimpleTestCase):
    """get_template / get_stage 行为。"""

    def test_get_template_returns_known_type(self):
        self.assertEqual(get_template('bond'), STAGE_TEMPLATES['bond'])

    def test_get_template_unknown_falls_back_to_other(self):
        self.assertEqual(get_template('not_a_type'), STAGE_TEMPLATES['other'])

    def test_get_stage_found(self):
        stage = get_stage('bank_loan', 'disbursement')
        self.assertIsNotNone(stage)
        self.assertEqual(stage.label, '放款')
        self.assertEqual(stage.maps_to_status, 'landed')

    def test_get_stage_missing_returns_none(self):
        self.assertIsNone(get_stage('bank_loan', 'no_such_stage'))


class ResolveCurrentStageKeyTest(SimpleTestCase):
    """扁平大状态 → 首个子阶段 key 的反查（迁移回填核心）。"""

    def test_preparing_maps_to_intake_for_every_type(self):
        for project_type in STAGE_TEMPLATES:
            self.assertEqual(
                resolve_current_stage_key(project_type, 'preparing'), 'intake'
            )

    def test_materials_maps_to_first_materials_stage(self):
        # bank_loan 下 materials 段第一个是 due_diligence（materials_prep 同段但靠后）。
        self.assertEqual(
            resolve_current_stage_key('bank_loan', 'materials'), 'due_diligence'
        )

    def test_engaging_maps_to_first_engaging_stage(self):
        self.assertEqual(
            resolve_current_stage_key('bank_loan', 'engaging'), 'credit_committee'
        )

    def test_landed_maps_to_first_landed_stage(self):
        self.assertEqual(
            resolve_current_stage_key('bank_loan', 'landed'), 'disbursement'
        )

    def test_terminated_resolves_to_empty(self):
        for project_type in STAGE_TEMPLATES:
            self.assertEqual(
                resolve_current_stage_key(project_type, 'terminated'), ''
            )

    def test_resolved_key_actually_maps_back_to_status(self):
        # 反查得到的 key，其 maps_to_status 必须等于输入的大状态。
        for project_type in STAGE_TEMPLATES:
            for status in _VALID_MAPPED_STATUSES:
                key = resolve_current_stage_key(project_type, status)
                self.assertTrue(key, msg=f'{project_type}/{status} 应能反查到子阶段')
                self.assertEqual(get_stage(project_type, key).maps_to_status, status)


class BuildInitialStagePlanTest(SimpleTestCase):
    """预生成阶段行计划 —— 迁移回填与 Gate 2 创建项目共用。"""

    def test_plan_covers_full_template_in_order(self):
        for project_type, template in STAGE_TEMPLATES.items():
            plan = build_initial_stage_plan(project_type, 'preparing')
            self.assertEqual(len(plan), len(template))
            self.assertEqual(
                [item['stage_key'] for item in plan],
                [stage.key for stage in template],
            )
            self.assertEqual(
                [item['stage_order'] for item in plan],
                [stage.order for stage in template],
            )

    def test_plan_stage_statuses_are_valid(self):
        for project_type in STAGE_TEMPLATES:
            for status in FinanceProjectStatus.values:
                for item in build_initial_stage_plan(project_type, status):
                    self.assertIn(item['stage_status'], _VALID_STAGE_STATUSES)

    def test_preparing_makes_intake_active_rest_pending(self):
        plan = build_initial_stage_plan('bank_loan', 'preparing')
        self.assertEqual(plan[0]['stage_status'], 'active')
        self.assertTrue(all(p['stage_status'] == 'pending' for p in plan[1:]))

    def test_non_terminated_has_exactly_one_active_stage(self):
        for project_type in STAGE_TEMPLATES:
            for status in ('preparing', 'materials', 'engaging', 'landed'):
                plan = build_initial_stage_plan(project_type, status)
                active = [p for p in plan if p['stage_status'] == 'active']
                self.assertEqual(
                    len(active), 1, msg=f'{project_type}/{status} 应恰有 1 个 active 阶段'
                )

    def test_stages_before_active_are_done_after_are_pending(self):
        # bank_loan / engaging：current = credit_committee (order 3)。
        plan = build_initial_stage_plan('bank_loan', 'engaging')
        statuses = [p['stage_status'] for p in plan]
        self.assertEqual(
            statuses,
            ['done', 'done', 'done', 'active', 'pending', 'pending', 'pending'],
        )

    def test_terminated_makes_every_stage_pending(self):
        for project_type, template in STAGE_TEMPLATES.items():
            plan = build_initial_stage_plan(project_type, 'terminated')
            self.assertEqual(len(plan), len(template))
            self.assertTrue(all(p['stage_status'] == 'pending' for p in plan))
