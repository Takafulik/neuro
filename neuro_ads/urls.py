from django.urls import path
from . import views

app_name = 'neuro_ads'

urlpatterns = [
    # Dashboard
    path('', views.ads_home, name='home'),
    path('dashboard/', views.ads_home, name='ads_home'),
    
    # Campaign management
    path('campaigns/', views.campaign_list, name='campaigns'),
    path('campaigns/create/', views.create_campaign, name='create_campaign'),
    path('campaigns/<int:campaign_id>/', views.campaign_detail, name='campaign_detail'),
    path('campaigns/<int:campaign_id>/optimize/', views.optimize_campaign_budget, name='optimize_budget'),
    path('campaigns/<int:campaign_id>/pause/', views.pause_campaign, name='pause_campaign'),
    path('campaigns/<int:campaign_id>/resume/', views.resume_campaign, name='resume_campaign'),
    
    # A/B Testing
    path('ab-tests/', views.ab_tests_list, name='ab_tests'),
    path('ab-tests/<int:test_id>/', views.ab_test_detail, name='ab_test_detail'),
    path('campaigns/<int:campaign_id>/ab-test/create/', views.create_ab_test, name='create_ab_test'),
    
    # Platform connections
    path('platforms/', views.platform_connections, name='platform_connections'),
    
    # Analytics
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    
    # Automation
    path('automation/', views.automation_rules, name='automation_rules'),
]