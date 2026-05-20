# coding=utf-8
"""
    @project: MaxKB
    @file： project.py
    @desc: FinanceProject — workspace-scoped financing project record.

    Mirrors the conventions in apps/application/models/application.py:
      - UUID primary key seeded by uuid_utils.compat.uuid7
      - workspace_id is a soft FK (CharField/UUID), not a Django ForeignKey,
        because workspaces are managed by another app and addressed by id.
      - Soft delete via is_deleted flag.

    Note: we intentionally do NOT extend AppModelMixin here — the mixin
    exposes create_time/update_time, whereas Gate-2 spec requires the
    created_at/updated_at field names. Keeping our own timestamp fields
    keeps the API contract crisp.
"""
import uuid_utils.compat as uuid
from django.db import models
from django.db.models import Q, UniqueConstraint


class FinanceProjectType(models.TextChoices):
    """融资项目类型"""
    BANK_LOAN = 'bank_loan', '银行贷款'
    BOND = 'bond', '债券'
    TRUST = 'trust', '信托'
    ABS = 'abs', 'ABS'
    OTHER = 'other', '其他'


class FinanceProjectStatus(models.TextChoices):
    """项目状态"""
    PREPARING = 'preparing', '筹备'
    MATERIALS = 'materials', '材料准备'
    ENGAGING = 'engaging', '对接中'
    LANDED = 'landed', '已落地'
    TERMINATED = 'terminated', '已终止'


class FinanceProject(models.Model):
    """
    融资项目主表。每个项目归属于一个工作空间，并可关联若干知识库作为
    其素材白名单（knowledge_base_ids）。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id')
    workspace_id = models.CharField(max_length=64, db_index=True, verbose_name='工作空间id')
    name = models.CharField(max_length=200, verbose_name='项目名称')
    code = models.CharField(max_length=64, blank=True, default='', verbose_name='项目编码')
    project_type = models.CharField(
        max_length=32,
        choices=FinanceProjectType.choices,
        default=FinanceProjectType.BANK_LOAN,
        verbose_name='项目类型',
    )
    target_amount = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True, verbose_name='目标金额'
    )
    currency = models.CharField(max_length=10, default='CNY', verbose_name='币种')
    status = models.CharField(
        max_length=32,
        choices=FinanceProjectStatus.choices,
        default=FinanceProjectStatus.PREPARING,
        verbose_name='项目状态',
    )
    region = models.CharField(max_length=100, blank=True, default='', verbose_name='地区')
    industry_code = models.CharField(max_length=32, blank=True, default='', verbose_name='行业代码')
    knowledge_base_ids = models.JSONField(default=list, verbose_name='关联知识库白名单')
    description = models.TextField(blank=True, default='', verbose_name='项目描述')
    # --- P2「进度归集」新增字段（见 docs/finance-p2-progress-design.md §5.1）---
    owner_id = models.UUIDField(
        null=True, blank=True, verbose_name='项目负责人id'
    )  # DR-P2-03；迁移时回填 = created_by
    counterparty = models.CharField(
        max_length=200, blank=True, default='', verbose_name='主要对手方机构'
    )  # DR-P2-02 free-text 字段，不拆独立实体
    current_stage_key = models.CharField(
        max_length=32, blank=True, default='', verbose_name='当前子阶段key'
    )  # 指向类型模板里的细阶段；大状态 status 由它派生
    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name='是否已删除')
    created_by = models.UUIDField(verbose_name='创建人id')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_project'
        ordering = ['-created_at']
        constraints = [
            # 同一 workspace 下，非空 code 唯一
            UniqueConstraint(
                fields=['workspace_id', 'code'],
                condition=Q(code__gt=''),
                name='uniq_finance_project_workspace_code',
            ),
        ]

    def __str__(self):
        return self.name
