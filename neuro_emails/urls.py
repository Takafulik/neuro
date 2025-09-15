from django.urls import path
from . import views

app_name = 'neuro_emails'

urlpatterns = [
    path('', views.email_home, name='home'),
    path('campaigns/', views.campaign_list, name='campaigns'),
    path('templates/', views.template_list, name='templates'),
    path('analytics/', views.email_analytics, name='analytics'),
]