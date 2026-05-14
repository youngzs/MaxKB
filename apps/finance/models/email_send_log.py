# coding=utf-8
"""
    @project: MaxKB
    @file： email_send_log.py
    @desc: EmailSendLog — immutable per-attempt outbound email send log
    (Gate 5 Track B).

    One row per `send` invocation. The row is written BEFORE SMTP dial (with
    `status='sending'`) and updated to `sent` or `failed` once the call
    returns. This guarantees we have a forensic trail even when the process
    is killed mid-send.

    The materials send pipeline keys log entries via `(target_type='MATERIALS_TASK',
    target_id=<task_id>)` so the detail page can query
    "give me every send attempt for this task" cheaply.
"""
import uuid_utils.compat as uuid
from django.db import models


class EmailSendStatus(models.TextChoices):
    QUEUED = 'queued', '排队中'
    SENDING = 'sending', '发送中'
    SENT = 'sent', '已发送'
    FAILED = 'failed', '失败'
    RETRIED = 'retried', '已重发'


class EmailSendLog(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.CharField(
        max_length=64, db_index=True, verbose_name='工作空间id'
    )
    target_type = models.CharField(
        max_length=32, default='MATERIALS_TASK', verbose_name='目标对象类型'
    )
    target_id = models.UUIDField(
        null=True, blank=True, verbose_name='目标对象id'
    )
    smtp_config_id = models.UUIDField(
        null=True, blank=True, verbose_name='所用 SMTP 配置id'
    )
    email_template_id = models.UUIDField(
        null=True, blank=True, verbose_name='所用模板id'
    )
    to_addresses = models.JSONField(default=list, verbose_name='收件人列表')
    cc_addresses = models.JSONField(default=list, verbose_name='抄送列表')
    subject = models.CharField(
        max_length=512, blank=True, default='', verbose_name='渲染后的主题'
    )
    body_preview = models.CharField(
        max_length=500, blank=True, default='', verbose_name='正文预览（前 500 字）'
    )
    attachment_keys = models.JSONField(
        default=list, verbose_name='附件 OSS key 列表'
    )
    status = models.CharField(
        max_length=16,
        choices=EmailSendStatus.choices,
        default=EmailSendStatus.QUEUED,
        verbose_name='发送状态',
    )
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    retry_count = models.PositiveSmallIntegerField(default=0, verbose_name='重试次数')
    sent_by = models.UUIDField(verbose_name='发送人id')
    sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name='发送完成时间'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name='创建时间'
    )

    class Meta:
        db_table = 'finance_email_send_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['workspace_id', '-created_at'],
                name='idx_fin_send_ws_time',
            ),
            models.Index(
                fields=['target_type', 'target_id'],
                name='idx_fin_send_target',
            ),
        ]

    def __str__(self):
        return f'{self.target_type}:{self.target_id} [{self.status}]'
