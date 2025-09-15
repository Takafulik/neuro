from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import BusinessUser


@admin.register(BusinessUser)
class BusinessUserAdmin(UserAdmin):
    """Admin interface for BusinessUser model"""
    
    list_display = ('username', 'email', 'business_name', 'industry', 'company_size', 
                   'subscription_tier', 'is_staff', 'date_joined')
    list_filter = ('subscription_tier', 'company_size', 'industry', 'is_staff', 
                  'is_active', 'date_joined', 'profile_completed', 'onboarding_completed')
    search_fields = ('username', 'email', 'business_name', 'industry')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Business Information', {
            'fields': ('business_name', 'business_type', 'industry', 'company_size', 
                      'phone_number', 'website')
        }),
        ('Subscription & Features', {
            'fields': ('subscription_tier', 'neuro_ads_enabled', 'omni_social_enabled', 
                      'email_cortex_enabled')
        }),
        ('Profile Status', {
            'fields': ('profile_completed', 'onboarding_completed')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Business Information', {
            'fields': ('email', 'business_name', 'industry', 'company_size')
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()
