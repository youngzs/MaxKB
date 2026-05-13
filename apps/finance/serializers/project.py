# coding=utf-8
"""
    @project: MaxKB
    @file： project.py
    @desc: Request / response serializers for FinanceProject.
"""
from rest_framework import serializers

from finance.models import FinanceProject, FinanceProjectStatus, FinanceProjectType


class FinanceProjectInputSerializer(serializers.Serializer):
    """
    Body validator for POST (create) and PUT (full-update) routes.

    PUT reuses this with partial=True semantics handled at the view layer
    where appropriate; for now we keep the spec simple — only name and
    project_type are required, everything else is optional with sensible
    defaults defined on the model.
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


class FinanceProjectOutputSerializer(serializers.ModelSerializer):
    """Read-only payload returned by every Finance Project endpoint."""

    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.UUIDField(format='hex_verbose')
    created_by = serializers.UUIDField(format='hex_verbose')

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
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # UUIDs as strings throughout the API surface.
        for k in ('id', 'workspace_id', 'created_by'):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
