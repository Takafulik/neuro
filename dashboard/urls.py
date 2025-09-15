from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('neuro-ads/', views.neuro_ads_dashboard, name='neuro_ads'),
    path('social-pulse/', views.social_pulse_dashboard, name='social_pulse'),
    path('email-cortex/', views.email_cortex_dashboard, name='email_cortex'),
    path('analytics/', views.analytics_overview, name='analytics'),
    path('settings/', views.dashboard_settings, name='settings'),
]