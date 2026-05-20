# Generated for MaxKB Finance — P2「进度归集」Gate 1（数据底座）
# Hand-written (same reason as 0003/0005/0007: the Windows dev environment
# cannot import the full Django app stack to run makemigrations — one upstream
# app needs the POSIX-only `pwd` module). Structurally mirrors the previous
# CreateModel / AddField migrations.
#
# 本迁移做三件事：
#   1. FinanceProject 加 owner_id / counterparty / current_stage_key 三个字段；
#   2. 新建 ProjectStageRecord 表（项目 × 子阶段）；
#   3. RunPython 回填存量项目 —— 回填 owner_id(=created_by) 与 current_stage_key，
#      并按类型模板预生成全部阶段行。回填逻辑复用 finance.constants.stage_templates
#      的纯函数（该模块零 finance.models 依赖，可被迁移安全导入）。
import uuid_utils.compat
from django.db import migrations, models


def _backfill_progress(apps, schema_editor):
    """回填存量项目的进度字段并预生成阶段记录。"""
    from finance.constants.stage_templates import (
        build_initial_stage_plan,
        resolve_current_stage_key,
    )

    FinanceProject = apps.get_model('finance', 'FinanceProject')
    ProjectStageRecord = apps.get_model('finance', 'ProjectStageRecord')
    db_alias = schema_editor.connection.alias

    new_records = []
    for project in FinanceProject.objects.using(db_alias).all():
        # updated_at 在 save(update_fields=...) 时不会被改动，但仍先取出，
        # 作为「进行中」阶段 entered_at 的最佳估计值（无真实阶段时间数据）。
        entered_estimate = project.updated_at

        if project.owner_id is None:
            project.owner_id = project.created_by
        project.current_stage_key = resolve_current_stage_key(
            project.project_type, project.status
        )
        project.save(using=db_alias, update_fields=['owner_id', 'current_stage_key'])

        for item in build_initial_stage_plan(project.project_type, project.status):
            is_active = item['stage_status'] == 'active'
            new_records.append(
                ProjectStageRecord(
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    stage_key=item['stage_key'],
                    stage_order=item['stage_order'],
                    planned_at=None,
                    actual_at=None,
                    owner_id=None,  # 空则继承项目负责人
                    entered_at=entered_estimate if is_active else None,
                    status=item['stage_status'],
                    note='',
                )
            )

    if new_records:
        ProjectStageRecord.objects.using(db_alias).bulk_create(
            new_records, batch_size=200
        )


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0008_workflowrun_cancelled_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='financeproject',
            name='owner_id',
            field=models.UUIDField(blank=True, null=True, verbose_name='项目负责人id'),
        ),
        migrations.AddField(
            model_name='financeproject',
            name='counterparty',
            field=models.CharField(
                blank=True, default='', max_length=200, verbose_name='主要对手方机构'
            ),
        ),
        migrations.AddField(
            model_name='financeproject',
            name='current_stage_key',
            field=models.CharField(
                blank=True, default='', max_length=32, verbose_name='当前子阶段key'
            ),
        ),
        migrations.CreateModel(
            name='ProjectStageRecord',
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
                ('project_id', models.UUIDField(db_index=True, verbose_name='融资项目id')),
                ('stage_key', models.CharField(max_length=32, verbose_name='子阶段key')),
                ('stage_order', models.IntegerField(verbose_name='阶段顺序号')),
                (
                    'planned_at',
                    models.DateTimeField(
                        blank=True, null=True, verbose_name='计划完成时间'
                    ),
                ),
                (
                    'actual_at',
                    models.DateTimeField(
                        blank=True, null=True, verbose_name='实际完成时间'
                    ),
                ),
                (
                    'owner_id',
                    models.UUIDField(
                        blank=True,
                        null=True,
                        verbose_name='阶段责任人id（空则继承项目负责人）',
                    ),
                ),
                (
                    'entered_at',
                    models.DateTimeField(
                        blank=True, null=True, verbose_name='进入本阶段时间'
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', '未开始'),
                            ('active', '进行中'),
                            ('done', '已完成'),
                            ('skipped', '已跳过'),
                        ],
                        default='pending',
                        max_length=16,
                        verbose_name='阶段状态',
                    ),
                ),
                ('note', models.TextField(blank=True, default='', verbose_name='备注')),
                (
                    'created_at',
                    models.DateTimeField(auto_now_add=True, verbose_name='创建时间'),
                ),
                (
                    'updated_at',
                    models.DateTimeField(auto_now=True, verbose_name='修改时间'),
                ),
            ],
            options={
                'db_table': 'finance_project_stage_record',
                'ordering': ['project_id', 'stage_order'],
            },
        ),
        migrations.AddIndex(
            model_name='projectstagerecord',
            index=models.Index(
                fields=['workspace_id', 'project_id', 'stage_order'],
                name='idx_fin_stage_ws_pj_ord',
            ),
        ),
        migrations.AddIndex(
            model_name='projectstagerecord',
            index=models.Index(fields=['status'], name='idx_fin_stage_status'),
        ),
        # 回填只往本迁移新建的表/字段写数据；回滚时这些表/字段会被一并删除，
        # 故反向操作为 noop。
        migrations.RunPython(_backfill_progress, migrations.RunPython.noop),
    ]
