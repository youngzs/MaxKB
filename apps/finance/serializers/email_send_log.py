# coding=utf-8
"""
    @project: MaxKB
    @file： email_send_log.py
    @desc: EmailSendLog serializers + materials send request shape
    (Gate 5 Track B).
"""
from rest_framework import serializers

from finance.models import EmailSendLog


class MaterialsTaskSendSerializer(serializers.Serializer):
    """
    POST /materials-task/<pk>/send body.

    `to_addresses` must contain at least one entry; the view layer further
    validates state transitions (only `approved` is sendable).
    """
    smtp_config_id = serializers.UUIDField()
    email_template_id = serializers.UUIDField()
    to_addresses = serializers.ListField(
        child=serializers.EmailField(), allow_empty=False, max_length=50,
    )
    cc_addresses = serializers.ListField(
        child=serializers.EmailField(),
        required=False, allow_empty=True, default=list, max_length=50,
    )
    extra_context = serializers.DictField(required=False)
    attach_zip = serializers.BooleanField(default=True)


class EmailSendLogOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    target_id = serializers.UUIDField(format='hex_verbose', allow_null=True)
    smtp_config_id = serializers.UUIDField(format='hex_verbose', allow_null=True)
    email_template_id = serializers.UUIDField(format='hex_verbose', allow_null=True)
    sent_by = serializers.UUIDField(format='hex_verbose')

    class Meta:
        model = EmailSendLog
        fields = [
            'id',
            'workspace_id',
            'target_type',
            'target_id',
            'smtp_config_id',
            'email_template_id',
            'to_addresses',
            'cc_addresses',
            'subject',
            'body_preview',
            'attachment_keys',
            'status',
            'error_message',
            'retry_count',
            'sent_by',
            'sent_at',
            'created_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in (
            'id',
            'workspace_id',
            'target_id',
            'smtp_config_id',
            'email_template_id',
            'sent_by',
        ):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
