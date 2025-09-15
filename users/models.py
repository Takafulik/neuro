from django.contrib.auth.models import AbstractUser
from django.db import models


class BusinessUser(AbstractUser):
    """Custom user model for businesses"""
    
    # Business-specific fields
    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=100, blank=True)
    company_size = models.CharField(max_length=50, blank=True, choices=[
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-1000', '201-1000 employees'),
        ('1000+', '1000+ employees'),
    ])
    industry = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Subscription and feature flags
    subscription_tier = models.CharField(max_length=20, default='free', choices=[
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ])
    
    # Feature access flags
    neuro_ads_enabled = models.BooleanField(default=True)
    omni_social_enabled = models.BooleanField(default=True)
    email_cortex_enabled = models.BooleanField(default=True)
    
    # Profile completion
    profile_completed = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} - {self.business_name or 'No Business Name'}"
    
    def get_full_business_name(self):
        """Return business name or fallback to username"""
        return self.business_name or self.username
    
    def is_profile_complete(self):
        """Check if business profile is complete"""
        required_fields = [self.business_name, self.industry, self.company_size]
        return all(field for field in required_fields)
    
    class Meta:
        verbose_name = "Business User"
        verbose_name_plural = "Business Users"
