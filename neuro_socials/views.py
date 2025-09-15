from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def social_home(request):
    """Social media home view"""
    return render(request, 'neuro_socials/home.html')


@login_required
def post_list(request):
    """List all posts"""
    return render(request, 'neuro_socials/posts.html')


@login_required
def schedule_post(request):
    """Schedule new post"""
    return render(request, 'neuro_socials/schedule.html')


@login_required
def social_analytics(request):
    """Social media analytics"""
    return render(request, 'neuro_socials/analytics.html')


@login_required
def index(request):
    """Neuro Socials app index view"""
    return render(request, 'neuro_socials/index.html')
