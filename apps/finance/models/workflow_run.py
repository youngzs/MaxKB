# coding=utf-8
"""
    @project: MaxKB
    @file： workflow_run.py
    @desc: WorkflowRun — per-execution audit row for the Gate 7 Track B async
    pipeline. One row per Celery task invocation (parse / match / pack /
    generate), tracking timing, status, retries, and any error message.

    Distinct from FinanceAuditLog: the audit log records *user-facing* events
    ("User X parsed task Y"), whereas WorkflowRun records *runtime* events
    ("Celery task finance.materials.async_parse started at T, succeeded at
    T+12.4s on attempt 1"). Two different audiences (compliance vs. ops).

    target_type / target_id loosely mirror the audit log so a UI drawer can
    query "all runs for materials_task Y" without joining through audit rows.
"""
import uuid_utils.compat as uuid
from django.db import models


class WorkflowRunStatus(models.TextChoices):
    QUEUED = 'queued', '排队中'
    RUNNING = 'running', '运行中'
    SUCCEEDED = 'succeeded', '成功'
    FAILED = 'failed', '失败'
    RETRYING = 'retrying', '重试中'


class WorkflowRunTargetType(models.TextChoices):
    MATERIALS_TASK = 'MATERIALS_TASK', 'materials_task'
    DOC_GENERATION = 'DOC_GENERATION', 'doc_generation'
    OTHER = 'OTHER', 'other'


class WorkflowRun(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.CharField(
        max_length=64, db_index=True, verbose_name='工作空间id'
    )
    target_type = models.CharField(
        max_length=32,
        choices=WorkflowRunTargetType.choices,
        verbose_name='对象类型',
    )
    target_id = models.UUIDField(db_index=True, verbose_name='对象id')
    task_name = models.CharField(
        max_length=128, verbose_name='Celery 任务名'
    )
    celery_task_id = models.CharField(
        max_length=64, blank=True, default='', verbose_name='Celery 任务 id'
    )
    status = models.CharField(
        max_length=20,
        choices=WorkflowRunStatus.choices,
        default=WorkflowRunStatus.QUEUED,
        verbose_name='状态',
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    duration_ms = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='耗时(毫秒)'
    )
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    payload = models.JSONField(default=dict, verbose_name='输入/输出快照')
    retry_count = models.PositiveSmallIntegerField(
        default=0, verbose_name='重试次数'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_workflow_run'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['workspace_id', '-created_at'],
                name='idx_fin_wflow_run_ws_t',
            ),
            models.Index(
                fields=['target_type', 'target_id', '-created_at'],
                name='idx_fin_wflow_run_target',
            ),
            models.Index(fields=['status'], name='idx_fin_wflow_run_status'),
        ]

    def __str__(self):
        return f'{self.task_name} [{self.status}] -> {self.target_type}/{self.target_id}'
