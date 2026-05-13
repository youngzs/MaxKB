# coding=utf-8
"""
    @project: MaxKB
    @file： document_generation.py
    @desc: DocumentGeneration — one rendered docx instance for a given
    (project, template, placeholder-values) triple, plus a state machine
    GENERATING → PENDING_REVIEW → CONFIRMED / REVOKED. FAILED is a sink.

    template_version_snapshot is captured at generation time so a later
    template re-upload doesn't invalidate the audit trail.
"""
import uuid_utils.compat as uuid
from django.db import models


class GenerationStatus(models.TextChoices):
    GENERATING = 'generating', '生成中'
    PENDING_REVIEW = 'pending_review', '待确认'
    CONFIRMED = 'confirmed', '已确认'
    REVOKED = 'revoked', '已撤回'
    FAILED = 'failed', '失败'


class DocumentGeneration(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.UUIDField(db_index=True, verbose_name='工作空间id')
    project_id = models.UUIDField(db_index=True, verbose_name='融资项目id')
    template_id = models.UUIDField(db_index=True, verbose_name='模板id')
    template_version_snapshot = models.PositiveIntegerField(
        verbose_name='模板版本快照'
    )
    placeholder_values = models.JSONField(default=dict, verbose_name='填充值')
    workflow_run_id = models.UUIDField(null=True, blank=True, verbose_name='工作流运行id')
    output_oss_key = models.CharField(
        max_length=500, blank=True, default='', verbose_name='输出文件 OSS key'
    )
    status = models.CharField(
        max_length=20,
        choices=GenerationStatus.choices,
        default=GenerationStatus.GENERATING,
        verbose_name='状态',
    )
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    reviewer_id = models.UUIDField(null=True, blank=True, verbose_name='审核人id')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    created_by = models.UUIDField(verbose_name='创建人id')
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_document_generation'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['workspace_id', 'project_id', '-created_at'],
                name='idx_fin_doc_gen_ws_pj_t',
            ),
            models.Index(fields=['template_id'], name='idx_fin_doc_gen_template'),
            models.Index(fields=['status'], name='idx_fin_doc_gen_status'),
        ]

    def __str__(self):
        return f'{self.template_id} -> {self.status}'
