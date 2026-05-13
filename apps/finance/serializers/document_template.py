# coding=utf-8
"""
    @project: MaxKB
    @file： document_template.py
    @desc: Request / response serializers for DocumentTemplate.
"""
from rest_framework import serializers

from finance.models import DocumentTemplate, TemplateScenario


class _PlaceholderItemSerializer(serializers.Serializer):
    """One row of the `placeholders` JSON list — used on PUT only."""

    key = serializers.CharField(max_length=200)
    label = serializers.CharField(max_length=200, allow_blank=True, default='')
    type = serializers.ChoiceField(
        choices=('text', 'long_text', 'number', 'date', 'enum'), default='text'
    )
    required = serializers.BooleanField(default=True)
    ai_hint = serializers.CharField(allow_blank=True, default='', required=False)
    enum_options = serializers.ListField(
        child=serializers.CharField(), default=list, required=False
    )


class DocumentTemplateUploadSerializer(serializers.Serializer):
    """POST /template — multipart: file + name + scenario."""

    file = serializers.FileField()
    name = serializers.CharField(max_length=200)
    scenario = serializers.ChoiceField(
        choices=TemplateScenario.choices, default=TemplateScenario.OTHER
    )


class DocumentTemplateUpdateSerializer(serializers.Serializer):
    """
    PUT /template/<pk> — metadata + placeholder annotations only.

    The docx binary itself is replaced by a separate re-upload call (which
    bumps `version` in the view layer). This keeps the JSON shape stable
    and lets the UI edit placeholder labels / ai_hints / types without
    re-uploading the file.
    """

    name = serializers.CharField(max_length=200, required=False)
    scenario = serializers.ChoiceField(
        choices=TemplateScenario.choices, required=False
    )
    is_active = serializers.BooleanField(required=False)
    placeholders = serializers.ListField(
        child=_PlaceholderItemSerializer(), required=False
    )


class DocumentTemplateOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.UUIDField(format='hex_verbose')
    created_by = serializers.UUIDField(format='hex_verbose')

    class Meta:
        model = DocumentTemplate
        fields = [
            'id',
            'workspace_id',
            'name',
            'scenario',
            'docx_oss_key',
            'placeholders',
            'version',
            'is_active',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('id', 'workspace_id', 'created_by'):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
