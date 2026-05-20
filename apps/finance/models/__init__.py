# coding=utf-8
"""
    @project: MaxKB
    @file： __init__.py
    @desc: finance models package. Gate 2 added FinanceProject + FinanceAuditLog;
    Gate 3 adds DocumentTemplate + DocumentGeneration;
    Gate 4 adds MaterialsTask (materials packaging workflow);
    Gate 5 adds SmtpConfig + EmailTemplate + EmailSendLog (send pipeline);
    P2 Gate 1 adds ProjectStageRecord (progress tracking) + FinanceProject
    progress fields (owner_id / counterparty / current_stage_key).
"""
from .audit_log import FinanceAuditAction, FinanceAuditLog, FinanceAuditTargetType
from .document_generation import DocumentGeneration, GenerationStatus
from .document_template import DocumentTemplate, TemplateScenario
from .email_send_log import EmailSendLog, EmailSendStatus
from .email_template import EmailTemplate, EmailTemplateScenario
from .materials_task import MaterialsTask, MaterialsTaskStatus
from .project import FinanceProject, FinanceProjectStatus, FinanceProjectType
from .project_stage_record import ProjectStageRecord, ProjectStageStatus
from .smtp_config import SmtpConfig
from .workflow_run import WorkflowRun, WorkflowRunStatus, WorkflowRunTargetType

__all__ = [
    'FinanceProject',
    'FinanceProjectType',
    'FinanceProjectStatus',
    'ProjectStageRecord',
    'ProjectStageStatus',
    'FinanceAuditLog',
    'FinanceAuditTargetType',
    'FinanceAuditAction',
    'DocumentTemplate',
    'TemplateScenario',
    'DocumentGeneration',
    'GenerationStatus',
    'MaterialsTask',
    'MaterialsTaskStatus',
    'SmtpConfig',
    'EmailTemplate',
    'EmailTemplateScenario',
    'EmailSendLog',
    'EmailSendStatus',
    'WorkflowRun',
    'WorkflowRunStatus',
    'WorkflowRunTargetType',
]
