# coding=utf-8
"""
    @project: MaxKB
    @file： smtp_config.py
    @desc: SmtpConfig — workspace-scoped outbound SMTP credentials used by the
    materials send pipeline (Gate 5 Track B).

    The password is stored as `password_encrypted` (Fernet ciphertext derived
    from `settings.SECRET_KEY`). Plaintext NEVER leaves
    `finance.service.email_sender` — neither serializers nor the audit log
    expose it. See `finance.service.encryption` for the key derivation.

    A workspace may have multiple configs; exactly one may be marked
    `is_default=True` (enforced by a partial unique constraint that ignores
    soft-deleted rows).
"""
import uuid_utils.compat as uuid
from django.db import models


class SmtpConfig(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.CharField(
        max_length=64, db_index=True, verbose_name='工作空间id'
    )
    name = models.CharField(max_length=100, verbose_name='展示名称')
    host = models.CharField(max_length=255, verbose_name='SMTP 主机')
    port = models.PositiveSmallIntegerField(default=587, verbose_name='SMTP 端口')
    username = models.CharField(max_length=255, verbose_name='登录用户名')
    password_encrypted = models.TextField(
        verbose_name='SMTP 登录密码密文（Fernet）'
    )
    from_email = models.EmailField(verbose_name='发件邮箱')
    from_name = models.CharField(
        max_length=100, blank=True, default='', verbose_name='发件人显示名'
    )
    use_tls = models.BooleanField(default=True, verbose_name='STARTTLS')
    use_ssl = models.BooleanField(default=False, verbose_name='SMTPS (SSL)')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    is_deleted = models.BooleanField(
        default=False, db_index=True, verbose_name='是否已删除'
    )
    created_by = models.UUIDField(verbose_name='创建人id')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_smtp_config'
        ordering = ['-is_default', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace_id'],
                condition=models.Q(is_default=True, is_deleted=False),
                name='unique_default_smtp_per_ws',
            )
        ]
        indexes = [
            models.Index(
                fields=['workspace_id', 'is_deleted'],
                name='idx_fin_smtp_ws_del',
            ),
        ]

    def __str__(self):
        return f'{self.name} <{self.from_email}>'
