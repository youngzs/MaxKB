# Generated for MaxKB Finance — Gate 5 Track B
# Hand-written because the Windows dev environment cannot import the full
# Django app stack (one of the upstream apps requires the POSIX-only `pwd`
# module). Structurally mirrors apps/finance/migrations/0003_materialstask.py.
import uuid_utils.compat
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0004_workspace_id_charfield'),
    ]

    operations = [
        # ---------------- SmtpConfig ----------------
        migrations.CreateModel(
            name='SmtpConfig',
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
                ('name', models.CharField(max_length=100, verbose_name='展示名称')),
                ('host', models.CharField(max_length=255, verbose_name='SMTP 主机')),
                (
                    'port',
                    models.PositiveSmallIntegerField(
                        default=587, verbose_name='SMTP 端口'
                    ),
                ),
                (
                    'username',
                    models.CharField(max_length=255, verbose_name='登录用户名'),
                ),
                (
                    'password_encrypted',
                    models.TextField(verbose_name='SMTP 登录密码密文（Fernet）'),
                ),
                ('from_email', models.EmailField(max_length=254, verbose_name='发件邮箱')),
                (
                    'from_name',
                    models.CharField(
                        blank=True, default='', max_length=100,
                        verbose_name='发件人显示名',
                    ),
                ),
                ('use_tls', models.BooleanField(default=True, verbose_name='STARTTLS')),
                ('use_ssl', models.BooleanField(default=False, verbose_name='SMTPS (SSL)')),
                ('is_default', models.BooleanField(default=False, verbose_name='是否默认')),
                (
                    'is_deleted',
                    models.BooleanField(
                        db_index=True, default=False, verbose_name='是否已删除'
                    ),
                ),
                ('created_by', models.UUIDField(verbose_name='创建人id')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'finance_smtp_config',
                'ordering': ['-is_default', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='smtpconfig',
            index=models.Index(
                fields=['workspace_id', 'is_deleted'],
                name='idx_fin_smtp_ws_del',
            ),
        ),
        migrations.AddConstraint(
            model_name='smtpconfig',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_default', True), ('is_deleted', False)),
                fields=('workspace_id',),
                name='unique_default_smtp_per_ws',
            ),
        ),
        # ---------------- EmailTemplate ----------------
        migrations.CreateModel(
            name='EmailTemplate',
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
                ('name', models.CharField(max_length=100, verbose_name='模板名称')),
                ('subject', models.CharField(max_length=255, verbose_name='邮件主题')),
                ('body_text', models.TextField(verbose_name='纯文本正文')),
                (
                    'body_html',
                    models.TextField(blank=True, default='', verbose_name='HTML 正文（可选）'),
                ),
                (
                    'scenario',
                    models.CharField(
                        choices=[
                            ('materials', '材料发送'),
                            ('progress_report', '进度汇报'),
                            ('general', '通用'),
                            ('other', '其他'),
                        ],
                        default='materials',
                        max_length=32,
                        verbose_name='场景',
                    ),
                ),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                (
                    'is_deleted',
                    models.BooleanField(
                        db_index=True, default=False, verbose_name='是否已删除'
                    ),
                ),
                ('created_by', models.UUIDField(verbose_name='创建人id')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='修改时间')),
            ],
            options={
                'db_table': 'finance_email_template',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailtemplate',
            index=models.Index(
                fields=['workspace_id', 'scenario', 'is_deleted'],
                name='idx_fin_email_tpl_ws_sc',
            ),
        ),
        # ---------------- EmailSendLog ----------------
        migrations.CreateModel(
            name='EmailSendLog',
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
                        default='MATERIALS_TASK', max_length=32, verbose_name='目标对象类型'
                    ),
                ),
                (
                    'target_id',
                    models.UUIDField(blank=True, null=True, verbose_name='目标对象id'),
                ),
                (
                    'smtp_config_id',
                    models.UUIDField(blank=True, null=True, verbose_name='所用 SMTP 配置id'),
                ),
                (
                    'email_template_id',
                    models.UUIDField(blank=True, null=True, verbose_name='所用模板id'),
                ),
                ('to_addresses', models.JSONField(default=list, verbose_name='收件人列表')),
                ('cc_addresses', models.JSONField(default=list, verbose_name='抄送列表')),
                (
                    'subject',
                    models.CharField(
                        blank=True, default='', max_length=512,
                        verbose_name='渲染后的主题',
                    ),
                ),
                (
                    'body_preview',
                    models.CharField(
                        blank=True, default='', max_length=500,
                        verbose_name='正文预览（前 500 字）',
                    ),
                ),
                (
                    'attachment_keys',
                    models.JSONField(default=list, verbose_name='附件 OSS key 列表'),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('queued', '排队中'),
                            ('sending', '发送中'),
                            ('sent', '已发送'),
                            ('failed', '失败'),
                            ('retried', '已重发'),
                        ],
                        default='queued',
                        max_length=16,
                        verbose_name='发送状态',
                    ),
                ),
                ('error_message', models.TextField(blank=True, default='', verbose_name='错误信息')),
                (
                    'retry_count',
                    models.PositiveSmallIntegerField(default=0, verbose_name='重试次数'),
                ),
                ('sent_by', models.UUIDField(verbose_name='发送人id')),
                (
                    'sent_at',
                    models.DateTimeField(blank=True, null=True, verbose_name='发送完成时间'),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True, db_index=True, verbose_name='创建时间'
                    ),
                ),
            ],
            options={
                'db_table': 'finance_email_send_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailsendlog',
            index=models.Index(
                fields=['workspace_id', '-created_at'],
                name='idx_fin_send_ws_time',
            ),
        ),
        migrations.AddIndex(
            model_name='emailsendlog',
            index=models.Index(
                fields=['target_type', 'target_id'],
                name='idx_fin_send_target',
            ),
        ),
    ]
