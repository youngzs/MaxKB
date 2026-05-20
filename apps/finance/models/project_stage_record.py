# coding=utf-8
"""
    @project: MaxKB
    @file： project_stage_record.py
    @desc: ProjectStageRecord — P2「进度归集」的阶段记录表。

    每个融资项目 × 每个子阶段一行（项目创建时按 constants/stage_templates.py
    的类型模板预生成全部阶段行）。阶段流转（advance / rollback，Gate 2）写入
    actual_at / entered_at 并派生大状态。回退会**追加**新记录留痕，因此
    (project_id, stage_key) 不设唯一约束。

    风险标记（黄/红）不落表 —— 由 Gate 4 的规则在查询时实时计算。

    沿用 finance 既有约定：UUID7 主键、workspace_id 软 FK（CharField）、
    created_at / updated_at 自带时间戳字段。
"""
import uuid_utils.compat as uuid
from django.db import models


class ProjectStageStatus(models.TextChoices):
    """子阶段记录状态。取值须与 constants/stage_templates.py 的 STAGE_STATUS_* 一致。"""

    PENDING = 'pending', '未开始'
    ACTIVE = 'active', '进行中'
    DONE = 'done', '已完成'
    SKIPPED = 'skipped', '已跳过'


class ProjectStageRecord(models.Model):
    """
    融资项目子阶段记录。`stage_key` 指向类型模板里的稳定标识，`stage_order`
    冗余存模板里的序号以便排序。
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.CharField(max_length=64, db_index=True, verbose_name='工作空间id')
    project_id = models.UUIDField(db_index=True, verbose_name='融资项目id')
    stage_key = models.CharField(max_length=32, verbose_name='子阶段key')
    stage_order = models.IntegerField(verbose_name='阶段顺序号')
    planned_at = models.DateTimeField(null=True, blank=True, verbose_name='计划完成时间')
    actual_at = models.DateTimeField(null=True, blank=True, verbose_name='实际完成时间')
    owner_id = models.UUIDField(
        null=True, blank=True, verbose_name='阶段责任人id（空则继承项目负责人）'
    )
    entered_at = models.DateTimeField(null=True, blank=True, verbose_name='进入本阶段时间')
    status = models.CharField(
        max_length=16,
        choices=ProjectStageStatus.choices,
        default=ProjectStageStatus.PENDING,
        verbose_name='阶段状态',
    )
    note = models.TextField(blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_project_stage_record'
        ordering = ['project_id', 'stage_order']
        indexes = [
            models.Index(
                fields=['workspace_id', 'project_id', 'stage_order'],
                name='idx_fin_stage_ws_pj_ord',
            ),
            models.Index(fields=['status'], name='idx_fin_stage_status'),
        ]

    def __str__(self):
        return f'{self.project_id}:{self.stage_key} [{self.status}]'
