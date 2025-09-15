from django.urls import path
from . import views

app_name = 'neuro_socials'

urlpatterns = [
    path('', views.social_home, name='home'),
    path('posts/', views.post_list, name='posts'),
    path('schedule/', views.schedule_post, name='schedule'),
    path('analytics/', views.social_analytics, name='analytics'),
]