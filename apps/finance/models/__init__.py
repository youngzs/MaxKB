# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance models package. Gate 2 added FinanceProject + FinanceAuditLog;
    Gate 3 adds DocumentTemplate + DocumentGeneration;
    Gate 4 adds MaterialsTask (materials packaging workflow).
"""
from .audit_log import FinanceAuditAction, FinanceAuditLog, FinanceAuditTargetType
from .document_generation import DocumentGeneration, GenerationStatus
from .document_template import DocumentTemplate, TemplateScenario
from .materials_task import MaterialsTask, MaterialsTaskStatus
from .project import FinanceProject, FinanceProjectStatus, FinanceProjectType

__all__ = [
    'FinanceProject',
    'FinanceProjectType',
    'FinanceProjectStatus',
    'FinanceAuditLog',
    'FinanceAuditTargetType',
    'FinanceAuditAction',
    'DocumentTemplate',
    'TemplateScenario',
    'DocumentGeneration',
    'GenerationStatus',
    'MaterialsTask',
    'MaterialsTaskStatus',
]
