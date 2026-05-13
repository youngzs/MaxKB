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
from .project import FinanceProjectInputSerializer, FinanceProjectOutputSerializer

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
]
