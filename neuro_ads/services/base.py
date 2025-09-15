"""
Base platform service class for common functionality
"""

import requests
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.utils import timezone
from ..models import Campaign, AdSet, AdCreative, PlatformCredentials

logger = logging.getLogger(__name__)


class BasePlatformService(ABC):
    """Base class for all advertising platform integrations"""
    
    def __init__(self, user, platform_name: str):
        self.user = user
        self.platform_name = platform_name
        self.credentials = self._get_credentials()
        
    def _get_credentials(self) -> Optional[PlatformCredentials]:
        """Get user credentials for this platform"""
        try:
            return PlatformCredentials.objects.get(
                user=self.user,
                platform__name=self.platform_name,
                is_active=True
            )
        except PlatformCredentials.DoesNotExist:
            logger.warning(f"No credentials found for {self.user.username} on {self.platform_name}")
            return None
    
    def is_authenticated(self) -> bool:
        """Check if user has valid credentials"""
        if not self.credentials:
            return False
        
        # Check if token is expired
        if self.credentials.expires_at and self.credentials.expires_at < timezone.now():
            return False
            
        return True
    
    @abstractmethod
    def authenticate(self, auth_data: Dict[str, Any]) -> bool:
        """Authenticate with the platform"""
        pass
    
    @abstractmethod
    def create_campaign(self, campaign: Campaign) -> Dict[str, Any]:
        """Create a campaign on the platform"""
        pass
    
    @abstractmethod
    def update_campaign(self, campaign: Campaign, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a campaign on the platform"""
        pass
    
    @abstractmethod
    def pause_campaign(self, campaign: Campaign) -> bool:
        """Pause a campaign on the platform"""
        pass
    
    @abstractmethod
    def resume_campaign(self, campaign: Campaign) -> bool:
        """Resume a campaign on the platform"""
        pass
    
    @abstractmethod
    def get_campaign_metrics(self, campaign: Campaign, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get campaign performance metrics"""
        pass
    
    @abstractmethod
    def create_ad_set(self, ad_set: AdSet) -> Dict[str, Any]:
        """Create an ad set on the platform"""
        pass
    
    @abstractmethod
    def update_budget(self, ad_set: AdSet, new_budget: float) -> bool:
        """Update ad set budget"""
        pass
    
    @abstractmethod
    def create_ad_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create an ad creative on the platform"""
        pass
    
    @abstractmethod
    def get_targeting_options(self) -> Dict[str, List[Dict]]:
        """Get available targeting options for the platform"""
        pass
    
    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict]:
        """Make authenticated API request"""
        if not self.is_authenticated():
            logger.error(f"Not authenticated for {self.platform_name}")
            return None
        
        headers = kwargs.get('headers', {})
        headers.update(self._get_auth_headers())
        kwargs['headers'] = headers
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {self.platform_name}: {e}")
            return None
    
    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        pass
    
    def validate_campaign_data(self, campaign_data: Dict[str, Any]) -> List[str]:
        """Validate campaign data for this platform"""
        errors = []
        
        # Common validations
        if not campaign_data.get('name'):
            errors.append("Campaign name is required")
        
        if not campaign_data.get('budget') or float(campaign_data['budget']) <= 0:
            errors.append("Valid budget is required")
        
        return errors