# Generated for MaxKB Finance — Gate 3 Track A
# Hand-written because the Windows dev environment cannot import the full
# Django app stack (one of the upstream apps requires the POSIX-only `pwd`
# module). Structurally mirrors apps/finance/migrations/0001_initial.py.
import uuid_utils.compat
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentTemplate',
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
                ('name', models.CharField(max_length=200, verbose_name='模板名称')),
                (
                    'scenario',
                    models.CharField(
                        choices=[
                            ('internal_report', '内部汇报'),
                            ('meeting', '上会材料'),
                            ('system_process', '系统流程'),
                            ('other', '其他'),
                        ],
                        default='other',
                        max_length=32,
                        verbose_name='模板场景',
                    ),
                ),
                ('docx_oss_key', models.CharField(max_length=500, verbose_name='docx OSS key')),
                (
                    'placeholders',
                    models.JSONField(
                        default=list,
                        verbose_name='占位符元数据 [{key,label,type,required,ai_hint,enum_options}]',
                    ),
                ),
                ('version', models.PositiveIntegerField(default=1, verbose_name='版本号')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='是否已删除')),
                ('created_by', models.UUIDField(verbose_name='创建人id')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'finance_document_template',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='documenttemplate',
            index=models.Index(
                fields=['workspace_id', 'scenario'], name='idx_fin_doc_tpl_ws_scn'
            ),
        ),
        migrations.CreateModel(
            name='DocumentGeneration',
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
                ('template_id', models.UUIDField(db_index=True, verbose_name='模板id')),
                (
                    'template_version_snapshot',
                    models.PositiveIntegerField(verbose_name='模板版本快照'),
                ),
                ('placeholder_values', models.JSONField(default=dict, verbose_name='填充值')),
                (
                    'workflow_run_id',
                    models.UUIDField(blank=True, null=True, verbose_name='工作流运行id'),
                ),
                (
                    'output_oss_key',
                    models.CharField(
                        blank=True, default='', max_length=500, verbose_name='输出文件 OSS key'
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('generating', '生成中'),
                            ('pending_review', '待确认'),
                            ('confirmed', '已确认'),
                            ('revoked', '已撤回'),
                            ('failed', '失败'),
                        ],
                        default='generating',
                        max_length=20,
                        verbose_name='状态',
                    ),
                ),
                ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                ('reviewer_id', models.UUIDField(blank=True, null=True, verbose_name='审核人id')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='审核时间')),
                ('created_by', models.UUIDField(verbose_name='创建人id')),
                (
                    'created_at',
                    models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='创建时间'),
                ),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'finance_document_generation',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='documentgeneration',
            index=models.Index(
                fields=['workspace_id', 'project_id', '-created_at'],
                name='idx_fin_doc_gen_ws_pj_t',
            ),
        ),
        migrations.AddIndex(
            model_name='documentgeneration',
            index=models.Index(fields=['template_id'], name='idx_fin_doc_gen_template'),
        ),
        migrations.AddIndex(
            model_name='documentgeneration',
            index=models.Index(fields=['status'], name='idx_fin_doc_gen_status'),
        ),
    ]
