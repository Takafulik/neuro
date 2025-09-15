from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication URLs
    path('login/', views.BusinessLoginView.as_view(), name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # User profile and onboarding
    path('profile/', views.profile_view, name='profile'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    
    # Dashboard redirect
    path('dashboard-redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    
    # AJAX endpoints
    path('check-username/', views.check_username_availability, name='check_username'),
    path('check-email/', views.check_email_availability, name='check_email'),
]