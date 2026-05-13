# coding=utf-8
"""
    @project: MaxKB
    @file： audit_log.py
    @desc: FinanceAuditLog — append-only audit trail for finance-module actions.

    Distinct from system_manage.Log (the global operation log): finance has
    its own table so review/compliance queries don't trip over unrelated
    workspace activity, and so we can shape indexes around the finance
    access patterns (workspace + time-range, by target).
"""
import uuid_utils.compat as uuid
from django.db import models


class FinanceAuditTargetType(models.TextChoices):
    PROJECT = 'PROJECT', 'project'
    MATERIALS_TASK = 'MATERIALS_TASK', 'materials_task'
    DOC_TEMPLATE = 'DOC_TEMPLATE', 'doc_template'
    DOC_GENERATION = 'DOC_GENERATION', 'doc_generation'
    OTHER = 'OTHER', 'other'


class FinanceAuditAction(models.TextChoices):
    CREATE = 'CREATE', 'create'
    UPDATE = 'UPDATE', 'update'
    DELETE = 'DELETE', 'delete'
    READ = 'READ', 'read'
    REVIEW_PASS = 'REVIEW_PASS', 'review_pass'
    REVIEW_REJECT = 'REVIEW_REJECT', 'review_reject'
    SEND = 'SEND', 'send'
    DOWNLOAD = 'DOWNLOAD', 'download'


class FinanceAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id')
    workspace_id = models.UUIDField(verbose_name='工作空间id', db_index=True)
    actor_id = models.UUIDField(verbose_name='操作人id')
    target_type = models.CharField(
        max_length=32,
        choices=FinanceAuditTargetType.choices,
        verbose_name='对象类型',
    )
    target_id = models.UUIDField(null=True, blank=True, verbose_name='对象id')
    action = models.CharField(
        max_length=32,
        choices=FinanceAuditAction.choices,
        verbose_name='操作',
    )
    payload = models.JSONField(default=dict, verbose_name='请求快照（已脱敏）')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='来源IP')
    user_agent = models.CharField(max_length=512, blank=True, default='', verbose_name='User-Agent')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='创建时间')

    class Meta:
        db_table = 'finance_audit_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workspace_id', 'created_at'], name='idx_fin_audit_ws_time'),
            models.Index(fields=['target_type', 'target_id'], name='idx_fin_audit_target'),
        ]
