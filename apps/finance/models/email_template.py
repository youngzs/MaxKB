# coding=utf-8
"""
    @project: MaxKB
    @file： email_template.py
    @desc: EmailTemplate — reusable outbound email body/subject for the
    materials send pipeline (Gate 5 Track B).

    Templates use a deliberately tiny `{{ var }}` substitution language (see
    `finance.service.email_sender.render_template_string`). We intentionally
    do NOT plug in Jinja's full expression evaluator here: rendered content
    can flow out to external recipients, so the parser must be sandbox-safe
    and predictable.

    Supported placeholders today:
      {{ project_name }}    project.name
      {{ task_title }}      materials_task.title
      {{ recipient_name }}  first entry of `to_addresses` local part
      {{ zip_filename }}    `materials-<task_id>.zip`
      ... plus anything passed via `extra_context` to the send endpoint.
"""
import uuid_utils.compat as uuid
from django.db import models


class EmailTemplateScenario(models.TextChoices):
    MATERIALS = 'materials', '材料发送'
    PROGRESS_REPORT = 'progress_report', '进度汇报'
    GENERAL = 'general', '通用'
    OTHER = 'other', '其他'


class EmailTemplate(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.CharField(
        max_length=64, db_index=True, verbose_name='工作空间id'
    )
    name = models.CharField(max_length=100, verbose_name='模板名称')
    subject = models.CharField(max_length=255, verbose_name='邮件主题')
    body_text = models.TextField(verbose_name='纯文本正文')
    body_html = models.TextField(
        blank=True, default='', verbose_name='HTML 正文（可选）'
    )
    scenario = models.CharField(
        max_length=32,
        choices=EmailTemplateScenario.choices,
        default=EmailTemplateScenario.MATERIALS,
        verbose_name='场景',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    is_deleted = models.BooleanField(
        default=False, db_index=True, verbose_name='是否已删除'
    )
    created_by = models.UUIDField(verbose_name='创建人id')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_email_template'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['workspace_id', 'scenario', 'is_deleted'],
                name='idx_fin_email_tpl_ws_sc',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.scenario})'
