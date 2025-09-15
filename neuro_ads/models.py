from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import json


class AdPlatform(models.Model):
    """Supported advertising platforms"""
    PLATFORM_CHOICES = [
        ('google', 'Google Ads'),
        ('meta', 'Meta (Facebook/Instagram)'),
        ('linkedin', 'LinkedIn Campaign Manager'),
    ]
    
    name = models.CharField(max_length=50, choices=PLATFORM_CHOICES, unique=True)
    api_endpoint = models.URLField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.get_name_display()


class PlatformCredentials(models.Model):
    """Store API credentials for each platform per user"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    platform = models.ForeignKey(AdPlatform, on_delete=models.CASCADE)
    
    # Encrypted credential fields
    api_key = models.TextField(blank=True)
    api_secret = models.TextField(blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    account_id = models.CharField(max_length=255, blank=True)
    
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'platform']
    
    def __str__(self):
        return f"{self.user.username} - {self.platform.name}"


class Campaign(models.Model):
    """AI-generated autonomous advertising campaigns"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    
    CAMPAIGN_TYPE_CHOICES = [
        ('awareness', 'Brand Awareness'),
        ('traffic', 'Website Traffic'),
        ('engagement', 'Engagement'),
        ('leads', 'Lead Generation'),
        ('conversions', 'Conversions'),
        ('sales', 'Sales'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Campaign configuration
    campaign_type = models.CharField(max_length=50, choices=CAMPAIGN_TYPE_CHOICES)
    target_audience = models.JSONField(default=dict)  # Stores targeting parameters
    
    # Budget settings
    total_budget = models.DecimalField(max_digits=10, decimal_places=2)
    daily_budget = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    
    # AI-generated content
    ai_generated_copy = models.JSONField(default=dict)  # Stores multiple copy variations
    ai_generated_keywords = models.JSONField(default=list)
    ai_target_suggestions = models.JSONField(default=dict)
    
    # Autonomous settings
    auto_optimization = models.BooleanField(default=True)
    auto_budget_reallocation = models.BooleanField(default=True)
    auto_ab_testing = models.BooleanField(default=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.campaign_type})"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def total_spent(self):
        return sum(ad_set.total_spent for ad_set in self.adset_set.all())


class AdSet(models.Model):
    """Ad sets for each platform within a campaign"""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    platform = models.ForeignKey(AdPlatform, on_delete=models.CASCADE)
    
    name = models.CharField(max_length=255)
    platform_ad_set_id = models.CharField(max_length=255, blank=True)  # External platform ID
    
    # Budget allocation
    allocated_budget = models.DecimalField(max_digits=8, decimal_places=2)
    spent_budget = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Targeting (platform-specific)
    targeting_parameters = models.JSONField(default=dict)
    
    # Performance tracking
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    ctr = models.FloatField(default=0.0)  # Click-through rate
    cpc = models.FloatField(default=0.0)  # Cost per click
    cpa = models.FloatField(default=0.0)  # Cost per acquisition
    roas = models.FloatField(default=0.0)  # Return on ad spend
    
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['campaign', 'platform']
    
    def __str__(self):
        return f"{self.campaign.name} - {self.platform.name}"
    
    @property
    def total_spent(self):
        return float(self.spent_budget)


class AdCreative(models.Model):
    """Individual ad creatives for A/B testing"""
    CREATIVE_TYPE_CHOICES = [
        ('text', 'Text Ad'),
        ('image', 'Image Ad'),
        ('video', 'Video Ad'),
        ('carousel', 'Carousel Ad'),
        ('collection', 'Collection Ad'),
    ]
    
    ad_set = models.ForeignKey(AdSet, on_delete=models.CASCADE)
    
    name = models.CharField(max_length=255)
    creative_type = models.CharField(max_length=20, choices=CREATIVE_TYPE_CHOICES)
    
    # Creative content
    headline = models.CharField(max_length=255)
    description = models.TextField()
    call_to_action = models.CharField(max_length=100)
    destination_url = models.URLField()
    
    # Media assets
    image_url = models.URLField(blank=True)
    video_url = models.URLField(blank=True)
    media_assets = models.JSONField(default=list)  # For carousel/collection ads
    
    # A/B testing metrics
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    ctr = models.FloatField(default=0.0)
    conversion_rate = models.FloatField(default=0.0)
    
    # AI confidence score
    ai_confidence_score = models.FloatField(
        default=0.0, 
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    is_winner = models.BooleanField(default=False)  # A/B test winner
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.creative_type})"


class ABTest(models.Model):
    """A/B testing configurations and results"""
    TEST_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    TEST_TYPE_CHOICES = [
        ('headline', 'Headline Test'),
        ('description', 'Description Test'),
        ('cta', 'Call-to-Action Test'),
        ('creative', 'Creative Test'),
        ('audience', 'Audience Test'),
    ]
    
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES)
    
    # Test configuration
    confidence_level = models.FloatField(default=0.95)
    minimum_sample_size = models.IntegerField(default=1000)
    test_duration_days = models.IntegerField(default=7)
    
    # Test results
    status = models.CharField(max_length=20, choices=TEST_STATUS_CHOICES, default='draft')
    winner_creative = models.ForeignKey(
        AdCreative, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='won_tests'
    )
    statistical_significance = models.FloatField(null=True, blank=True)
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.test_type}"


class BudgetOptimization(models.Model):
    """Budget optimization history and decisions"""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    
    # Previous allocation
    previous_allocation = models.JSONField(default=dict)
    
    # New allocation
    new_allocation = models.JSONField(default=dict)
    
    # Optimization reason
    optimization_reason = models.TextField()
    performance_metrics = models.JSONField(default=dict)
    
    # Expected improvement
    expected_roas_improvement = models.FloatField(default=0.0)
    
    applied_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Budget optimization for {self.campaign.name} at {self.applied_at}"


class CampaignAnalytics(models.Model):
    """Daily analytics data for campaigns"""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE)
    ad_set = models.ForeignKey(AdSet, on_delete=models.CASCADE, null=True, blank=True)
    
    date = models.DateField()
    
    # Performance metrics
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    conversions = models.BigIntegerField(default=0)
    spend = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Calculated metrics
    ctr = models.FloatField(default=0.0)
    cpc = models.FloatField(default=0.0)
    cpa = models.FloatField(default=0.0)
    roas = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['campaign', 'ad_set', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.campaign.name} analytics for {self.date}"


class AutomationRule(models.Model):
    """Rules for autonomous campaign management"""
    RULE_TYPE_CHOICES = [
        ('budget_increase', 'Increase Budget'),
        ('budget_decrease', 'Decrease Budget'),
        ('pause_ad', 'Pause Ad'),
        ('activate_ad', 'Activate Ad'),
        ('bid_adjustment', 'Bid Adjustment'),
    ]
    
    CONDITION_CHOICES = [
        ('ctr_above', 'CTR Above Threshold'),
        ('ctr_below', 'CTR Below Threshold'),
        ('cpa_above', 'CPA Above Threshold'),
        ('cpa_below', 'CPA Below Threshold'),
        ('roas_above', 'ROAS Above Threshold'),
        ('roas_below', 'ROAS Below Threshold'),
        ('spend_threshold', 'Spend Threshold Reached'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    
    # Rule configuration
    rule_type = models.CharField(max_length=50, choices=RULE_TYPE_CHOICES)
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES)
    threshold_value = models.FloatField()
    
    # Action parameters
    action_value = models.FloatField()  # e.g., budget increase percentage
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.rule_type}"
