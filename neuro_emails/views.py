from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def email_home(request):
    """Email marketing home view"""
    return render(request, 'neuro_emails/home.html')


@login_required
def campaign_list(request):
    """List all email campaigns"""
    return render(request, 'neuro_emails/campaigns.html')


@login_required
def template_list(request):
    """List email templates"""
    return render(request, 'neuro_emails/templates.html')


@login_required
def email_analytics(request):
    """Email analytics"""
    return render(request, 'neuro_emails/analytics.html')


@login_required
def index(request):
    """Neuro Emails app index view"""
    return render(request, 'neuro_emails/index.html')
