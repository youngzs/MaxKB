# Generated for MaxKB Finance — Gate 4 Track A
# Hand-written because the Windows dev environment cannot import the full
# Django app stack (one of the upstream apps requires the POSIX-only `pwd`
# module). Structurally mirrors apps/finance/migrations/0002_*.py.
import uuid_utils.compat
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_documenttemplate_documentgeneration'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialsTask',
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
                ('workspace_id', models.UUIDField(db_index=True, verbose_name='工作空间id')),
                ('project_id', models.UUIDField(db_index=True, verbose_name='融资项目id')),
                ('title', models.CharField(max_length=200, verbose_name='任务标题')),
                (
                    'requirement_text',
                    models.TextField(blank=True, default='', verbose_name='需求清单原文'),
                ),
                (
                    'requirement_file_oss_key',
                    models.CharField(
                        blank=True, default='', max_length=500,
                        verbose_name='需求清单文件 OSS key',
                    ),
                ),
                ('parsed_items', models.JSONField(default=list, verbose_name='结构化需求项')),
                (
                    'matched_documents',
                    models.JSONField(
                        default=list,
                        verbose_name='匹配到的候选文档（含敏感等级与AI概要）',
                    ),
                ),
                (
                    'selected_documents',
                    models.JSONField(default=list, verbose_name='最终选定的文档id列表'),
                ),
                (
                    'zip_oss_key',
                    models.CharField(
                        blank=True, default='', max_length=500,
                        verbose_name='打包 zip OSS key',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('draft', '草稿'),
                            ('parsing', '解析中'),
                            ('matching', '匹配中'),
                            ('pending_review', '待审核'),
                            ('approved', '已审核'),
                            ('sent', '已发送'),
                            ('rejected', '已退回'),
                            ('failed', '失败'),
                        ],
                        default='draft',
                        max_length=20,
                        verbose_name='状态',
                    ),
                ),
                ('reviewer_id', models.UUIDField(blank=True, null=True, verbose_name='审核人id')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='审核时间')),
                ('review_comment', models.TextField(blank=True, default='', verbose_name='审核意见')),
                ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='是否已删除')),
                ('created_by', models.UUIDField(verbose_name='创建人id')),
                (
                    'created_at',
                    models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='创建时间'),
                ),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'finance_materials_task',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='materialstask',
            index=models.Index(
                fields=['workspace_id', 'project_id', '-created_at'],
                name='idx_fin_mat_task_ws_pj_t',
            ),
        ),
        migrations.AddIndex(
            model_name='materialstask',
            index=models.Index(fields=['status'], name='idx_fin_mat_task_status'),
        ),
    ]
