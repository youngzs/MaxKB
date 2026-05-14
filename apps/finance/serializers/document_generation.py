# coding=utf-8
"""
    @project: MaxKB
    @file： document_generation.py
    @desc: Request / response serializers for DocumentGeneration + AI-fill.
"""
from rest_framework import serializers

from finance.models import DocumentGeneration


class DocumentGenerationCreateSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    template_id = serializers.UUIDField()
    placeholder_values = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)


class DocumentGenerationOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    project_id = serializers.UUIDField(format='hex_verbose')
    template_id = serializers.UUIDField(format='hex_verbose')
    workflow_run_id = serializers.UUIDField(format='hex_verbose', allow_null=True)
    reviewer_id = serializers.UUIDField(format='hex_verbose', allow_null=True)
    created_by = serializers.UUIDField(format='hex_verbose')

    class Meta:
        model = DocumentGeneration
        fields = [
            'id',
            'workspace_id',
            'project_id',
            'template_id',
            'template_version_snapshot',
            'placeholder_values',
            'workflow_run_id',
            'output_oss_key',
            'status',
            'error_message',
            'reviewer_id',
            'reviewed_at',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in (
            'id',
            'workspace_id',
            'project_id',
            'template_id',
            'workflow_run_id',
            'reviewer_id',
            'created_by',
        ):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data


class AIFillRequestSerializer(serializers.Serializer):
    """
    POST /generation/ai-fill — request body to ask AI to fill specified
    placeholders for a (project, template) pair.

    `placeholder_keys` is the subset of the template's placeholders the
    caller wants AI-generated values for. Returning anything else is wasted
    work, so the response is keyed by exactly these.
    """

    template_id = serializers.UUIDField()
    project_id = serializers.UUIDField()
    placeholder_keys = serializers.ListField(
        child=serializers.CharField(max_length=200), allow_empty=False
    )
