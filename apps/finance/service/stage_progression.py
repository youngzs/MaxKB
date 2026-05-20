# coding=utf-8
"""
    @project: MaxKB
    @file： stage_progression.py
    @desc: P2「进度归集」Gate 2 — 阶段流转服务层。

    封装融资项目子阶段的三类写操作：
      - pregenerate_stage_records  项目创建时按类型模板预生成全部阶段行；
      - advance_project_stage      推进到下一阶段；
      - rollback_project_stage     回退到上一阶段。

    设计要点（见 docs/finance-p2-progress-design.md §4.6）：
      - `ProjectStageRecord` 维持「每阶段恰一行」—— advance / rollback 都**就地
        改**这 N 行，不追加历史行（2026-05-20 评审确认）。回退的 who/when/
        from→to/原因 由 view 层的 @audit_log 写入 FinanceAuditLog 留痕。
      - 大状态 `FinanceProject.status` 由 `current_stage_key` 的 `maps_to_status`
        派生 —— 流转时一并更新，消除两套状态打架。
      - 不允许跳跃式跨阶段：advance/rollback 每次只动一格。
      - 写操作在 transaction.atomic + select_for_update 下进行，避免并发串台。
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from common.exception.app_exception import AppApiException
from finance.constants.stage_templates import (
    build_initial_stage_plan,
    get_stage,
    get_template,
)
from finance.models import FinanceProject, ProjectStageRecord, ProjectStageStatus
from finance.models.project import FinanceProjectStatus


def pregenerate_stage_records(project: FinanceProject, *, stage_plans: dict | None = None):
    """
    项目创建后按类型模板预生成全部阶段行。

    `stage_plans` —— `{stage_key: planned_at}`，业务手填的计划完成时间
    （DR-P2-04），缺省为空。当前阶段（按 project.status 反查）的行写入
    `entered_at`，其余留空。
    """
    plans = stage_plans or {}
    now = timezone.now()
    records = [
        ProjectStageRecord(
            workspace_id=project.workspace_id,
            project_id=project.id,
            stage_key=item['stage_key'],
            stage_order=item['stage_order'],
            planned_at=plans.get(item['stage_key']),
            entered_at=now if item['stage_status'] == ProjectStageStatus.ACTIVE else None,
            status=item['stage_status'],
        )
        for item in build_initial_stage_plan(project.project_type, project.status)
    ]
    ProjectStageRecord.objects.bulk_create(records)
    return records


def _stage_row(project_id, stage_key: str) -> ProjectStageRecord:
    """取某项目某子阶段的记录行（须在 transaction.atomic 内调用 —— 带行锁）。"""
    row = (
        ProjectStageRecord.objects.select_for_update()
        .filter(project_id=project_id, stage_key=stage_key)
        .order_by('stage_order')
        .first()
    )
    if row is None:
        raise AppApiException(
            500, _('Stage record missing for stage: %(key)s') % {'key': stage_key}
        )
    return row


def advance_project_stage(project: FinanceProject, *, note: str = '') -> FinanceProject:
    """
    推进到下一个子阶段：当前阶段 → done(+actual_at)，下一阶段 → active(+entered_at)，
    项目 current_stage_key / status 一并更新。返回更新后的项目。
    """
    if project.status == FinanceProjectStatus.TERMINATED:
        raise AppApiException(400, _('A terminated project cannot be advanced'))
    current = get_stage(project.project_type, project.current_stage_key)
    if current is None:
        raise AppApiException(400, _('Project has no resolvable current stage'))
    template = get_template(project.project_type)
    next_order = current.order + 1
    if next_order >= len(template):
        raise AppApiException(400, _('Project is already at the final stage'))
    next_stage = template[next_order]
    now = timezone.now()

    with transaction.atomic():
        locked = FinanceProject.objects.select_for_update().get(id=project.id)
        cur_row = _stage_row(locked.id, current.key)
        nxt_row = _stage_row(locked.id, next_stage.key)

        cur_row.status = ProjectStageStatus.DONE
        cur_row.actual_at = now
        cur_row.save(update_fields=['status', 'actual_at', 'updated_at'])

        nxt_row.status = ProjectStageStatus.ACTIVE
        nxt_row.entered_at = now
        if note:
            nxt_row.note = note
        nxt_row.save(update_fields=['status', 'entered_at', 'note', 'updated_at'])

        locked.current_stage_key = next_stage.key
        locked.status = next_stage.maps_to_status
        locked.save(update_fields=['current_stage_key', 'status', 'updated_at'])
    return locked


def rollback_project_stage(project: FinanceProject, *, note: str = '') -> FinanceProject:
    """
    回退到上一个子阶段：当前阶段 → pending（清 entered_at），上一阶段重新
    active（+entered_at、清 actual_at），项目 current_stage_key / status 一并更新。
    `note` 写入被重新激活的上一阶段行的备注（回退原因）。返回更新后的项目。
    """
    if project.status == FinanceProjectStatus.TERMINATED:
        raise AppApiException(400, _('A terminated project cannot be rolled back'))
    current = get_stage(project.project_type, project.current_stage_key)
    if current is None:
        raise AppApiException(400, _('Project has no resolvable current stage'))
    prev_order = current.order - 1
    if prev_order < 0:
        raise AppApiException(400, _('Project is already at the first stage'))
    prev_stage = get_template(project.project_type)[prev_order]
    now = timezone.now()

    with transaction.atomic():
        locked = FinanceProject.objects.select_for_update().get(id=project.id)
        cur_row = _stage_row(locked.id, current.key)
        prev_row = _stage_row(locked.id, prev_stage.key)

        cur_row.status = ProjectStageStatus.PENDING
        cur_row.entered_at = None
        cur_row.actual_at = None
        cur_row.save(
            update_fields=['status', 'entered_at', 'actual_at', 'updated_at']
        )

        prev_row.status = ProjectStageStatus.ACTIVE
        prev_row.entered_at = now
        prev_row.actual_at = None
        if note:
            prev_row.note = note
        prev_row.save(
            update_fields=['status', 'entered_at', 'actual_at', 'note', 'updated_at']
        )

        locked.current_stage_key = prev_stage.key
        locked.status = prev_stage.maps_to_status
        locked.save(update_fields=['current_stage_key', 'status', 'updated_at'])
    return locked
