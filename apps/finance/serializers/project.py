# coding=utf-8
"""
    @project: MaxKB
    @file： project.py
    @desc: Request / response serializers for FinanceProject.
"""
from rest_framework import serializers

from finance.models import FinanceProject, FinanceProjectStatus, FinanceProjectType


class StagePlanInputSerializer(serializers.Serializer):
    """
    创建项目时单个子阶段的计划完成时间录入项（DR-P2-04 手填）。

    `stage_key` 必须属于该项目类型的阶段模板；`planned_at` 可留空。
    校验由 view 层按 project_type 对照模板完成。
    """

    stage_key = serializers.CharField(max_length=32)
    planned_at = serializers.DateTimeField(required=False, allow_null=True)


class FinanceProjectInputSerializer(serializers.Serializer):
    """
    Body validator for POST (create) and PUT (full-update) routes.

    PUT reuses this with partial=True semantics handled at the view layer
    where appropriate; for now we keep the spec simple — only name and
    project_type are required, everything else is optional with sensible
    defaults defined on the model.

    P2 注意：`status` 仅在 **创建** 时作为起始大状态种子（据此反查起始子阶段
    并预生成阶段行）；项目创建后大状态由 current_stage_key 派生，PUT 不再据此
    改写（view 层保证，唯一例外是置为 terminated）。`stage_plans` 也只在创建
    时生效。
    """

    name = serializers.CharField(max_length=200)
    code = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    project_type = serializers.ChoiceField(choices=FinanceProjectType.choices)
    target_amount = serializers.DecimalField(
        max_digits=20, decimal_places=2, required=False, allow_null=True
    )
    currency = serializers.CharField(max_length=10, required=False, default='CNY')
    status = serializers.ChoiceField(
        choices=FinanceProjectStatus.choices,
        required=False,
        default=FinanceProjectStatus.PREPARING,
    )
    region = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    industry_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=''
    )
    knowledge_base_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    # --- P2「进度归集」字段 ---
    owner_id = serializers.UUIDField(required=False, allow_null=True)  # DR-P2-03
    counterparty = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default=''
    )  # DR-P2-02
    stage_plans = serializers.ListField(
        child=StagePlanInputSerializer(), required=False, default=list
    )  # DR-P2-04 —— 仅创建时生效


class FinanceProjectOutputSerializer(serializers.ModelSerializer):
    """Read-only payload returned by every Finance Project endpoint."""

    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    created_by = serializers.UUIDField(format='hex_verbose')
    owner_id = serializers.UUIDField(format='hex_verbose', allow_null=True)

    class Meta:
        model = FinanceProject
        fields = [
            'id',
            'workspace_id',
            'name',
            'code',
            'project_type',
            'target_amount',
            'currency',
            'status',
            'region',
            'industry_code',
            'knowledge_base_ids',
            'description',
            'owner_id',
            'counterparty',
            'current_stage_key',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # UUIDs as strings throughout the API surface.
        for k in ('id', 'workspace_id', 'created_by', 'owner_id'):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
