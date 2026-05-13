# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance views package
"""
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
from .ping import FinancePingView
from .project import FinanceProjectDetailView, FinanceProjectListView

__all__ = [
    'FinancePingView',
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
]
