"""
Google Ads API integration service
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base import BasePlatformService
from ..models import Campaign, AdSet, AdCreative

logger = logging.getLogger(__name__)


class GoogleAdsService(BasePlatformService):
    """Google Ads API integration for autonomous campaign management"""
    
    def __init__(self, user):
        super().__init__(user, 'google')
        self.api_version = 'v14'
        self.base_url = f'https://googleads.googleapis.com/{self.api_version}'
        
    def authenticate(self, auth_data: Dict[str, Any]) -> bool:
        """Authenticate with Google Ads API using OAuth2"""
        try:
            # Store credentials
            if self.credentials:
                self.credentials.api_key = auth_data.get('developer_token', '')
                self.credentials.access_token = auth_data.get('access_token', '')
                self.credentials.refresh_token = auth_data.get('refresh_token', '')
                self.credentials.account_id = auth_data.get('customer_id', '')
                self.credentials.save()
            
            return True
        except Exception as e:
            logger.error(f"Google Ads authentication failed: {e}")
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Google Ads API"""
        return {
            'Authorization': f'Bearer {self.credentials.access_token}',
            'developer-token': self.credentials.api_key,
            'Content-Type': 'application/json',
        }
    
    def create_campaign(self, campaign: Campaign) -> Dict[str, Any]:
        """Create a Google Ads campaign"""
        campaign_data = {
            'operations': [{
                'create': {
                    'name': campaign.name,
                    'status': 'ENABLED',
                    'advertising_channel_type': self._get_channel_type(campaign.campaign_type),
                    'campaign_budget': {
                        'amount_micros': int(float(campaign.daily_budget or campaign.total_budget) * 1000000),
                        'delivery_method': 'STANDARD'
                    },
                    'bidding_strategy': {
                        'target_cpa': {
                            'target_cpa_micros': int(self._calculate_target_cpa(campaign) * 1000000)
                        }
                    },
                    'geo_target_type_setting': {
                        'positive_geo_target_type': 'PRESENCE_OR_INTEREST',
                        'negative_geo_target_type': 'PRESENCE'
                    }
                }
            }]
        }
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/campaigns:mutate"
        response = self._make_request('POST', url, json=campaign_data)
        
        if response and 'results' in response:
            # Store the external campaign ID
            external_id = response['results'][0]['resourceName'].split('/')[-1]
            # Update campaign with external ID if needed
            return {'success': True, 'external_id': external_id, 'response': response}
        
        return {'success': False, 'error': 'Failed to create campaign'}
    
    def create_ad_set(self, ad_set: AdSet) -> Dict[str, Any]:
        """Create a Google Ads ad group (equivalent to ad set)"""
        ad_group_data = {
            'operations': [{
                'create': {
                    'name': ad_set.name,
                    'campaign': f"customers/{self.credentials.account_id}/campaigns/{ad_set.campaign.id}",
                    'status': 'ENABLED',
                    'type': 'SEARCH_STANDARD',
                    'cpc_bid_micros': int(self._calculate_default_bid(ad_set) * 1000000),
                    'targeting_setting': {
                        'target_restrictions': self._build_targeting(ad_set.targeting_parameters)
                    }
                }
            }]
        }
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/adGroups:mutate"
        response = self._make_request('POST', url, json=ad_group_data)
        
        if response and 'results' in response:
            external_id = response['results'][0]['resourceName'].split('/')[-1]
            ad_set.platform_ad_set_id = external_id
            ad_set.save()
            return {'success': True, 'external_id': external_id}
        
        return {'success': False, 'error': 'Failed to create ad group'}
    
    def create_ad_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a Google Ads responsive search ad"""
        if creative.creative_type == 'text':
            return self._create_responsive_search_ad(creative)
        elif creative.creative_type == 'image':
            return self._create_responsive_display_ad(creative)
        else:
            return {'success': False, 'error': f'Unsupported creative type: {creative.creative_type}'}
    
    def _create_responsive_search_ad(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a responsive search ad"""
        headlines = self._generate_headline_variations(creative.headline)
        descriptions = self._generate_description_variations(creative.description)
        
        ad_data = {
            'operations': [{
                'create': {
                    'ad_group': f"customers/{self.credentials.account_id}/adGroups/{creative.ad_set.platform_ad_set_id}",
                    'status': 'ENABLED',
                    'ad': {
                        'responsive_search_ad': {
                            'headlines': headlines,
                            'descriptions': descriptions,
                            'path1': '',
                            'path2': ''
                        },
                        'final_urls': [creative.destination_url]
                    }
                }
            }]
        }
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/adGroupAds:mutate"
        response = self._make_request('POST', url, json=ad_data)
        
        if response and 'results' in response:
            return {'success': True, 'external_id': response['results'][0]['resourceName']}
        
        return {'success': False, 'error': 'Failed to create responsive search ad'}
    
    def _create_responsive_display_ad(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a responsive display ad"""
        ad_data = {
            'operations': [{
                'create': {
                    'ad_group': f"customers/{self.credentials.account_id}/adGroups/{creative.ad_set.platform_ad_set_id}",
                    'status': 'ENABLED',
                    'ad': {
                        'responsive_display_ad': {
                            'short_headline': {'text': creative.headline[:30]},
                            'long_headline': {'text': creative.headline},
                            'descriptions': [{'text': creative.description}],
                            'business_name': self.user.company.name if hasattr(self.user, 'company') else 'Business',
                            'call_to_action_text': creative.call_to_action.upper(),
                            'marketing_images': [
                                {
                                    'asset': {
                                        'image_asset': {
                                            'data': '',  # Base64 encoded image data
                                            'file_size': 0,
                                            'mime_type': 'IMAGE_JPEG',
                                            'full_size': {
                                                'width_pixels': 1200,
                                                'height_pixels': 628,
                                                'url': creative.image_url
                                            }
                                        }
                                    }
                                }
                            ] if creative.image_url else []
                        },
                        'final_urls': [creative.destination_url]
                    }
                }
            }]
        }
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/adGroupAds:mutate"
        response = self._make_request('POST', url, json=ad_data)
        
        if response and 'results' in response:
            return {'success': True, 'external_id': response['results'][0]['resourceName']}
        
        return {'success': False, 'error': 'Failed to create responsive display ad'}
    
    def update_campaign(self, campaign: Campaign, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update campaign settings"""
        update_data = {
            'operations': [{
                'update': {
                    'resource_name': f"customers/{self.credentials.account_id}/campaigns/{campaign.id}",
                    'status': updates.get('status', 'ENABLED').upper(),
                    'name': updates.get('name', campaign.name)
                },
                'update_mask': {'paths': list(updates.keys())}
            }]
        }
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/campaigns:mutate"
        response = self._make_request('POST', url, json=update_data)
        
        return {'success': bool(response and 'results' in response)}
    
    def pause_campaign(self, campaign: Campaign) -> bool:
        """Pause a Google Ads campaign"""
        return self.update_campaign(campaign, {'status': 'PAUSED'})['success']
    
    def resume_campaign(self, campaign: Campaign) -> bool:
        """Resume a Google Ads campaign"""
        return self.update_campaign(campaign, {'status': 'ENABLED'})['success']
    
    def update_budget(self, ad_set: AdSet, new_budget: float) -> bool:
        """Update ad group budget (through campaign budget)"""
        # Google Ads manages budget at campaign level
        update_data = {
            'operations': [{
                'update': {
                    'resource_name': f"customers/{self.credentials.account_id}/campaigns/{ad_set.campaign.id}",
                    'campaign_budget': {
                        'amount_micros': int(new_budget * 1000000)
                    }
                },
                'update_mask': {'paths': ['campaign_budget.amount_micros']}
            }]
        }
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/campaigns:mutate"
        response = self._make_request('POST', url, json=update_data)
        
        return bool(response and 'results' in response)
    
    def get_campaign_metrics(self, campaign: Campaign, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get Google Ads campaign performance metrics"""
        query = f"""
        SELECT 
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_micros,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_per_conversion,
            segments.date
        FROM campaign
        WHERE 
            campaign.id = {campaign.id}
            AND segments.date BETWEEN '{date_range['start_date']}' AND '{date_range['end_date']}'
        """
        
        url = f"{self.base_url}/customers/{self.credentials.account_id}/googleAds:searchStream"
        response = self._make_request('POST', url, json={'query': query})
        
        if response and 'results' in response:
            return self._parse_metrics_response(response)
        
        return {}
    
    def get_targeting_options(self) -> Dict[str, List[Dict]]:
        """Get Google Ads targeting options"""
        return {
            'locations': self._get_location_targeting(),
            'demographics': self._get_demographic_targeting(),
            'interests': self._get_interest_targeting(),
            'keywords': self._get_keyword_suggestions(),
        }
    
    def _get_channel_type(self, campaign_type: str) -> str:
        """Map campaign type to Google Ads channel type"""
        mapping = {
            'awareness': 'DISPLAY',
            'traffic': 'SEARCH',
            'engagement': 'DISPLAY',
            'leads': 'SEARCH',
            'conversions': 'SEARCH',
            'sales': 'SHOPPING'
        }
        return mapping.get(campaign_type, 'SEARCH')
    
    def _calculate_target_cpa(self, campaign: Campaign) -> float:
        """Calculate target CPA based on campaign budget and goals"""
        # Simple calculation - can be enhanced with ML
        daily_budget = float(campaign.daily_budget or campaign.total_budget / 30)
        return daily_budget * 0.1  # 10% of daily budget as target CPA
    
    def _calculate_default_bid(self, ad_set: AdSet) -> float:
        """Calculate default bid for ad group"""
        return float(ad_set.allocated_budget) * 0.05  # 5% of allocated budget
    
    def _build_targeting(self, targeting_params: Dict) -> List[Dict]:
        """Build targeting restrictions from parameters"""
        restrictions = []
        
        if 'locations' in targeting_params:
            restrictions.extend([
                {'location': {'geo_target_constant': loc}} 
                for loc in targeting_params['locations']
            ])
        
        if 'age_ranges' in targeting_params:
            restrictions.extend([
                {'age_range': {'type': age}} 
                for age in targeting_params['age_ranges']
            ])
        
        return restrictions
    
    def _generate_headline_variations(self, base_headline: str) -> List[Dict]:
        """Generate headline variations for responsive search ads"""
        variations = [
            {'text': base_headline},
            {'text': f"Best {base_headline}"},
            {'text': f"{base_headline} Today"},
        ]
        return variations[:15]  # Max 15 headlines
    
    def _generate_description_variations(self, base_description: str) -> List[Dict]:
        """Generate description variations"""
        variations = [
            {'text': base_description},
            {'text': f"{base_description} Learn more today."},
        ]
        return variations[:4]  # Max 4 descriptions
    
    def _get_location_targeting(self) -> List[Dict]:
        """Get available location targeting options"""
        # This would typically call the Google Ads API
        return [
            {'id': '2840', 'name': 'United States', 'type': 'Country'},
            {'id': '2124', 'name': 'Canada', 'type': 'Country'},
            # Add more locations...
        ]
    
    def _get_demographic_targeting(self) -> List[Dict]:
        """Get demographic targeting options"""
        return [
            {'id': 'AGE_RANGE_18_24', 'name': '18-24 years', 'type': 'Age'},
            {'id': 'AGE_RANGE_25_34', 'name': '25-34 years', 'type': 'Age'},
            {'id': 'AGE_RANGE_35_44', 'name': '35-44 years', 'type': 'Age'},
            # Add more demographics...
        ]
    
    def _get_interest_targeting(self) -> List[Dict]:
        """Get interest targeting options"""
        return [
            {'id': '10001', 'name': 'Technology', 'type': 'Interest'},
            {'id': '10002', 'name': 'Sports', 'type': 'Interest'},
            # Add more interests...
        ]
    
    def _get_keyword_suggestions(self) -> List[Dict]:
        """Get keyword suggestions"""
        return [
            {'keyword': 'digital marketing', 'competition': 'HIGH', 'suggested_bid': 2.50},
            {'keyword': 'online advertising', 'competition': 'MEDIUM', 'suggested_bid': 1.80},
            # Add more keywords...
        ]
    
    def _parse_metrics_response(self, response: Dict) -> Dict[str, Any]:
        """Parse Google Ads metrics response"""
        metrics = {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'spend': 0.0,
            'ctr': 0.0,
            'cpc': 0.0,
            'cpa': 0.0,
        }
        
        for result in response.get('results', []):
            if 'metrics' in result:
                m = result['metrics']
                metrics['impressions'] += m.get('impressions', 0)
                metrics['clicks'] += m.get('clicks', 0)
                metrics['conversions'] += m.get('conversions', 0)
                metrics['spend'] += m.get('cost_micros', 0) / 1000000
        
        # Calculate derived metrics
        if metrics['impressions'] > 0:
            metrics['ctr'] = (metrics['clicks'] / metrics['impressions']) * 100
        
        if metrics['clicks'] > 0:
            metrics['cpc'] = metrics['spend'] / metrics['clicks']
        
        if metrics['conversions'] > 0:
            metrics['cpa'] = metrics['spend'] / metrics['conversions']
        
        return metrics