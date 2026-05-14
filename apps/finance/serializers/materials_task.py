# coding=utf-8
"""
    @project: MaxKB
    @file： materials_task.py
    @desc: Request / response serializers for the MaterialsTask workflow.

    Create accepts EITHER `requirement_text` (pasted directly from an email)
    OR a multipart `requirement_file` upload — the view handles the
    extraction step.
"""
from rest_framework import serializers

from finance.models import MaterialsTask


class MaterialsTaskCreateSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    requirement_text = serializers.CharField(
        required=False, allow_blank=True, default='', trim_whitespace=False
    )
    # File arrives via multipart; not always present (text-only path).
    requirement_file = serializers.FileField(required=False, allow_null=True)


class MaterialsTaskUpdateSelectionSerializer(serializers.Serializer):
    """
    PUT /selection — user-curated final set of document_ids the user
    actually wants packed, plus optionally an updated `matched_documents`
    list (when the UI lets the user override AI summaries inline).
    """
    selected_documents = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True
    )
    matched_documents = serializers.ListField(
        child=serializers.DictField(), required=False
    )


class MaterialsTaskReviewSerializer(serializers.Serializer):
    """POST /review — pass or reject a pending_review task."""
    action = serializers.ChoiceField(choices=['pass', 'reject'])
    comment = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=2000
    )


class MaterialsTaskPackSerializer(serializers.Serializer):
    """
    POST /pack — optional override of `selected_documents` and grouping
    layout. When `item_groups` is provided we use that grouping verbatim;
    otherwise we derive groups from `parsed_items` + `selected_documents`.
    """
    item_groups = serializers.ListField(
        child=serializers.DictField(), required=False
    )


class MaterialsTaskOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    project_id = serializers.UUIDField(format='hex_verbose')
    reviewer_id = serializers.UUIDField(format='hex_verbose', allow_null=True)
    created_by = serializers.UUIDField(format='hex_verbose')

    class Meta:
        model = MaterialsTask
        fields = [
            'id',
            'workspace_id',
            'project_id',
            'title',
            'requirement_text',
            'requirement_file_oss_key',
            'parsed_items',
            'matched_documents',
            'selected_documents',
            'zip_oss_key',
            'status',
            'reviewer_id',
            'reviewed_at',
            'review_comment',
            'error_message',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Coerce UUID-typed fields to strings for JSON friendliness — same
        # pattern as DocumentGenerationOutputSerializer.
        for k in ('id', 'workspace_id', 'project_id', 'reviewer_id', 'created_by'):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
