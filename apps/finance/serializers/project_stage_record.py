# coding=utf-8
"""
    @project: MaxKB
    @file： project_stage_record.py
    @desc: Response serializer for ProjectStageRecord.

    Gate 1 仅交付 Output serializer（为 Gate 2 的 gantt / stages / advance /
    rollback 端点铺路）。阶段名 label 由类型模板派生、需 project_type 才能
    解析，故不在本表的纯字段输出里；Gate 2/3 的 gantt 端点再做 join 富化。
"""
from rest_framework import serializers

from finance.models import ProjectStageRecord


class ProjectStageRecordOutputSerializer(serializers.ModelSerializer):
    """单条阶段记录的只读输出。"""

    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    project_id = serializers.UUIDField(format='hex_verbose')
    owner_id = serializers.UUIDField(format='hex_verbose', allow_null=True)

    class Meta:
        model = ProjectStageRecord
        fields = [
            'id',
            'workspace_id',
            'project_id',
            'stage_key',
            'stage_order',
            'planned_at',
            'actual_at',
            'owner_id',
            'entered_at',
            'status',
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # UUID 字段统一转字符串 —— 与 FinanceProject/MaterialsTask 输出一致。
        for key in ('id', 'workspace_id', 'project_id', 'owner_id'):
            value = data.get(key)
            if value is not None:
                data[key] = str(value)
        return data
