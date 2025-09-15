"""
Meta (Facebook/Instagram) Marketing API integration service
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base import BasePlatformService
from ..models import Campaign, AdSet, AdCreative

logger = logging.getLogger(__name__)


class MetaAdsService(BasePlatformService):
    """Meta Marketing API integration for autonomous campaign management"""
    
    def __init__(self, user):
        super().__init__(user, 'meta')
        self.api_version = 'v18.0'
        self.base_url = f'https://graph.facebook.com/{self.api_version}'
        
    def authenticate(self, auth_data: Dict[str, Any]) -> bool:
        """Authenticate with Meta Marketing API"""
        try:
            if self.credentials:
                self.credentials.access_token = auth_data.get('access_token', '')
                self.credentials.account_id = auth_data.get('ad_account_id', '')
                self.credentials.save()
            
            return True
        except Exception as e:
            logger.error(f"Meta Ads authentication failed: {e}")
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Meta Marketing API"""
        return {
            'Authorization': f'Bearer {self.credentials.access_token}',
            'Content-Type': 'application/json',
        }
    
    def create_campaign(self, campaign: Campaign) -> Dict[str, Any]:
        """Create a Meta Ads campaign"""
        campaign_data = {
            'name': campaign.name,
            'objective': self._get_campaign_objective(campaign.campaign_type),
            'status': 'ACTIVE',
            'special_ad_categories': [],
            'buying_type': 'AUCTION',
            'bid_strategy': 'LOWEST_COST_WITHOUT_CAP',
        }
        
        url = f"{self.base_url}/act_{self.credentials.account_id}/campaigns"
        response = self._make_request('POST', url, json=campaign_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': response.get('error', {}).get('message', 'Unknown error')}
    
    def create_ad_set(self, ad_set: AdSet) -> Dict[str, Any]:
        """Create a Meta Ads ad set"""
        targeting = self._build_meta_targeting(ad_set.targeting_parameters)
        
        ad_set_data = {
            'name': ad_set.name,
            'campaign_id': ad_set.campaign.id,  # This should be the external campaign ID
            'status': 'ACTIVE',
            'billing_event': 'IMPRESSIONS',
            'optimization_goal': self._get_optimization_goal(ad_set.campaign.campaign_type),
            'bid_amount': int(self._calculate_bid_amount(ad_set) * 100),  # in cents
            'daily_budget': int(float(ad_set.allocated_budget) * 100),  # in cents
            'targeting': targeting,
            'attribution_spec': [
                {
                    'event_type': 'CLICK_THROUGH',
                    'window_days': 1
                },
                {
                    'event_type': 'VIEW_THROUGH', 
                    'window_days': 1
                }
            ],
            'destination_type': 'WEBSITE',
            'promoted_object': {
                'pixel_id': self._get_pixel_id(),
                'page_id': self._get_page_id(),
            } if self._get_pixel_id() else {}
        }
        
        url = f"{self.base_url}/act_{self.credentials.account_id}/adsets"
        response = self._make_request('POST', url, json=ad_set_data)
        
        if response and 'id' in response:
            ad_set.platform_ad_set_id = response['id']
            ad_set.save()
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': response.get('error', {}).get('message', 'Unknown error')}
    
    def create_ad_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a Meta ad creative"""
        if creative.creative_type == 'image':
            return self._create_image_creative(creative)
        elif creative.creative_type == 'video':
            return self._create_video_creative(creative)
        elif creative.creative_type == 'carousel':
            return self._create_carousel_creative(creative)
        else:
            return self._create_single_image_creative(creative)
    
    def _create_single_image_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a single image ad creative"""
        creative_data = {
            'name': creative.name,
            'object_story_spec': {
                'page_id': self._get_page_id(),
                'link_data': {
                    'call_to_action': {
                        'type': self._map_cta_to_meta(creative.call_to_action),
                        'value': {
                            'link': creative.destination_url,
                            'link_caption': creative.destination_url.split('/')[2] if creative.destination_url else ''
                        }
                    },
                    'image_hash': self._upload_image(creative.image_url) if creative.image_url else '',
                    'link': creative.destination_url,
                    'message': creative.description,
                    'name': creative.headline,
                    'description': creative.description[:90]  # Meta description limit
                }
            },
            'degrees_of_freedom_spec': {
                'creative_features_spec': {
                    'standard_enhancements': {
                        'enroll_status': 'OPT_IN'
                    }
                }
            }
        }
        
        url = f"{self.base_url}/act_{self.credentials.account_id}/adcreatives"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            # Create the actual ad
            return self._create_ad_from_creative(creative, response['id'])
        
        return {'success': False, 'error': 'Failed to create ad creative'}
    
    def _create_carousel_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a carousel ad creative"""
        child_attachments = []
        
        for i, asset in enumerate(creative.media_assets[:10]):  # Max 10 carousel cards
            child_attachments.append({
                'link': creative.destination_url,
                'name': f"{creative.headline} - Card {i+1}",
                'description': asset.get('description', creative.description),
                'image_hash': self._upload_image(asset.get('image_url', '')) if asset.get('image_url') else '',
                'call_to_action': {
                    'type': self._map_cta_to_meta(creative.call_to_action)
                }
            })
        
        creative_data = {
            'name': creative.name,
            'object_story_spec': {
                'page_id': self._get_page_id(),
                'link_data': {
                    'child_attachments': child_attachments,
                    'link': creative.destination_url,
                    'message': creative.description,
                    'call_to_action': {
                        'type': self._map_cta_to_meta(creative.call_to_action)
                    }
                }
            }
        }
        
        url = f"{self.base_url}/act_{self.credentials.account_id}/adcreatives"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return self._create_ad_from_creative(creative, response['id'])
        
        return {'success': False, 'error': 'Failed to create carousel creative'}
    
    def _create_video_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a video ad creative"""
        video_id = self._upload_video(creative.video_url) if creative.video_url else None
        
        if not video_id:
            return {'success': False, 'error': 'Failed to upload video'}
        
        creative_data = {
            'name': creative.name,
            'object_story_spec': {
                'page_id': self._get_page_id(),
                'video_data': {
                    'video_id': video_id,
                    'call_to_action': {
                        'type': self._map_cta_to_meta(creative.call_to_action),
                        'value': {
                            'link': creative.destination_url
                        }
                    },
                    'message': creative.description,
                    'title': creative.headline
                }
            }
        }
        
        url = f"{self.base_url}/act_{self.credentials.account_id}/adcreatives"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return self._create_ad_from_creative(creative, response['id'])
        
        return {'success': False, 'error': 'Failed to create video creative'}
    
    def _create_ad_from_creative(self, creative: AdCreative, creative_id: str) -> Dict[str, Any]:
        """Create an ad from a creative"""
        ad_data = {
            'name': creative.name,
            'adset_id': creative.ad_set.platform_ad_set_id,
            'creative': {'creative_id': creative_id},
            'status': 'ACTIVE'
        }
        
        url = f"{self.base_url}/act_{self.credentials.account_id}/ads"
        response = self._make_request('POST', url, json=ad_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id'], 'creative_id': creative_id}
        
        return {'success': False, 'error': 'Failed to create ad from creative'}
    
    def update_campaign(self, campaign: Campaign, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update Meta campaign settings"""
        update_data = {}
        
        if 'status' in updates:
            update_data['status'] = updates['status'].upper()
        if 'name' in updates:
            update_data['name'] = updates['name']
        
        url = f"{self.base_url}/{campaign.id}"  # External campaign ID
        response = self._make_request('POST', url, json=update_data)
        
        return {'success': bool(response and 'success' in response)}
    
    def pause_campaign(self, campaign: Campaign) -> bool:
        """Pause a Meta campaign"""
        return self.update_campaign(campaign, {'status': 'PAUSED'})['success']
    
    def resume_campaign(self, campaign: Campaign) -> bool:
        """Resume a Meta campaign"""
        return self.update_campaign(campaign, {'status': 'ACTIVE'})['success']
    
    def update_budget(self, ad_set: AdSet, new_budget: float) -> bool:
        """Update Meta ad set budget"""
        update_data = {
            'daily_budget': int(new_budget * 100)  # Convert to cents
        }
        
        url = f"{self.base_url}/{ad_set.platform_ad_set_id}"
        response = self._make_request('POST', url, json=update_data)
        
        return bool(response and 'success' in response)
    
    def get_campaign_metrics(self, campaign: Campaign, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get Meta campaign performance metrics"""
        fields = [
            'impressions',
            'clicks',
            'actions',
            'spend',
            'ctr',
            'cpc',
            'cost_per_action_type',
            'video_views',
            'video_view_time'
        ]
        
        params = {
            'fields': ','.join(fields),
            'time_range': {
                'since': date_range['start_date'],
                'until': date_range['end_date']
            },
            'time_increment': 1,
            'level': 'campaign'
        }
        
        url = f"{self.base_url}/{campaign.id}/insights"  # External campaign ID
        response = self._make_request('GET', url, params=params)
        
        if response and 'data' in response:
            return self._parse_meta_metrics(response['data'])
        
        return {}
    
    def get_targeting_options(self) -> Dict[str, List[Dict]]:
        """Get Meta targeting options"""
        return {
            'interests': self._get_interest_targeting(),
            'behaviors': self._get_behavior_targeting(),
            'demographics': self._get_demographic_targeting(),
            'locations': self._get_location_targeting(),
            'custom_audiences': self._get_custom_audiences(),
        }
    
    def _get_campaign_objective(self, campaign_type: str) -> str:
        """Map campaign type to Meta objective"""
        mapping = {
            'awareness': 'BRAND_AWARENESS',
            'traffic': 'LINK_CLICKS',
            'engagement': 'POST_ENGAGEMENT',
            'leads': 'LEAD_GENERATION',
            'conversions': 'CONVERSIONS',
            'sales': 'CONVERSIONS'
        }
        return mapping.get(campaign_type, 'LINK_CLICKS')
    
    def _get_optimization_goal(self, campaign_type: str) -> str:
        """Map campaign type to Meta optimization goal"""
        mapping = {
            'awareness': 'REACH',
            'traffic': 'LINK_CLICKS',
            'engagement': 'POST_ENGAGEMENT',
            'leads': 'LEAD_GENERATION',
            'conversions': 'OFFSITE_CONVERSIONS',
            'sales': 'OFFSITE_CONVERSIONS'
        }
        return mapping.get(campaign_type, 'LINK_CLICKS')
    
    def _build_meta_targeting(self, targeting_params: Dict) -> Dict:
        """Build Meta targeting from parameters"""
        targeting = {
            'geo_locations': {},
            'age_min': targeting_params.get('age_min', 18),
            'age_max': targeting_params.get('age_max', 65),
        }
        
        if 'locations' in targeting_params:
            targeting['geo_locations']['countries'] = targeting_params['locations']
        
        if 'genders' in targeting_params:
            targeting['genders'] = targeting_params['genders']
        
        if 'interests' in targeting_params:
            targeting['interests'] = [{'id': int_id} for int_id in targeting_params['interests']]
        
        if 'behaviors' in targeting_params:
            targeting['behaviors'] = [{'id': beh_id} for beh_id in targeting_params['behaviors']]
        
        return targeting
    
    def _calculate_bid_amount(self, ad_set: AdSet) -> float:
        """Calculate bid amount for ad set"""
        # Simple calculation - can be enhanced with ML
        return float(ad_set.allocated_budget) * 0.1  # 10% of daily budget
    
    def _map_cta_to_meta(self, cta: str) -> str:
        """Map call-to-action to Meta CTA type"""
        mapping = {
            'Learn More': 'LEARN_MORE',
            'Shop Now': 'SHOP_NOW',
            'Sign Up': 'SIGN_UP',
            'Book Now': 'BOOK_TRAVEL',
            'Download': 'DOWNLOAD',
            'Get Quote': 'GET_QUOTE',
            'Contact Us': 'CONTACT_US',
            'Apply Now': 'APPLY_NOW',
        }
        return mapping.get(cta, 'LEARN_MORE')
    
    def _upload_image(self, image_url: str) -> Optional[str]:
        """Upload image to Meta and return hash"""
        if not image_url:
            return None
        
        # In a real implementation, you would:
        # 1. Download the image from the URL
        # 2. Upload it to Meta's ad images endpoint
        # 3. Return the image hash
        
        # Placeholder implementation
        logger.info(f"Would upload image from {image_url}")
        return "dummy_image_hash"
    
    def _upload_video(self, video_url: str) -> Optional[str]:
        """Upload video to Meta and return video ID"""
        if not video_url:
            return None
        
        # In a real implementation, you would:
        # 1. Download the video from the URL
        # 2. Upload it to Meta's ad videos endpoint
        # 3. Return the video ID
        
        # Placeholder implementation
        logger.info(f"Would upload video from {video_url}")
        return "dummy_video_id"
    
    def _get_page_id(self) -> str:
        """Get Facebook page ID for the user"""
        # This should be stored in user profile or settings
        return "dummy_page_id"
    
    def _get_pixel_id(self) -> Optional[str]:
        """Get Facebook pixel ID for the user"""
        # This should be stored in user profile or settings
        return "dummy_pixel_id"
    
    def _get_interest_targeting(self) -> List[Dict]:
        """Get available interest targeting options"""
        return [
            {'id': '6003107902433', 'name': 'Digital marketing', 'audience_size': 25000000},
            {'id': '6003195797124', 'name': 'Online advertising', 'audience_size': 15000000},
            # Add more interests...
        ]
    
    def _get_behavior_targeting(self) -> List[Dict]:
        """Get available behavior targeting options"""
        return [
            {'id': '6002714895372', 'name': 'Technology early adopters', 'audience_size': 12000000},
            {'id': '6017253486583', 'name': 'Small business owners', 'audience_size': 8000000},
            # Add more behaviors...
        ]
    
    def _get_demographic_targeting(self) -> List[Dict]:
        """Get demographic targeting options"""
        return [
            {'id': 'education_statuses', 'name': 'Education Level', 'options': ['1', '2', '3']},
            {'id': 'life_events', 'name': 'Life Events', 'options': ['1', '2', '3']},
            # Add more demographics...
        ]
    
    def _get_location_targeting(self) -> List[Dict]:
        """Get location targeting options"""
        return [
            {'key': 'US', 'name': 'United States', 'type': 'country'},
            {'key': 'CA', 'name': 'Canada', 'type': 'country'},
            # Add more locations...
        ]
    
    def _get_custom_audiences(self) -> List[Dict]:
        """Get custom audiences for the account"""
        url = f"{self.base_url}/act_{self.credentials.account_id}/customaudiences"
        response = self._make_request('GET', url, params={'fields': 'id,name,approximate_count'})
        
        if response and 'data' in response:
            return response['data']
        
        return []
    
    def _parse_meta_metrics(self, data: List[Dict]) -> Dict[str, Any]:
        """Parse Meta insights response"""
        metrics = {
            'impressions': 0,
            'clicks': 0,
            'conversions': 0,
            'spend': 0.0,
            'ctr': 0.0,
            'cpc': 0.0,
            'cpa': 0.0,
            'video_views': 0,
        }
        
        for day_data in data:
            metrics['impressions'] += int(day_data.get('impressions', 0))
            metrics['clicks'] += int(day_data.get('clicks', 0))
            metrics['spend'] += float(day_data.get('spend', 0))
            metrics['video_views'] += int(day_data.get('video_views', 0))
            
            # Parse actions for conversions
            actions = day_data.get('actions', [])
            for action in actions:
                if action.get('action_type') in ['offsite_conversion', 'purchase', 'lead']:
                    metrics['conversions'] += int(action.get('value', 0))
        
        # Calculate derived metrics
        if metrics['impressions'] > 0:
            metrics['ctr'] = (metrics['clicks'] / metrics['impressions']) * 100
        
        if metrics['clicks'] > 0:
            metrics['cpc'] = metrics['spend'] / metrics['clicks']
        
        if metrics['conversions'] > 0:
            metrics['cpa'] = metrics['spend'] / metrics['conversions']
        
        return metrics