from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta, date
import json

from .models import (
    Campaign, AdSet, AdCreative, ABTest, AdPlatform, 
    PlatformCredentials, CampaignAnalytics, BudgetOptimization, AutomationRule
)
from .ai.campaign_generator import CampaignGenerator
from .ai.budget_optimizer import BudgetOptimizer
from .ai.ab_testing import ABTestEngine


@login_required
def ads_home(request):
    """Neuro-Ads home dashboard"""
    
    # Get user's campaigns
    campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    # Get recent performance metrics
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    recent_analytics = CampaignAnalytics.objects.filter(
        campaign__user=request.user,
        date__gte=start_date
    )
    
    # Calculate summary metrics
    summary_metrics = recent_analytics.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
        total_conversions=Sum('conversions')
    )
    
    # Calculate derived metrics
    total_spend = float(summary_metrics['total_spend'] or 0)
    total_revenue = float(summary_metrics['total_revenue'] or 0)
    total_clicks = summary_metrics['total_clicks'] or 0
    total_impressions = summary_metrics['total_impressions'] or 0
    total_conversions = summary_metrics['total_conversions'] or 0
    
    roas = (total_revenue / total_spend) if total_spend > 0 else 0
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    cpc = (total_spend / total_clicks) if total_clicks > 0 else 0
    
    # Get active A/B tests
    active_ab_tests = ABTest.objects.filter(
        campaign__user=request.user,
        status='running'
    ).count()
    
    # Get platform connections
    connected_platforms = PlatformCredentials.objects.filter(
        user=request.user,
        is_active=True
    ).count()
    
    context = {
        'campaigns': campaigns,
        'summary_metrics': {
            'total_spend': total_spend,
            'total_revenue': total_revenue,
            'roas': roas,
            'ctr': ctr,
            'cpc': cpc,
            'total_conversions': total_conversions,
        },
        'active_ab_tests': active_ab_tests,
        'connected_platforms': connected_platforms,
        'total_campaigns': campaigns.count(),
    }
    
    return render(request, 'neuro_ads/dashboard.html', context)


@login_required
def campaign_list(request):
    """List all campaigns with filtering and search"""
    
    campaigns = Campaign.objects.filter(user=request.user)
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        campaigns = campaigns.filter(status=status_filter)
    
    # Filter by campaign type
    type_filter = request.GET.get('type')
    if type_filter:
        campaigns = campaigns.filter(campaign_type=type_filter)
    
    # Search by name
    search_query = request.GET.get('search')
    if search_query:
        campaigns = campaigns.filter(name__icontains=search_query)
    
    # Add performance data
    campaigns_with_metrics = []
    for campaign in campaigns:
        # Get recent metrics
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        metrics = CampaignAnalytics.objects.filter(
            campaign=campaign,
            date__gte=start_date
        ).aggregate(
            total_spend=Sum('spend'),
            total_revenue=Sum('revenue'),
            total_conversions=Sum('conversions'),
            total_clicks=Sum('clicks')
        )
        
        spend = float(metrics['total_spend'] or 0)
        revenue = float(metrics['total_revenue'] or 0)
        
        campaign_data = {
            'campaign': campaign,
            'metrics': {
                'spend': spend,
                'revenue': revenue,
                'roas': (revenue / spend) if spend > 0 else 0,
                'conversions': metrics['total_conversions'] or 0,
                'clicks': metrics['total_clicks'] or 0,
            }
        }
        campaigns_with_metrics.append(campaign_data)
    
    context = {
        'campaigns_with_metrics': campaigns_with_metrics,
        'status_choices': Campaign.STATUS_CHOICES,
        'type_choices': Campaign.CAMPAIGN_TYPE_CHOICES,
        'current_filters': {
            'status': status_filter,
            'type': type_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'neuro_ads/campaigns.html', context)


@login_required
def create_campaign(request):
    """Create new autonomous campaign"""
    
    if request.method == 'POST':
        try:
            # Get campaign brief from form
            campaign_brief = {
                'business_description': request.POST.get('business_description'),
                'target_audience': request.POST.get('target_audience'),
                'campaign_goal': request.POST.get('campaign_goal'),
                'total_budget': float(request.POST.get('total_budget')),
                'duration_days': int(request.POST.get('duration_days', 30)),
                'product_service': request.POST.get('product_service'),
                'website_url': request.POST.get('website_url'),
                'preferred_platforms': request.POST.getlist('platforms')
            }
            
            # Generate autonomous campaign
            generator = CampaignGenerator(request.user)
            result = generator.generate_autonomous_campaign(campaign_brief)
            
            if result['success']:
                campaign = result['campaign']
                messages.success(request, f'Autonomous campaign "{campaign.name}" created successfully!')
                return redirect('neuro_ads:campaign_detail', campaign_id=campaign.id)
            else:
                messages.error(request, f'Failed to create campaign: {result.get("error", "Unknown error")}')
                
        except Exception as e:
            messages.error(request, f'Error creating campaign: {str(e)}')
    
    # Get available platforms
    platforms = AdPlatform.objects.filter(is_active=True)
    
    # Check connected platforms
    connected_platforms = PlatformCredentials.objects.filter(
        user=request.user,
        is_active=True
    ).values_list('platform__name', flat=True)
    
    context = {
        'platforms': platforms,
        'connected_platforms': list(connected_platforms),
        'campaign_types': Campaign.CAMPAIGN_TYPE_CHOICES,
    }
    
    return render(request, 'neuro_ads/create_campaign.html', context)


@login_required
def campaign_detail(request, campaign_id):
    """Campaign detail view with analytics and controls"""
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    # Get time range for analytics
    days = int(request.GET.get('days', 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get campaign analytics
    analytics = CampaignAnalytics.objects.filter(
        campaign=campaign,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    # Calculate metrics
    total_metrics = analytics.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
        total_conversions=Sum('conversions')
    )
    
    spend = float(total_metrics['total_spend'] or 0)
    revenue = float(total_metrics['total_revenue'] or 0)
    clicks = total_metrics['total_clicks'] or 0
    impressions = total_metrics['total_impressions'] or 0
    conversions = total_metrics['total_conversions'] or 0
    
    campaign_metrics = {
        'spend': spend,
        'revenue': revenue,
        'roas': (revenue / spend) if spend > 0 else 0,
        'ctr': (clicks / impressions * 100) if impressions > 0 else 0,
        'cpc': (spend / clicks) if clicks > 0 else 0,
        'cpa': (spend / conversions) if conversions > 0 else 0,
        'conversions': conversions,
        'clicks': clicks,
        'impressions': impressions,
    }
    
    # Get ad sets with performance
    ad_sets = []
    for ad_set in campaign.adset_set.all():
        ad_set_analytics = analytics.filter(ad_set=ad_set)
        ad_set_metrics = ad_set_analytics.aggregate(
            spend=Sum('spend'),
            revenue=Sum('revenue'),
            conversions=Sum('conversions'),
            clicks=Sum('clicks')
        )
        
        ad_set_spend = float(ad_set_metrics['spend'] or 0)
        ad_set_revenue = float(ad_set_metrics['revenue'] or 0)
        
        ad_sets.append({
            'ad_set': ad_set,
            'metrics': {
                'spend': ad_set_spend,
                'revenue': ad_set_revenue,
                'roas': (ad_set_revenue / ad_set_spend) if ad_set_spend > 0 else 0,
                'conversions': ad_set_metrics['conversions'] or 0,
                'clicks': ad_set_metrics['clicks'] or 0,
            }
        })
    
    # Get A/B tests
    ab_tests = ABTest.objects.filter(campaign=campaign).order_by('-created_at')
    
    # Get recent optimizations
    recent_optimizations = BudgetOptimization.objects.filter(
        campaign=campaign
    ).order_by('-applied_at')[:5]
    
    # Prepare chart data
    chart_data = {
        'dates': [item.date.strftime('%Y-%m-%d') for item in analytics],
        'spend': [float(item.spend) for item in analytics],
        'revenue': [float(item.revenue) for item in analytics],
        'clicks': [item.clicks for item in analytics],
        'conversions': [item.conversions for item in analytics],
    }
    
    context = {
        'campaign': campaign,
        'campaign_metrics': campaign_metrics,
        'ad_sets': ad_sets,
        'ab_tests': ab_tests,
        'recent_optimizations': recent_optimizations,
        'chart_data': json.dumps(chart_data),
        'days_filter': days,
    }
    
    return render(request, 'neuro_ads/campaign_detail.html', context)


@login_required
@require_http_methods(["POST"])
def optimize_campaign_budget(request, campaign_id):
    """Trigger budget optimization for a campaign"""
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    if not campaign.auto_budget_reallocation:
        return JsonResponse({'success': False, 'error': 'Auto budget reallocation is disabled'})
    
    try:
        optimizer = BudgetOptimizer()
        result = optimizer.optimize_campaign_budgets(campaign)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'Budget optimization completed',
                'changes_made': result.get('changes_made', []),
                'expected_improvement': result.get('expected_improvement', 0),
                'optimization_id': result.get('optimization_id')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('reason', 'Optimization failed')
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def pause_campaign(request, campaign_id):
    """Pause a campaign"""
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    try:
        campaign.status = 'paused'
        campaign.save()
        
        # TODO: Pause campaigns on actual platforms
        
        return JsonResponse({'success': True, 'message': 'Campaign paused successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def resume_campaign(request, campaign_id):
    """Resume a paused campaign"""
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    try:
        campaign.status = 'active'
        campaign.save()
        
        # TODO: Resume campaigns on actual platforms
        
        return JsonResponse({'success': True, 'message': 'Campaign resumed successfully'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def ab_tests_list(request):
    """List all A/B tests"""
    
    ab_tests = ABTest.objects.filter(campaign__user=request.user).order_by('-created_at')
    
    # Add performance data
    ab_tests_with_data = []
    for ab_test in ab_tests:
        # Calculate test performance
        test_performance = {
            'duration_days': 0,
            'sample_size': 0,
            'confidence': ab_test.statistical_significance or 0,
        }
        
        if ab_test.started_at:
            if ab_test.completed_at:
                test_performance['duration_days'] = (ab_test.completed_at - ab_test.started_at).days
            else:
                test_performance['duration_days'] = (timezone.now() - ab_test.started_at).days
        
        ab_tests_with_data.append({
            'ab_test': ab_test,
            'performance': test_performance
        })
    
    context = {
        'ab_tests_with_data': ab_tests_with_data,
        'test_status_choices': ABTest.TEST_STATUS_CHOICES,
        'test_type_choices': ABTest.TEST_TYPE_CHOICES,
    }
    
    return render(request, 'neuro_ads/ab_tests.html', context)


@login_required
def ab_test_detail(request, test_id):
    """A/B test detail view"""
    
    ab_test = get_object_or_404(ABTest, id=test_id, campaign__user=request.user)
    
    # Run analysis if test is running
    if ab_test.status == 'running':
        engine = ABTestEngine()
        analysis_result = engine.run_ab_test_analysis(ab_test)
    else:
        analysis_result = {'success': True, 'status': ab_test.status}
    
    # Get test creatives
    test_creatives = AdCreative.objects.filter(
        ad_set__campaign=ab_test.campaign,
        created_at__gte=ab_test.started_at if ab_test.started_at else timezone.now()
    )
    
    context = {
        'ab_test': ab_test,
        'analysis_result': analysis_result,
        'test_creatives': test_creatives,
    }
    
    return render(request, 'neuro_ads/ab_test_detail.html', context)


@login_required
@require_http_methods(["POST"])
def create_ab_test(request, campaign_id):
    """Create a new A/B test"""
    
    campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
    
    try:
        test_config = {
            'test_type': request.POST.get('test_type'),
            'variants': [
                {
                    'headline': request.POST.get('variant_1_headline'),
                    'description': request.POST.get('variant_1_description'),
                    'call_to_action': request.POST.get('variant_1_cta'),
                },
                {
                    'headline': request.POST.get('variant_2_headline'),
                    'description': request.POST.get('variant_2_description'),
                    'call_to_action': request.POST.get('variant_2_cta'),
                }
            ],
            'duration_days': int(request.POST.get('duration_days', 7)),
            'min_sample_size': int(request.POST.get('min_sample_size', 1000))
        }
        
        engine = ABTestEngine()
        result = engine.create_automated_ab_test(campaign, test_config)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': 'A/B test created and launched',
                'test_id': result['ab_test'].id
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('reason', 'Failed to create test')
            })
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def platform_connections(request):
    """Manage platform connections"""
    
    platforms = AdPlatform.objects.filter(is_active=True)
    
    # Get user's credentials
    user_credentials = {}
    for platform in platforms:
        try:
            cred = PlatformCredentials.objects.get(
                user=request.user,
                platform=platform
            )
            user_credentials[platform.name] = cred
        except PlatformCredentials.DoesNotExist:
            user_credentials[platform.name] = None
    
    context = {
        'platforms': platforms,
        'user_credentials': user_credentials,
    }
    
    return render(request, 'neuro_ads/platform_connections.html', context)


@login_required
def analytics_dashboard(request):
    """Advanced analytics dashboard"""
    
    # Get date range
    days = int(request.GET.get('days', 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    # Get all user campaigns
    campaigns = Campaign.objects.filter(user=request.user)
    
    # Get analytics for all campaigns
    analytics = CampaignAnalytics.objects.filter(
        campaign__user=request.user,
        date__gte=start_date,
        date__lte=end_date
    )
    
    # Overall performance metrics
    overall_metrics = analytics.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_impressions=Sum('impressions'),
        total_clicks=Sum('clicks'),
        total_conversions=Sum('conversions')
    )
    
    # Performance by platform
    platform_performance = []
    for platform in AdPlatform.objects.filter(is_active=True):
        platform_analytics = analytics.filter(ad_set__platform=platform)
        platform_metrics = platform_analytics.aggregate(
            spend=Sum('spend'),
            revenue=Sum('revenue'),
            conversions=Sum('conversions'),
            clicks=Sum('clicks')
        )
        
        spend = float(platform_metrics['spend'] or 0)
        revenue = float(platform_metrics['revenue'] or 0)
        
        if spend > 0:  # Only include platforms with spend
            platform_performance.append({
                'platform': platform,
                'spend': spend,
                'revenue': revenue,
                'roas': (revenue / spend) if spend > 0 else 0,
                'conversions': platform_metrics['conversions'] or 0,
                'clicks': platform_metrics['clicks'] or 0,
            })
    
    # Daily performance trend
    daily_performance = analytics.values('date').annotate(
        daily_spend=Sum('spend'),
        daily_revenue=Sum('revenue'),
        daily_clicks=Sum('clicks'),
        daily_conversions=Sum('conversions')
    ).order_by('date')
    
    # Top performing campaigns
    campaign_performance = []
    for campaign in campaigns:
        campaign_analytics = analytics.filter(campaign=campaign)
        campaign_metrics = campaign_analytics.aggregate(
            spend=Sum('spend'),
            revenue=Sum('revenue'),
            conversions=Sum('conversions')
        )
        
        spend = float(campaign_metrics['spend'] or 0)
        revenue = float(campaign_metrics['revenue'] or 0)
        
        if spend > 0:
            campaign_performance.append({
                'campaign': campaign,
                'spend': spend,
                'revenue': revenue,
                'roas': (revenue / spend) if spend > 0 else 0,
                'conversions': campaign_metrics['conversions'] or 0,
            })
    
    # Sort by ROAS
    campaign_performance.sort(key=lambda x: x['roas'], reverse=True)
    
    context = {
        'overall_metrics': overall_metrics,
        'platform_performance': platform_performance,
        'daily_performance': list(daily_performance),
        'top_campaigns': campaign_performance[:10],
        'days_filter': days,
        'date_range': {
            'start': start_date,
            'end': end_date
        }
    }
    
    return render(request, 'neuro_ads/analytics_dashboard.html', context)


@login_required
def automation_rules(request):
    """Manage automation rules"""
    
    rules = AutomationRule.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        try:
            rule = AutomationRule.objects.create(
                user=request.user,
                name=request.POST.get('name'),
                rule_type=request.POST.get('rule_type'),
                condition=request.POST.get('condition'),
                threshold_value=float(request.POST.get('threshold_value')),
                action_value=float(request.POST.get('action_value')),
                is_active=request.POST.get('is_active') == 'on'
            )
            
            messages.success(request, f'Automation rule "{rule.name}" created successfully!')
            return redirect('neuro_ads:automation_rules')
            
        except Exception as e:
            messages.error(request, f'Error creating rule: {str(e)}')
    
    context = {
        'rules': rules,
        'rule_type_choices': AutomationRule.RULE_TYPE_CHOICES,
        'condition_choices': AutomationRule.CONDITION_CHOICES,
    }
    
    return render(request, 'neuro_ads/automation_rules.html', context)


@login_required
def index(request):
    """Neuro Ads app index view"""
    return redirect('neuro_ads:ads_home')
