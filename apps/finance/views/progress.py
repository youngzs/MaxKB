# coding=utf-8
"""
    @project: MaxKB
    @file： progress.py
    @desc: P2「进度归集」Gate 3/4 — 进度看板聚合端点。

    GET /workspace/<wid>/progress/gantt      Gantt 数据：项目 + 阶段记录 + 风险。
    GET /workspace/<wid>/progress/dashboard  驾驶舱聚合 KPI。

    （Gate 5 将在此文件追加 progress/alerts。）
"""
from collections import Counter
from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from finance.constants.stage_templates import get_stage
from finance.models import FinanceProject, MaterialsTask, ProjectStageRecord
from finance.models.project import FinanceProjectStatus
from finance.serializers.project import FinanceProjectOutputSerializer
from finance.serializers.project_stage_record import ProjectStageRecordOutputSerializer
from finance.service.risk import compute_project_risk


def _gather_projects(workspace_id, *, status='', project_type='', owner_id=''):
    """
    拉项目 + 各项目阶段记录 + 「有失败材料任务」的项目集合 —— 一次性查询，
    供 gantt / dashboard 共用，避免 N+1。
    """
    qs = FinanceProject.objects.filter(workspace_id=workspace_id, is_deleted=False)
    if status:
        qs = qs.filter(status=status)
    if project_type:
        qs = qs.filter(project_type=project_type)
    if owner_id:
        qs = qs.filter(owner_id=owner_id)
    projects = list(qs)
    project_ids = [p.id for p in projects]

    stages_by_project: dict = {}
    for row in ProjectStageRecord.objects.filter(
        project_id__in=project_ids
    ).order_by('project_id', 'stage_order'):
        stages_by_project.setdefault(row.project_id, []).append(row)

    failed_materials = set(
        MaterialsTask.objects.filter(
            project_id__in=project_ids, is_deleted=False, status='failed'
        ).values_list('project_id', flat=True)
    )
    return projects, stages_by_project, failed_materials


def _cycle_days(project, stages):
    """落地项目周期（天）= 阶段最大 actual_at − 项目 created_at；无数据返回 None。"""
    actuals = [s.actual_at for s in stages if s.actual_at]
    if not actuals:
        return None
    delta = (max(actuals) - project.created_at).total_seconds() / 86400
    return round(delta, 1) if delta >= 0 else None


class ProgressGanttView(APIView):
    """GET /workspace/<wid>/progress/gantt — 多项目 Gantt 数据（含运行时风险）。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Progress gantt data'),
        description=_('Project list with stage records and runtime risk for the gantt.'),
        operation_id=_('Progress gantt data'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        projects, stages_by_project, failed_materials = _gather_projects(
            workspace_id,
            status=(request.query_params.get('status') or '').strip(),
            project_type=(request.query_params.get('project_type') or '').strip(),
            owner_id=(request.query_params.get('owner_id') or '').strip(),
        )

        items = []
        for project in projects:
            rows = stages_by_project.get(project.id, [])
            stage_data = ProjectStageRecordOutputSerializer(rows, many=True).data
            for stage_item in stage_data:
                stage = get_stage(project.project_type, stage_item['stage_key'])
                stage_item['stage_label'] = (
                    stage.label if stage else stage_item['stage_key']
                )
            risk = compute_project_risk(
                rows, has_failed_materials=project.id in failed_materials
            )
            project_data = FinanceProjectOutputSerializer(project).data
            project_data['stages'] = stage_data
            project_data['risk'] = risk['level']
            project_data['risk_reasons'] = risk['reasons']
            items.append(project_data)

        return result.success({'projects': items})


class ProgressDashboardView(APIView):
    """GET /workspace/<wid>/progress/dashboard — 驾驶舱聚合 KPI（工作空间全量）。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('Progress dashboard'),
        description=_('Aggregate KPIs for the financing progress cockpit.'),
        operation_id=_('Progress dashboard'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        projects, stages_by_project, failed_materials = _gather_projects(workspace_id)

        in_flight = [
            p
            for p in projects
            if p.status
            not in (FinanceProjectStatus.LANDED, FinanceProjectStatus.TERMINATED)
        ]
        landed = [p for p in projects if p.status == FinanceProjectStatus.LANDED]
        terminated = [
            p for p in projects if p.status == FinanceProjectStatus.TERMINATED
        ]

        in_flight_amount = sum(
            (p.target_amount for p in in_flight if p.target_amount is not None),
            Decimal('0'),
        )

        decided = len(landed) + len(terminated)
        pass_rate = round(len(landed) / decided * 100, 1) if decided else None

        cycles = [
            c
            for c in (
                _cycle_days(p, stages_by_project.get(p.id, [])) for p in landed
            )
            if c is not None
        ]
        avg_cycle_days = round(sum(cycles) / len(cycles), 1) if cycles else None

        counter = Counter(p.counterparty for p in projects if p.counterparty)
        counterparty_share = [
            {'counterparty': name, 'count': cnt}
            for name, cnt in counter.most_common()
        ]

        risk_counter: Counter = Counter()
        for p in projects:
            risk = compute_project_risk(
                stages_by_project.get(p.id, []),
                has_failed_materials=p.id in failed_materials,
            )
            risk_counter[risk['level']] += 1

        return result.success(
            {
                'total_count': len(projects),
                'in_flight_count': len(in_flight),
                'in_flight_amount': str(in_flight_amount),
                'landed_count': len(landed),
                'terminated_count': len(terminated),
                'pass_rate': pass_rate,
                'avg_cycle_days': avg_cycle_days,
                'counterparty_share': counterparty_share,
                'risk': {
                    'yellow': risk_counter.get('yellow', 0),
                    'red': risk_counter.get('red', 0),
                },
            }
        )
