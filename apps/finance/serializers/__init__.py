# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance serializers package.
"""
from .audit_log import FinanceAuditLogOutputSerializer
from .document_generation import (
    AIFillRequestSerializer,
    DocumentGenerationCreateSerializer,
    DocumentGenerationOutputSerializer,
)
from .document_template import (
    DocumentTemplateOutputSerializer,
    DocumentTemplateUpdateSerializer,
    DocumentTemplateUploadSerializer,
)
from .email_send_log import (
    EmailSendLogOutputSerializer,
    MaterialsTaskSendSerializer,
)
from .email_template import (
    EmailTemplateCreateSerializer,
    EmailTemplateOutputSerializer,
    EmailTemplateUpdateSerializer,
)
from .materials_task import (
    MaterialsTaskCreateSerializer,
    MaterialsTaskOutputSerializer,
    MaterialsTaskPackSerializer,
    MaterialsTaskReviewSerializer,
    MaterialsTaskUpdateSelectionSerializer,
)
from .project import FinanceProjectInputSerializer, FinanceProjectOutputSerializer
from .smtp_config import (
    SmtpConfigCreateSerializer,
    SmtpConfigOutputSerializer,
    SmtpConfigTestSerializer,
    SmtpConfigUpdateSerializer,
)

__all__ = [
    'FinanceProjectInputSerializer',
    'FinanceProjectOutputSerializer',
    'FinanceAuditLogOutputSerializer',
    'DocumentTemplateUploadSerializer',
    'DocumentTemplateUpdateSerializer',
    'DocumentTemplateOutputSerializer',
    'DocumentGenerationCreateSerializer',
    'DocumentGenerationOutputSerializer',
    'AIFillRequestSerializer',
    'MaterialsTaskCreateSerializer',
    'MaterialsTaskOutputSerializer',
    'MaterialsTaskPackSerializer',
    'MaterialsTaskReviewSerializer',
    'MaterialsTaskUpdateSelectionSerializer',
    'SmtpConfigCreateSerializer',
    'SmtpConfigUpdateSerializer',
    'SmtpConfigTestSerializer',
    'SmtpConfigOutputSerializer',
    'EmailTemplateCreateSerializer',
    'EmailTemplateUpdateSerializer',
    'EmailTemplateOutputSerializer',
    'MaterialsTaskSendSerializer',
    'EmailSendLogOutputSerializer',
]
