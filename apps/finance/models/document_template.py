# coding=utf-8
"""
    @project: MaxKB
    @file： document_template.py
    @desc: DocumentTemplate — workspace-scoped docx template that owns a set
    of placeholders extracted from its docx body via docxtpl.

    Conventions mirror FinanceProject:
      - UUID primary key seeded by uuid_utils.compat.uuid7
      - workspace_id is a soft FK (UUIDField + index), not a Django FK
      - Soft delete via is_deleted flag
      - JSON placeholders shape:
          [{key, label, type, required, ai_hint, enum_options}, ...]
        where type ∈ {'text', 'long_text', 'number', 'date', 'enum'}.
    The actual docx file lives in OSS (`knowledge.models.File`), keyed by
    `docx_oss_key`. The `version` integer is bumped whenever the binary
    is replaced, so generations can snapshot the version that rendered them.
"""
import uuid_utils.compat as uuid
from django.db import models


class TemplateScenario(models.TextChoices):
    INTERNAL_REPORT = 'internal_report', '内部汇报'
    MEETING = 'meeting', '上会材料'
    SYSTEM_PROCESS = 'system_process', '系统流程'
    OTHER = 'other', '其他'


class DocumentTemplate(models.Model):
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.CharField(max_length=64, db_index=True, verbose_name='工作空间id')
    name = models.CharField(max_length=200, verbose_name='模板名称')
    scenario = models.CharField(
        max_length=32,
        choices=TemplateScenario.choices,
        default=TemplateScenario.OTHER,
        verbose_name='模板场景',
    )
    docx_oss_key = models.CharField(max_length=500, verbose_name='docx OSS key')
    placeholders = models.JSONField(
        default=list,
        verbose_name='占位符元数据 [{key,label,type,required,ai_hint,enum_options}]',
    )
    version = models.PositiveIntegerField(default=1, verbose_name='版本号')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name='是否已删除')
    created_by = models.UUIDField(verbose_name='创建人id')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_document_template'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['workspace_id', 'scenario'], name='idx_fin_doc_tpl_ws_scn'
            ),
        ]

    def __str__(self):
        return self.name
