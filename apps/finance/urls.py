from django.urls import path

from . import views

app_name = 'finance'
# @formatter:off
urlpatterns = [
    path('ping', views.FinancePingView.as_view(), name='finance_ping'),
]
