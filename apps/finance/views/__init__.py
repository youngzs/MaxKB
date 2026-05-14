# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance views package
"""
from .audit_log import FinanceAuditLogExportView, FinanceAuditLogListView
from .document_generation import (
    DocumentGenerationAIFillView,
    DocumentGenerationConfirmView,
    DocumentGenerationDetailView,
    DocumentGenerationDownloadView,
    DocumentGenerationListView,
    DocumentGenerationPreviewView,
    DocumentGenerationRevokeView,
)
from .document_sensitivity import DocumentSensitivityView
from .document_template import DocumentTemplateDetailView, DocumentTemplateListView
from .email_send_log import EmailSendLogListView
from .email_template import EmailTemplateDetailView, EmailTemplateListView
from .materials_send import MaterialsTaskSendView
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
from .healthz import FinanceHealthzView
from .ping import FinancePingView
from .project import FinanceProjectDetailView, FinanceProjectListView
from .signed_download import SignedDownloadView
from .smtp_config import (
    SmtpConfigDetailView,
    SmtpConfigListView,
    SmtpConfigTestView,
)

__all__ = [
    'FinancePingView',
    'FinanceHealthzView',
    'SignedDownloadView',
    'FinanceAuditLogListView',
    'FinanceAuditLogExportView',
    'DocumentSensitivityView',
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
    'SmtpConfigListView',
    'SmtpConfigDetailView',
    'SmtpConfigTestView',
    'EmailTemplateListView',
    'EmailTemplateDetailView',
    'MaterialsTaskSendView',
    'EmailSendLogListView',
]
