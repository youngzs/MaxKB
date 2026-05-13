# coding=utf-8
"""
    @project: MaxKB
    @file： materials_task.py
    @desc: MaterialsTask — orchestrates the "材料整理" (materials packaging)
    workflow for a financing project. Free-form requirement list (pasted from
    email or extracted from a docx) gets parsed into structured items, each
    item is matched against the project's whitelisted knowledge bases (with
    a SENSITIVITY GATE), a human curates the final selection, AI generates
    short summaries, and finally the documents are packed into a zip ready
    for review and external sharing (Gate 5).

    State machine:
        draft → parsing → matching → pending_review → approved
                                                    ↘ rejected
                                                    ↘ sent (Gate 5)
        any → failed (sink for unrecoverable errors)
"""
import uuid_utils.compat as uuid
from django.db import models


class MaterialsTaskStatus(models.TextChoices):
    """材料整理任务状态机"""
    DRAFT = 'draft', '草稿'
    PARSING = 'parsing', '解析中'
    MATCHING = 'matching', '匹配中'
    PENDING_REVIEW = 'pending_review', '待审核'
    APPROVED = 'approved', '已审核'
    SENT = 'sent', '已发送'  # Gate 5 will transition into this
    REJECTED = 'rejected', '已退回'
    FAILED = 'failed', '失败'


class MaterialsTask(models.Model):
    """
    材料整理任务主表。每行代表一次"按对方清单准备一套融资材料"的工作单。

    `parsed_items` — list of structured requirement items derived from
    `requirement_text` via LLM (or fallback heuristic). Shape:
        [{key, label, description, required}]

    `matched_documents` — search results from project KBs, one row per
    (item × candidate document) pair, filtered by sensitivity. Shape:
        [{item_key, document_id, document_name, sensitivity_level,
          score, ai_summary, snippet}]

    `selected_documents` — final curated set of document_ids the user
    wants packaged into the zip. Subset of matched_documents.document_id.
    """
    id = models.UUIDField(
        primary_key=True, default=uuid.uuid7, editable=False, verbose_name='主键id'
    )
    workspace_id = models.UUIDField(db_index=True, verbose_name='工作空间id')
    project_id = models.UUIDField(db_index=True, verbose_name='融资项目id')
    title = models.CharField(max_length=200, verbose_name='任务标题')
    requirement_text = models.TextField(
        blank=True, default='', verbose_name='需求清单原文'
    )
    requirement_file_oss_key = models.CharField(
        max_length=500, blank=True, default='', verbose_name='需求清单文件 OSS key'
    )
    parsed_items = models.JSONField(default=list, verbose_name='结构化需求项')
    matched_documents = models.JSONField(
        default=list, verbose_name='匹配到的候选文档（含敏感等级与AI概要）'
    )
    selected_documents = models.JSONField(
        default=list, verbose_name='最终选定的文档id列表'
    )
    zip_oss_key = models.CharField(
        max_length=500, blank=True, default='', verbose_name='打包 zip OSS key'
    )
    status = models.CharField(
        max_length=20,
        choices=MaterialsTaskStatus.choices,
        default=MaterialsTaskStatus.DRAFT,
        verbose_name='状态',
    )
    reviewer_id = models.UUIDField(null=True, blank=True, verbose_name='审核人id')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    review_comment = models.TextField(
        blank=True, default='', verbose_name='审核意见'
    )
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    is_deleted = models.BooleanField(
        default=False, db_index=True, verbose_name='是否已删除'
    )
    created_by = models.UUIDField(verbose_name='创建人id')
    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='修改时间')

    class Meta:
        db_table = 'finance_materials_task'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['workspace_id', 'project_id', '-created_at'],
                name='idx_fin_mat_task_ws_pj_t',
            ),
            models.Index(fields=['status'], name='idx_fin_mat_task_status'),
        ]

    def __str__(self):
        return f'{self.title} [{self.status}]'
