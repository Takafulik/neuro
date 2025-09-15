from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json


@login_required
def dashboard_home(request):
    """Main dashboard home view"""
    user = request.user
    
    # Check if user needs onboarding
    if not user.onboarding_completed:
        return redirect('users:onboarding')
    
    # Sample data - in production this would come from your models/APIs
    context = {
        'user': user,
        'current_time': timezone.now(),
        
        # Dashboard overview stats
        'overview_stats': {
            'total_campaigns': 12,
            'active_campaigns': 8,
            'total_spend': 15420.50,
            'total_revenue': 87350.25,
            'roi': 566.2,
            'leads_generated': 342,
            'emails_sent': 15684,
            'social_posts': 156,
        },
        
        # Feature status
        'neuro_ads_enabled': user.neuro_ads_enabled,
        'omni_social_enabled': user.omni_social_enabled,
        'email_cortex_enabled': user.email_cortex_enabled,
        
        # Recent activity (mock data)
        'recent_activities': [
            {
                'type': 'campaign_created',
                'title': 'New Google Ads campaign launched',
                'description': 'AI-generated "Spring Collection" campaign is now live',
                'time': '2 hours ago',
                'icon': 'ads'
            },
            {
                'type': 'social_post',
                'title': 'Social media post published',
                'description': 'LinkedIn post about industry trends generated engagement',
                'time': '4 hours ago',
                'icon': 'social'
            },
            {
                'type': 'email_campaign',
                'title': 'Email sequence completed',
                'description': 'Lead nurturing sequence achieved 24% open rate',
                'time': '6 hours ago',
                'icon': 'email'
            },
        ],
        
        # Quick actions
        'quick_actions': [
            {'name': 'Create Campaign', 'url': 'dashboard:neuro_ads', 'icon': 'ads'},
            {'name': 'Schedule Post', 'url': 'dashboard:social_pulse', 'icon': 'social'},
            {'name': 'Send Email', 'url': 'dashboard:email_cortex', 'icon': 'email'},
            {'name': 'View Analytics', 'url': 'dashboard:analytics', 'icon': 'chart'},
        ]
    }
    
    return render(request, 'dashboard/home.html', context)


@login_required
def neuro_ads_dashboard(request):
    """Neuro-Ads Engine dashboard"""
    if not request.user.neuro_ads_enabled:
        messages.warning(request, 'Neuro-Ads Engine is not enabled for your account.')
        return redirect('dashboard:home')
    
    context = {
        'user': request.user,
        'campaigns': [
            {
                'id': 1,
                'name': 'Spring Collection 2024',
                'platform': 'Google Ads',
                'status': 'Active',
                'budget': 1500.00,
                'spent': 1245.50,
                'impressions': 45678,
                'clicks': 1234,
                'conversions': 67,
                'ctr': 2.7,
                'cpc': 1.01,
                'created': '2024-03-01'
            },
            {
                'id': 2,
                'name': 'B2B Lead Generation',
                'platform': 'LinkedIn Ads',
                'status': 'Active',
                'budget': 2000.00,
                'spent': 876.25,
                'impressions': 23456,
                'clicks': 567,
                'conversions': 34,
                'ctr': 2.4,
                'cpc': 1.55,
                'created': '2024-02-28'
            },
        ],
        'ai_insights': [
            'Your Google Ads campaigns are performing 15% above industry average',
            'Consider increasing budget for "Spring Collection" - high conversion potential',
            'LinkedIn campaigns show strong engagement in the afternoon hours',
            'A/B testing suggests shorter ad copy performs better for your audience'
        ]
    }
    
    return render(request, 'dashboard/neuro_ads.html', context)


@login_required
def social_pulse_dashboard(request):
    """Omni-Social Pulse dashboard"""
    if not request.user.omni_social_enabled:
        messages.warning(request, 'Omni-Social Pulse is not enabled for your account.')
        return redirect('dashboard:home')
    
    context = {
        'user': request.user,
        'scheduled_posts': [
            {
                'id': 1,
                'platform': 'LinkedIn',
                'content': 'The future of AI in marketing is here. Our latest insights show...',
                'scheduled_time': timezone.now() + timedelta(hours=2),
                'status': 'Scheduled',
                'engagement_prediction': 'High'
            },
            {
                'id': 2,
                'platform': 'Twitter',
                'content': 'Just published: 5 game-changing marketing automation strategies',
                'scheduled_time': timezone.now() + timedelta(hours=4),
                'status': 'Scheduled',
                'engagement_prediction': 'Medium'
            },
        ],
        'content_suggestions': [
            'Industry trend analysis: AI marketing tools adoption rates',
            'Customer success story: How automation increased ROI by 200%',
            'Behind the scenes: Our team\'s approach to data-driven marketing',
            'Weekly roundup: Top marketing insights from industry leaders'
        ],
        'engagement_stats': {
            'total_followers': 5420,
            'weekly_growth': 2.3,
            'engagement_rate': 4.7,
            'reach': 12500,
            'impressions': 34567
        }
    }
    
    return render(request, 'dashboard/social_pulse.html', context)


@login_required
def email_cortex_dashboard(request):
    """Predictive Email Cortex dashboard"""
    if not request.user.email_cortex_enabled:
        messages.warning(request, 'Predictive Email Cortex is not enabled for your account.')
        return redirect('dashboard:home')
    
    context = {
        'user': request.user,
        'email_campaigns': [
            {
                'id': 1,
                'name': 'Welcome Series',
                'type': 'Automation',
                'status': 'Active',
                'subscribers': 1247,
                'sent': 847,
                'opened': 356,
                'clicked': 89,
                'open_rate': 42.0,
                'click_rate': 10.5,
                'created': '2024-02-15'
            },
            {
                'id': 2,
                'name': 'Product Launch Announcement',
                'type': 'Broadcast',
                'status': 'Sent',
                'subscribers': 5420,
                'sent': 5420,
                'opened': 1463,
                'clicked': 234,
                'open_rate': 27.0,
                'click_rate': 4.3,
                'created': '2024-03-10'
            },
        ],
        'ai_recommendations': [
            'Subject line optimization could increase open rates by 12%',
            'Personalization tokens show 23% higher engagement',
            'Tuesday 10 AM sends perform best for your audience',
            'A/B test: Short vs long-form content in your next campaign'
        ],
        'list_stats': {
            'total_subscribers': 8942,
            'active_subscribers': 7234,
            'growth_rate': 5.2,
            'churn_rate': 1.8,
            'engagement_score': 8.4
        }
    }
    
    return render(request, 'dashboard/email_cortex.html', context)


@login_required
def analytics_overview(request):
    """Analytics and reporting dashboard"""
    context = {
        'user': request.user,
        'analytics_data': {
            'revenue_trend': [
                {'month': 'Jan', 'revenue': 15420, 'spend': 3200},
                {'month': 'Feb', 'revenue': 18750, 'spend': 3800},
                {'month': 'Mar', 'revenue': 22100, 'spend': 4200},
            ],
            'channel_performance': [
                {'channel': 'Google Ads', 'revenue': 32500, 'roi': 520},
                {'channel': 'LinkedIn Ads', 'revenue': 18900, 'roi': 380},
                {'channel': 'Email Marketing', 'revenue': 12400, 'roi': 750},
                {'channel': 'Social Media', 'revenue': 8500, 'roi': 290},
            ],
            'conversion_funnel': [
                {'stage': 'Visitors', 'count': 15420, 'conversion_rate': 100},
                {'stage': 'Leads', 'count': 2840, 'conversion_rate': 18.4},
                {'stage': 'Qualified', 'count': 987, 'conversion_rate': 34.7},
                {'stage': 'Customers', 'count': 234, 'conversion_rate': 23.7},
            ]
        }
    }
    
    return render(request, 'dashboard/analytics.html', context)


@login_required
def dashboard_settings(request):
    """Dashboard settings and preferences"""
    if request.method == 'POST':
        # Handle settings updates
        messages.success(request, 'Settings updated successfully!')
        return redirect('dashboard:settings')
    
    context = {
        'user': request.user,
        'notification_preferences': {
            'email_notifications': True,
            'push_notifications': False,
            'campaign_alerts': True,
            'weekly_reports': True,
        }
    }
    
    return render(request, 'dashboard/settings.html', context)
