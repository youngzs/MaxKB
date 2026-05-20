# coding=utf-8
"""
    @project: MaxKB
    @file： project_stage.py
    @desc: P2「进度归集」Gate 2 — 阶段流转端点的请求体校验器。

    （阶段记录的只读输出在 project_stage_record.py 的
    ProjectStageRecordOutputSerializer；创建项目时的计划时间录入用
    project.py 的 StagePlanInputSerializer。）
"""
from rest_framework import serializers


class StageTransitionSerializer(serializers.Serializer):
    """POST advance / rollback —— 可选备注（回退原因等）。"""

    note = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=1000
    )


class ProjectStageUpdateSerializer(serializers.Serializer):
    """
    PUT /project/<pk>/stages/<stage_key> —— 改单个子阶段的元数据。

    三个字段全部可选（partial update）：
      - `planned_at`  计划完成时间（DR-P2-04 手填，可置空）
      - `owner_id`    阶段责任人；置空则继承项目负责人
      - `note`        备注

    不在此处改 status / entered_at / actual_at —— 那些只由 advance / rollback
    流转驱动。
    """

    planned_at = serializers.DateTimeField(required=False, allow_null=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)
