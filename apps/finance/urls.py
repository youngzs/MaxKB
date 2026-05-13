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
]
