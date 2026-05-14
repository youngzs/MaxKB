# coding=utf-8
"""
    @project: MaxKB
    @file： audit_log.py
    @desc: Read-only serializer for FinanceAuditLog.
"""
from rest_framework import serializers

from finance.models import FinanceAuditLog


class FinanceAuditLogOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    actor_id = serializers.UUIDField(format='hex_verbose')
    target_id = serializers.UUIDField(format='hex_verbose', allow_null=True)

    class Meta:
        model = FinanceAuditLog
        fields = [
            'id',
            'workspace_id',
            'actor_id',
            'target_type',
            'target_id',
            'action',
            'payload',
            'ip',
            'user_agent',
            'created_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('id', 'workspace_id', 'actor_id', 'target_id'):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
