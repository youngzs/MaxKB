# coding=utf-8
"""
    @project: MaxKB
    @file： email_template.py
    @desc: EmailTemplate serializers (Gate 5 Track B).
"""
from rest_framework import serializers

from finance.models import EmailTemplate, EmailTemplateScenario


class EmailTemplateCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    subject = serializers.CharField(max_length=255)
    body_text = serializers.CharField(allow_blank=False)
    body_html = serializers.CharField(required=False, allow_blank=True, default='')
    scenario = serializers.ChoiceField(
        choices=EmailTemplateScenario.choices,
        default=EmailTemplateScenario.MATERIALS,
    )
    is_active = serializers.BooleanField(default=True)


class EmailTemplateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    subject = serializers.CharField(max_length=255, required=False)
    body_text = serializers.CharField(required=False)
    body_html = serializers.CharField(required=False, allow_blank=True)
    scenario = serializers.ChoiceField(
        choices=EmailTemplateScenario.choices, required=False
    )
    is_active = serializers.BooleanField(required=False)


class EmailTemplateOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    created_by = serializers.UUIDField(format='hex_verbose')

    class Meta:
        model = EmailTemplate
        fields = [
            'id',
            'workspace_id',
            'name',
            'subject',
            'body_text',
            'body_html',
            'scenario',
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
