# coding=utf-8
"""
    @project: MaxKB
    @file： project_stage.py
    @desc: P2「进度归集」Gate 2 — 阶段流转 REST 端点。

    路由（全部挂在 /workspace/<wid>/project/<pk>/ 下）：
      GET   /stages               单项目全部阶段记录（按 stage_order 排序）
      PUT   /stages/<stage_key>   改单个子阶段 planned_at / owner_id / note
      POST  /advance              推进到下一阶段
      POST  /rollback             回退到上一阶段

    权限：读用 FINANCE_READ，推进/回退/改阶段用 FINANCE_EDIT。
    流转/改阶段写操作均挂 @audit_log（target_type=PROJECT，action=UPDATE）——
    回退的留痕即由此进入 FinanceAuditLog（见 stage_progression.py 设计说明）。
"""
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from common import result
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants
from common.exception.app_exception import NotFound404
from finance.constants.stage_templates import STAGE_TEMPLATES, get_stage
from finance.models import (
    FinanceAuditAction,
    FinanceAuditTargetType,
    FinanceProject,
    ProjectStageRecord,
)
from finance.serializers.project import FinanceProjectOutputSerializer
from finance.serializers.project_stage import (
    ProjectStageUpdateSerializer,
    StageTransitionSerializer,
)
from finance.serializers.project_stage_record import ProjectStageRecordOutputSerializer
from finance.service.audit import audit_log
from finance.service.stage_progression import (
    advance_project_stage,
    rollback_project_stage,
)


def _project_or_404(workspace_id, pk) -> FinanceProject:
    project = FinanceProject.objects.filter(
        id=pk, workspace_id=workspace_id, is_deleted=False
    ).first()
    if project is None:
        raise NotFound404(404, _('Project not found'))
    return project


def _serialize_stages(project: FinanceProject) -> list:
    """单项目全部阶段记录，按 stage_order 排序，附带模板派生的 stage_label。"""
    rows = ProjectStageRecord.objects.filter(project_id=project.id).order_by(
        'stage_order'
    )
    data = ProjectStageRecordOutputSerializer(rows, many=True).data
    for item in data:
        stage = get_stage(project.project_type, item['stage_key'])
        item['stage_label'] = stage.label if stage else item['stage_key']
    return data


class ProjectStagesView(APIView):
    """GET /project/<pk>/stages — 单项目全部阶段记录。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List project stages'),
        description=_('List all stage records of a finance project, ordered by stage.'),
        operation_id=_('List project stages'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id, pk):
        project = _project_or_404(workspace_id, pk)
        return result.success(_serialize_stages(project))


class ProjectStageDetailView(APIView):
    """PUT /project/<pk>/stages/<stage_key> — 改单个子阶段元数据。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['PUT'],
        summary=_('Update project stage'),
        description=_('Update planned_at / owner_id / note of one stage.'),
        operation_id=_('Update project stage'),  # type: ignore
        request=ProjectStageUpdateSerializer,
        responses=ProjectStageRecordOutputSerializer,
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.PROJECT)
    def put(self, request: Request, workspace_id, pk, stage_key):
        project = _project_or_404(workspace_id, pk)
        if get_stage(project.project_type, stage_key) is None:
            raise NotFound404(404, _('Stage not found in the project template'))
        row = (
            ProjectStageRecord.objects.filter(
                project_id=project.id, stage_key=stage_key
            )
            .order_by('stage_order')
            .first()
        )
        if row is None:
            raise NotFound404(404, _('Stage record not found'))

        body = ProjectStageUpdateSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        payload = body.validated_data

        update_fields: list[str] = []
        if 'planned_at' in payload:
            row.planned_at = payload['planned_at']
            update_fields.append('planned_at')
        if 'owner_id' in payload:
            row.owner_id = payload['owner_id']
            update_fields.append('owner_id')
        if 'note' in payload:
            row.note = payload['note']
            update_fields.append('note')
        if update_fields:
            update_fields.append('updated_at')
            row.save(update_fields=update_fields)
        return result.success(ProjectStageRecordOutputSerializer(row).data)


class ProjectStageAdvanceView(APIView):
    """POST /project/<pk>/advance — 推进到下一阶段。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Advance project stage'),
        description=_('Advance a project to the next sub-stage.'),
        operation_id=_('Advance project stage'),  # type: ignore
        request=StageTransitionSerializer,
        responses=FinanceProjectOutputSerializer,
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.PROJECT)
    def post(self, request: Request, workspace_id, pk):
        project = _project_or_404(workspace_id, pk)
        body = StageTransitionSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        project = advance_project_stage(
            project, note=body.validated_data.get('note') or ''
        )
        return result.success(FinanceProjectOutputSerializer(project).data)


class ProjectStageRollbackView(APIView):
    """POST /project/<pk>/rollback — 回退到上一阶段。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['POST'],
        summary=_('Roll back project stage'),
        description=_('Roll a project back to the previous sub-stage.'),
        operation_id=_('Roll back project stage'),  # type: ignore
        request=StageTransitionSerializer,
        responses=FinanceProjectOutputSerializer,
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_EDIT.get_workspace_permission(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    @audit_log(action=FinanceAuditAction.UPDATE, target_type=FinanceAuditTargetType.PROJECT)
    def post(self, request: Request, workspace_id, pk):
        project = _project_or_404(workspace_id, pk)
        body = StageTransitionSerializer(data=request.data or {})
        body.is_valid(raise_exception=True)
        project = rollback_project_stage(
            project, note=body.validated_data.get('note') or ''
        )
        return result.success(FinanceProjectOutputSerializer(project).data)


class StageTemplatesView(APIView):
    """GET /project stage-templates — 五套阶段模板（创建项目表单按类型列阶段用）。"""

    authentication_classes = [TokenAuth]

    @extend_schema(
        methods=['GET'],
        summary=_('List stage templates'),
        description=_('Return the fixed sub-stage templates keyed by project type.'),
        operation_id=_('List stage templates'),  # type: ignore
        tags=[_('Finance')],  # type: ignore
    )
    @has_permissions(
        PermissionConstants.FINANCE_READ.get_workspace_permission(),
        RoleConstants.USER.get_workspace_role(),
        RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
    )
    def get(self, request: Request, workspace_id):
        data = {
            project_type: [
                {
                    'stage_key': stage.key,
                    'label': stage.label,
                    'maps_to_status': stage.maps_to_status,
                    'order': stage.order,
                }
                for stage in stages
            ]
            for project_type, stages in STAGE_TEMPLATES.items()
        }
        return result.success(data)
