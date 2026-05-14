# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance views package
"""
from .audit_log import FinanceAuditLogListView
from .document_generation import (
    DocumentGenerationAIFillView,
    DocumentGenerationConfirmView,
    DocumentGenerationDetailView,
    DocumentGenerationDownloadView,
    DocumentGenerationListView,
    DocumentGenerationPreviewView,
    DocumentGenerationRevokeView,
)
from .document_template import DocumentTemplateDetailView, DocumentTemplateListView
from .materials_task import (
    MaterialsTaskDetailView,
    MaterialsTaskListView,
    MaterialsTaskMatchView,
    MaterialsTaskPackView,
    MaterialsTaskParseView,
    MaterialsTaskReviewView,
    MaterialsTaskSelectionView,
    MaterialsTaskSubmitReviewView,
    MaterialsTaskSummarizeView,
    MaterialsTaskZipDownloadView,
)
from .ping import FinancePingView
from .project import FinanceProjectDetailView, FinanceProjectListView

__all__ = [
    'FinancePingView',
    'FinanceAuditLogListView',
    'FinanceProjectListView',
    'FinanceProjectDetailView',
    'DocumentTemplateListView',
    'DocumentTemplateDetailView',
    'DocumentGenerationListView',
    'DocumentGenerationDetailView',
    'DocumentGenerationConfirmView',
    'DocumentGenerationRevokeView',
    'DocumentGenerationPreviewView',
    'DocumentGenerationDownloadView',
    'DocumentGenerationAIFillView',
    'MaterialsTaskListView',
    'MaterialsTaskDetailView',
    'MaterialsTaskParseView',
    'MaterialsTaskMatchView',
    'MaterialsTaskSelectionView',
    'MaterialsTaskSummarizeView',
    'MaterialsTaskPackView',
    'MaterialsTaskSubmitReviewView',
    'MaterialsTaskReviewView',
    'MaterialsTaskZipDownloadView',
]
