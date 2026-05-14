# coding=utf-8
"""
    @project: MaxKB
    @file： smtp_config.py
    @desc: SmtpConfig serializers (Gate 5 Track B).

    The output serializer NEVER exposes `password_encrypted`. Instead it
    surfaces a `has_password: bool` flag so the UI knows whether to default
    the password field to "keep existing" on edit.
"""
from rest_framework import serializers

from finance.models import SmtpConfig


class SmtpConfigCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    host = serializers.CharField(max_length=255)
    port = serializers.IntegerField(min_value=1, max_value=65535, default=587)
    username = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=512, trim_whitespace=False)
    from_email = serializers.EmailField()
    from_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=''
    )
    use_tls = serializers.BooleanField(default=True)
    use_ssl = serializers.BooleanField(default=False)
    is_default = serializers.BooleanField(default=False)


class SmtpConfigUpdateSerializer(serializers.Serializer):
    """All fields optional. Password is only changed when provided."""
    name = serializers.CharField(max_length=100, required=False)
    host = serializers.CharField(max_length=255, required=False)
    port = serializers.IntegerField(min_value=1, max_value=65535, required=False)
    username = serializers.CharField(max_length=255, required=False)
    # Blank/omitted → keep existing password.
    password = serializers.CharField(
        max_length=512, required=False, allow_blank=True, trim_whitespace=False
    )
    from_email = serializers.EmailField(required=False)
    from_name = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    use_tls = serializers.BooleanField(required=False)
    use_ssl = serializers.BooleanField(required=False)
    is_default = serializers.BooleanField(required=False)


class SmtpConfigTestSerializer(serializers.Serializer):
    to_address = serializers.EmailField()


class SmtpConfigOutputSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(format='hex_verbose')
    workspace_id = serializers.CharField(max_length=64)
    created_by = serializers.UUIDField(format='hex_verbose')
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = SmtpConfig
        fields = [
            'id',
            'workspace_id',
            'name',
            'host',
            'port',
            'username',
            'from_email',
            'from_name',
            'use_tls',
            'use_ssl',
            'is_default',
            'has_password',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_has_password(self, obj) -> bool:
        return bool(obj.password_encrypted)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for k in ('id', 'workspace_id', 'created_by'):
            v = data.get(k)
            if v is not None:
                data[k] = str(v)
        return data
