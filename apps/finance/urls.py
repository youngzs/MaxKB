from django.urls import path

from . import views

app_name = 'finance'
# @formatter:off
urlpatterns = [
    path('ping', views.FinancePingView.as_view(), name='finance_ping'),
    path(
        'workspace/<uuid:workspace_id>/project',
        views.FinanceProjectListView.as_view(),
        name='project_list',
    ),
    path(
        'workspace/<uuid:workspace_id>/project/<uuid:pk>',
        views.FinanceProjectDetailView.as_view(),
        name='project_detail',
    ),
    # ---- Gate 3 Track A: document templates ----
    path(
        'workspace/<uuid:workspace_id>/template',
        views.DocumentTemplateListView.as_view(),
        name='template_list',
    ),
    path(
        'workspace/<uuid:workspace_id>/template/<uuid:pk>',
        views.DocumentTemplateDetailView.as_view(),
        name='template_detail',
    ),
    # ---- Gate 3 Track A: document generations ----
    # NOTE: the `ai-fill` collection route is registered BEFORE the
    # `<uuid:pk>` routes so it isn't shadowed by the dispatcher.
    path(
        'workspace/<uuid:workspace_id>/generation/ai-fill',
        views.DocumentGenerationAIFillView.as_view(),
        name='generation_ai_fill',
    ),
    path(
        'workspace/<uuid:workspace_id>/generation',
        views.DocumentGenerationListView.as_view(),
        name='generation_list',
    ),
    path(
        'workspace/<uuid:workspace_id>/generation/<uuid:pk>',
        views.DocumentGenerationDetailView.as_view(),
        name='generation_detail',
    ),
    path(
        'workspace/<uuid:workspace_id>/generation/<uuid:pk>/confirm',
        views.DocumentGenerationConfirmView.as_view(),
        name='generation_confirm',
    ),
    path(
        'workspace/<uuid:workspace_id>/generation/<uuid:pk>/revoke',
        views.DocumentGenerationRevokeView.as_view(),
        name='generation_revoke',
    ),
    path(
        'workspace/<uuid:workspace_id>/generation/<uuid:pk>/preview',
        views.DocumentGenerationPreviewView.as_view(),
        name='generation_preview',
    ),
    path(
        'workspace/<uuid:workspace_id>/generation/<uuid:pk>/download',
        views.DocumentGenerationDownloadView.as_view(),
        name='generation_download',
    ),
]
