# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance views package
"""
from .ai_status import FinanceAiStatusView
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
from .document_template import (
    DocumentTemplateDetailView,
    DocumentTemplateDownloadView,
    DocumentTemplateListView,
    DocumentTemplateSampleView,
)
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
from .system_info import FinanceSystemInfoView
from .workflow_run import (
    FinanceWorkflowRunListView,
    WorkflowRunCancelView,
    WorkflowRunRetryView,
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
    'DocumentTemplateSampleView',
    'DocumentTemplateDownloadView',
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
    'FinanceSystemInfoView',
    'FinanceWorkflowRunListView',
    'WorkflowRunRetryView',
    'WorkflowRunCancelView',
    'FinanceAiStatusView',
]
