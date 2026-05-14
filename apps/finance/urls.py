from django.urls import path

from . import views

app_name = 'finance'
# @formatter:off
urlpatterns = [
    path('ping', views.FinancePingView.as_view(), name='finance_ping'),
    # ---- Gate 6 Track C: real health probe ----
    path('healthz', views.FinanceHealthzView.as_view(), name='finance_healthz'),
    # ---- Gate 6 Track C: signed-URL public download ----
    # Token IS the auth — do NOT nest under workspace/<workspace_id>/.
    path(
        'download/<str:token>',
        views.SignedDownloadView.as_view(),
        name='signed_download',
    ),
    path(
        'workspace/<str:workspace_id>/project',
        views.FinanceProjectListView.as_view(),
        name='project_list',
    ),
    path(
        'workspace/<str:workspace_id>/project/<uuid:pk>',
        views.FinanceProjectDetailView.as_view(),
        name='project_detail',
    ),
    # ---- Gate 3 Track A: document templates ----
    path(
        'workspace/<str:workspace_id>/template',
        views.DocumentTemplateListView.as_view(),
        name='template_list',
    ),
    path(
        'workspace/<str:workspace_id>/template/<uuid:pk>',
        views.DocumentTemplateDetailView.as_view(),
        name='template_detail',
    ),
    # ---- Gate 3 Track A: document generations ----
    # NOTE: the `ai-fill` collection route is registered BEFORE the
    # `<uuid:pk>` routes so it isn't shadowed by the dispatcher.
    path(
        'workspace/<str:workspace_id>/generation/ai-fill',
        views.DocumentGenerationAIFillView.as_view(),
        name='generation_ai_fill',
    ),
    path(
        'workspace/<str:workspace_id>/generation',
        views.DocumentGenerationListView.as_view(),
        name='generation_list',
    ),
    path(
        'workspace/<str:workspace_id>/generation/<uuid:pk>',
        views.DocumentGenerationDetailView.as_view(),
        name='generation_detail',
    ),
    path(
        'workspace/<str:workspace_id>/generation/<uuid:pk>/confirm',
        views.DocumentGenerationConfirmView.as_view(),
        name='generation_confirm',
    ),
    path(
        'workspace/<str:workspace_id>/generation/<uuid:pk>/revoke',
        views.DocumentGenerationRevokeView.as_view(),
        name='generation_revoke',
    ),
    path(
        'workspace/<str:workspace_id>/generation/<uuid:pk>/preview',
        views.DocumentGenerationPreviewView.as_view(),
        name='generation_preview',
    ),
    path(
        'workspace/<str:workspace_id>/generation/<uuid:pk>/download',
        views.DocumentGenerationDownloadView.as_view(),
        name='generation_download',
    ),
    # ---- Gate 4 Track A: materials task ----
    path(
        'workspace/<str:workspace_id>/materials-task',
        views.MaterialsTaskListView.as_view(),
        name='materials_task_list',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>',
        views.MaterialsTaskDetailView.as_view(),
        name='materials_task_detail',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/parse',
        views.MaterialsTaskParseView.as_view(),
        name='materials_task_parse',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/match',
        views.MaterialsTaskMatchView.as_view(),
        name='materials_task_match',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/selection',
        views.MaterialsTaskSelectionView.as_view(),
        name='materials_task_selection',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/summarize',
        views.MaterialsTaskSummarizeView.as_view(),
        name='materials_task_summarize',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/pack',
        views.MaterialsTaskPackView.as_view(),
        name='materials_task_pack',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/submit-review',
        views.MaterialsTaskSubmitReviewView.as_view(),
        name='materials_task_submit_review',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/review',
        views.MaterialsTaskReviewView.as_view(),
        name='materials_task_review',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/zip',
        views.MaterialsTaskZipDownloadView.as_view(),
        name='materials_task_zip',
    ),
    # ---- Gate 5 Track B: SMTP send closure ----
    path(
        'workspace/<str:workspace_id>/smtp-config',
        views.SmtpConfigListView.as_view(),
        name='smtp_config_list',
    ),
    path(
        'workspace/<str:workspace_id>/smtp-config/<uuid:pk>',
        views.SmtpConfigDetailView.as_view(),
        name='smtp_config_detail',
    ),
    path(
        'workspace/<str:workspace_id>/smtp-config/<uuid:pk>/test',
        views.SmtpConfigTestView.as_view(),
        name='smtp_config_test',
    ),
    path(
        'workspace/<str:workspace_id>/email-template',
        views.EmailTemplateListView.as_view(),
        name='email_template_list',
    ),
    path(
        'workspace/<str:workspace_id>/email-template/<uuid:pk>',
        views.EmailTemplateDetailView.as_view(),
        name='email_template_detail',
    ),
    path(
        'workspace/<str:workspace_id>/materials-task/<uuid:pk>/send',
        views.MaterialsTaskSendView.as_view(),
        name='materials_task_send',
    ),
    path(
        'workspace/<str:workspace_id>/email-send-log',
        views.EmailSendLogListView.as_view(),
        name='email_send_log_list',
    ),
    # ---- Gate 5 Track C: audit log admin page ----
    path(
        'workspace/<str:workspace_id>/audit-log',
        views.FinanceAuditLogListView.as_view(),
        name='audit_log_list',
    ),
    # ---- Gate 6 Track A4: audit log CSV export ----
    # Registered BEFORE the list route would otherwise win — list uses
    # the exact ``audit-log`` segment so we're fine, but keeping ``export``
    # as a sibling under ``audit-log/`` mirrors the rest of the module's
    # action-style URLs.
    path(
        'workspace/<str:workspace_id>/audit-log/export',
        views.FinanceAuditLogExportView.as_view(),
        name='audit_log_export',
    ),
    # ---- Gate 6 Track A3: document sensitivity PATCH ----
    path(
        'workspace/<str:workspace_id>/document-sensitivity/<uuid:document_id>',
        views.DocumentSensitivityView.as_view(),
        name='document_sensitivity',
    ),
]
