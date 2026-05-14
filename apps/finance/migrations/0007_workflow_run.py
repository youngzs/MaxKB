# Generated for MaxKB Finance — Gate 7 Track B
# Hand-written (same reason as 0005/0006: Windows dev cannot import the full
# Django app stack to run makemigrations). Structurally mirrors the previous
# CreateModel migrations.
import uuid_utils.compat
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_auditlog_smtp_target'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowRun',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid_utils.compat.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        verbose_name='主键id',
                    ),
                ),
                (
                    'workspace_id',
                    models.CharField(
                        db_index=True, max_length=64, verbose_name='工作空间id'
                    ),
                ),
                (
                    'target_type',
                    models.CharField(
                        choices=[
                            ('MATERIALS_TASK', 'materials_task'),
                            ('DOC_GENERATION', 'doc_generation'),
                            ('OTHER', 'other'),
                        ],
                        max_length=32,
                        verbose_name='对象类型',
                    ),
                ),
                (
                    'target_id',
                    models.UUIDField(db_index=True, verbose_name='对象id'),
                ),
                (
                    'task_name',
                    models.CharField(max_length=128, verbose_name='Celery 任务名'),
                ),
                (
                    'celery_task_id',
                    models.CharField(
                        blank=True,
                        default='',
                        max_length=64,
                        verbose_name='Celery 任务 id',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('queued', '排队中'),
                            ('running', '运行中'),
                            ('succeeded', '成功'),
                            ('failed', '失败'),
                            ('retrying', '重试中'),
                        ],
                        default='queued',
                        max_length=20,
                        verbose_name='状态',
                    ),
                ),
                (
                    'started_at',
                    models.DateTimeField(
                        blank=True, null=True, verbose_name='开始时间'
                    ),
                ),
                (
                    'finished_at',
                    models.DateTimeField(
                        blank=True, null=True, verbose_name='结束时间'
                    ),
                ),
                (
                    'duration_ms',
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name='耗时(毫秒)'
                    ),
                ),
                (
                    'error_message',
                    models.TextField(blank=True, default='', verbose_name='错误信息'),
                ),
                (
                    'payload',
                    models.JSONField(default=dict, verbose_name='输入/输出快照'),
                ),
                (
                    'retry_count',
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name='重试次数'
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        verbose_name='创建时间',
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(auto_now=True, verbose_name='修改时间'),
                ),
            ],
            options={
                'db_table': 'finance_workflow_run',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='workflowrun',
            index=models.Index(
                fields=['workspace_id', '-created_at'],
                name='idx_fin_wflow_run_ws_t',
            ),
        ),
        migrations.AddIndex(
            model_name='workflowrun',
            index=models.Index(
                fields=['target_type', 'target_id', '-created_at'],
                name='idx_fin_wflow_run_target',
            ),
        ),
        migrations.AddIndex(
            model_name='workflowrun',
            index=models.Index(
                fields=['status'], name='idx_fin_wflow_run_status'
            ),
        ),
    ]
