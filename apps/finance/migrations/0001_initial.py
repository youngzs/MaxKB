# Generated for MaxKB Finance — Gate 2 Track A
# Hand-written because the Windows dev environment cannot import the full
# Django app stack (one of the upstream apps requires the POSIX-only `pwd`
# module). Structurally mirrors apps/application/migrations/0001_initial.py.
import uuid_utils.compat
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='FinanceProject',
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
                ('name', models.CharField(max_length=200, verbose_name='项目名称')),
                ('code', models.CharField(blank=True, default='', max_length=64, verbose_name='项目编码')),
                (
                    'project_type',
                    models.CharField(
                        choices=[
                            ('bank_loan', '银行贷款'),
                            ('bond', '债券'),
                            ('trust', '信托'),
                            ('abs', 'ABS'),
                            ('other', '其他'),
                        ],
                        default='bank_loan',
                        max_length=32,
                        verbose_name='项目类型',
                    ),
                ),
                (
                    'target_amount',
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=20,
                        null=True,
                        verbose_name='目标金额',
                    ),
                ),
                ('currency', models.CharField(default='CNY', max_length=10, verbose_name='币种')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('preparing', '筹备'),
                            ('materials', '材料准备'),
                            ('engaging', '对接中'),
                            ('landed', '已落地'),
                            ('terminated', '已终止'),
                        ],
                        default='preparing',
                        max_length=32,
                        verbose_name='项目状态',
                    ),
                ),
                ('region', models.CharField(blank=True, default='', max_length=100, verbose_name='地区')),
                ('industry_code', models.CharField(blank=True, default='', max_length=32, verbose_name='行业代码')),
                ('knowledge_base_ids', models.JSONField(default=list, verbose_name='关联知识库白名单')),
                ('description', models.TextField(blank=True, default='', verbose_name='项目描述')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='是否已删除')),
                ('created_by', models.UUIDField(verbose_name='创建人id')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'finance_project',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='financeproject',
            constraint=models.UniqueConstraint(
                condition=models.Q(('code__gt', '')),
                fields=('workspace_id', 'code'),
                name='uniq_finance_project_workspace_code',
            ),
        ),
        migrations.CreateModel(
            name='FinanceAuditLog',
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
                ('actor_id', models.UUIDField(verbose_name='操作人id')),
                (
                    'target_type',
                    models.CharField(
                        choices=[
                            ('PROJECT', 'project'),
                            ('MATERIALS_TASK', 'materials_task'),
                            ('DOC_TEMPLATE', 'doc_template'),
                            ('DOC_GENERATION', 'doc_generation'),
                            ('OTHER', 'other'),
                        ],
                        max_length=32,
                        verbose_name='对象类型',
                    ),
                ),
                ('target_id', models.UUIDField(blank=True, null=True, verbose_name='对象id')),
                (
                    'action',
                    models.CharField(
                        choices=[
                            ('CREATE', 'create'),
                            ('UPDATE', 'update'),
                            ('DELETE', 'delete'),
                            ('READ', 'read'),
                            ('REVIEW_PASS', 'review_pass'),
                            ('REVIEW_REJECT', 'review_reject'),
                            ('SEND', 'send'),
                            ('DOWNLOAD', 'download'),
                        ],
                        max_length=32,
                        verbose_name='操作',
                    ),
                ),
                ('payload', models.JSONField(default=dict, verbose_name='请求快照（已脱敏）')),
                ('ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='来源IP')),
                ('user_agent', models.CharField(blank=True, default='', max_length=512, verbose_name='User-Agent')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='创建时间')),
            ],
            options={
                'db_table': 'finance_audit_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='financeauditlog',
            index=models.Index(fields=['workspace_id', 'created_at'], name='idx_fin_audit_ws_time'),
        ),
        migrations.AddIndex(
            model_name='financeauditlog',
            index=models.Index(fields=['target_type', 'target_id'], name='idx_fin_audit_target'),
        ),
    ]
