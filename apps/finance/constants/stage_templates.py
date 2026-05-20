# coding=utf-8
"""
    @project: MaxKB
    @file： stage_templates.py
    @desc: P2「进度归集」Gate 1 — 融资项目子阶段模板常量。

    每个 FinanceProjectType 对应一套有序子阶段（DR-P2-01「固定子阶段模板」）。
      - `stage_key`        稳定标识，写入 DB、**不可改名**。
      - `label`            中文阶段名，后续可 i18n。
      - `maps_to_status`   把子阶段映射回 FinanceProject 现有扁平 5 态大状态，
                           保证 P0/P1 兼容 —— 大状态由 current_stage_key 派生。

    见 docs/finance-p2-progress-design.md §四。终止态 `terminated` 是横切状态，
    不在任何子阶段序列里，故不会作为 maps_to_status 出现。

    本模块为纯数据 + 纯函数，**不导入 finance.models** —— 数据迁移 0009 的
    RunPython 回填逻辑直接复用此处的 resolve_current_stage_key / build_initial_stage_plan。
"""
from typing import NamedTuple, Optional


class StageDef(NamedTuple):
    """单个子阶段定义。`order` 为 0 起的序号（DB 排序键 stage_order）。"""

    key: str
    label: str
    maps_to_status: str
    order: int


# 横切终止态 —— 不出现在任何模板序列里。
TERMINATED_STATUS = 'terminated'

# project_type -> 有序 (stage_key, label, maps_to_status) 序列。
# 顺序即业务流转顺序；改动 = 改常量 + 配套迁移，不是热配置（见设计文档 §十）。
_RAW_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    'bank_loan': [
        ('intake', '立项受理', 'preparing'),
        ('due_diligence', '尽职调查', 'materials'),
        ('materials_prep', '授信材料准备', 'materials'),
        ('credit_committee', '审贷会', 'engaging'),
        ('approval', '批复', 'engaging'),
        ('disbursement', '放款', 'landed'),
        ('post_loan', '贷后管理', 'landed'),
    ],
    'bond': [
        ('intake', '立项受理', 'preparing'),
        ('due_diligence', '尽职调查与申报材料', 'materials'),
        ('regulatory_filing', '监管申报/注册', 'engaging'),
        ('issuance_prep', '发行准备', 'engaging'),
        ('bookbuilding', '簿记发行', 'engaging'),
        ('listing', '上市/登记', 'landed'),
        ('duration_mgmt', '存续期管理', 'landed'),
    ],
    'trust': [
        ('intake', '立项受理', 'preparing'),
        ('due_diligence', '尽职调查', 'materials'),
        ('risk_approval', '风控审批', 'engaging'),
        ('plan_setup', '计划设立', 'engaging'),
        ('fundraising', '募集', 'engaging'),
        ('established', '成立', 'landed'),
        ('duration_mgmt', '存续期管理', 'landed'),
    ],
    'abs': [
        ('intake', '立项受理', 'preparing'),
        ('asset_screening', '基础资产筛选与尽调', 'materials'),
        ('structuring', '交易结构设计', 'engaging'),
        ('rating_filing', '评级与申报', 'engaging'),
        ('issuance', '发行', 'engaging'),
        ('listing', '挂牌', 'landed'),
        ('duration_mgmt', '存续期管理', 'landed'),
    ],
    'other': [
        ('intake', '立项', 'preparing'),
        ('preparation', '准备', 'materials'),
        ('execution', '推进', 'engaging'),
        ('landed', '落地', 'landed'),
        ('follow_up', '后续管理', 'landed'),
    ],
}

# 对外只读视图：project_type -> (StageDef, ...) 不可变元组。
STAGE_TEMPLATES: dict[str, tuple[StageDef, ...]] = {
    project_type: tuple(
        StageDef(key=key, label=label, maps_to_status=maps_to_status, order=order)
        for order, (key, label, maps_to_status) in enumerate(stages)
    )
    for project_type, stages in _RAW_TEMPLATES.items()
}

# 子阶段记录状态 —— 与 ProjectStageRecord.ProjectStageStatus 的取值保持一致。
# 此处用字面量以保持本模块零 finance.models 依赖（迁移可安全导入）。
STAGE_STATUS_PENDING = 'pending'
STAGE_STATUS_ACTIVE = 'active'
STAGE_STATUS_DONE = 'done'
STAGE_STATUS_SKIPPED = 'skipped'


def get_template(project_type: str) -> tuple[StageDef, ...]:
    """返回某项目类型的有序子阶段模板；未知类型回退到 `other`（防御性）。"""
    return STAGE_TEMPLATES.get(project_type) or STAGE_TEMPLATES['other']


def get_stage(project_type: str, stage_key: str) -> Optional[StageDef]:
    """按 stage_key 取单个子阶段定义；不存在返回 None。"""
    for stage in get_template(project_type):
        if stage.key == stage_key:
            return stage
    return None


def resolve_current_stage_key(project_type: str, status: str) -> str:
    """
    把扁平大状态反查为「该状态下第一个子阶段」的 key（迁移回填用）。

    `terminated` 是横切态、无对应子阶段 —— 返回 ''；任何无法匹配的状态同样
    返回 ''。业务可在迁移后手工校正（见设计文档 §十）。
    """
    if status == TERMINATED_STATUS:
        return ''
    for stage in get_template(project_type):
        if stage.maps_to_status == status:
            return stage.key
    return ''


def build_initial_stage_plan(project_type: str, status: str) -> list[dict]:
    """
    为一个项目预生成全部阶段行的计划，返回有序 list of
    `{stage_key, stage_order, stage_status}`。

    定位规则（基于扁平大状态反查出的当前阶段）：
      - 当前阶段**之前** → done
      - 当前阶段        → active
      - 当前阶段**之后** → pending
      - `terminated` 或无法定位当前阶段 → 全部 pending

    用于：迁移回填存量项目；Gate 2 创建新项目时预生成阶段行（status=preparing
    时即「intake active，其余 pending」）。
    """
    template = get_template(project_type)
    current_key = resolve_current_stage_key(project_type, status)

    current_order: Optional[int] = None
    if current_key:
        current_stage = get_stage(project_type, current_key)
        if current_stage is not None:
            current_order = current_stage.order

    plan: list[dict] = []
    for stage in template:
        if current_order is None:
            stage_status = STAGE_STATUS_PENDING
        elif stage.order < current_order:
            stage_status = STAGE_STATUS_DONE
        elif stage.order == current_order:
            stage_status = STAGE_STATUS_ACTIVE
        else:
            stage_status = STAGE_STATUS_PENDING
        plan.append(
            {
                'stage_key': stage.key,
                'stage_order': stage.order,
                'stage_status': stage_status,
            }
        )
    return plan
