"""
LinkedIn Campaign Manager API integration service
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base import BasePlatformService
from ..models import Campaign, AdSet, AdCreative

logger = logging.getLogger(__name__)


class LinkedInAdsService(BasePlatformService):
    """LinkedIn Campaign Manager API integration for autonomous campaign management"""
    
    def __init__(self, user):
        super().__init__(user, 'linkedin')
        self.api_version = 'v2'
        self.base_url = f'https://api.linkedin.com/{self.api_version}'
        
    def authenticate(self, auth_data: Dict[str, Any]) -> bool:
        """Authenticate with LinkedIn Campaign Manager API"""
        try:
            if self.credentials:
                self.credentials.access_token = auth_data.get('access_token', '')
                self.credentials.account_id = auth_data.get('account_id', '')
                self.credentials.save()
            
            return True
        except Exception as e:
            logger.error(f"LinkedIn Ads authentication failed: {e}")
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for LinkedIn Campaign Manager API"""
        return {
            'Authorization': f'Bearer {self.credentials.access_token}',
            'Content-Type': 'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202310'
        }
    
    def create_campaign(self, campaign: Campaign) -> Dict[str, Any]:
        """Create a LinkedIn campaign"""
        campaign_data = {
            'name': campaign.name,
            'type': 'TEXT_AD',
            'status': 'ACTIVE',
            'account': f'urn:li:sponsoredAccount:{self.credentials.account_id}',
            'campaignGroup': self._get_or_create_campaign_group(),
            'targetingCriteria': {
                'include': {
                    'and': []
                },
                'exclude': {
                    'or': []
                }
            },
            'costType': 'CPC',
            'creativesCount': 0,
            'dailyBudget': {
                'amount': str(int(float(campaign.daily_budget or campaign.total_budget / 30) * 100)),
                'currencyCode': 'USD'
            },
            'unitCost': {
                'amount': str(int(self._calculate_default_bid(campaign) * 100)),
                'currencyCode': 'USD'
            },
            'format': self._get_campaign_format(campaign.campaign_type),
            'objective': self._get_campaign_objective(campaign.campaign_type)
        }
        
        url = f"{self.base_url}/adCampaignsV2"
        response = self._make_request('POST', url, json=campaign_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': response.get('message', 'Unknown error')}
    
    def create_ad_set(self, ad_set: AdSet) -> Dict[str, Any]:
        """Create a LinkedIn ad set (creative group)"""
        # LinkedIn doesn't have ad sets like Facebook, but we'll use campaign groups
        targeting = self._build_linkedin_targeting(ad_set.targeting_parameters)
        
        # Update the campaign with targeting instead of creating separate ad set
        campaign_update = {
            'targetingCriteria': targeting,
            'dailyBudget': {
                'amount': str(int(float(ad_set.allocated_budget) * 100)),
                'currencyCode': 'USD'
            }
        }
        
        url = f"{self.base_url}/adCampaignsV2/{ad_set.campaign.id}"
        response = self._make_request('POST', url, json=campaign_update)
        
        if response:
            # Store campaign ID as ad set platform ID for consistency
            ad_set.platform_ad_set_id = str(ad_set.campaign.id)
            ad_set.save()
            return {'success': True, 'external_id': str(ad_set.campaign.id)}
        
        return {'success': False, 'error': 'Failed to update campaign targeting'}
    
    def create_ad_creative(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a LinkedIn ad creative"""
        if creative.creative_type == 'text':
            return self._create_sponsored_content(creative)
        elif creative.creative_type == 'image':
            return self._create_single_image_ad(creative)
        elif creative.creative_type == 'video':
            return self._create_video_ad(creative)
        elif creative.creative_type == 'carousel':
            return self._create_carousel_ad(creative)
        else:
            return self._create_text_ad(creative)
    
    def _create_sponsored_content(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a LinkedIn sponsored content creative"""
        # First create the content (post)
        content_data = {
            'author': f'urn:li:organization:{self._get_organization_id()}',
            'commentary': creative.description,
            'visibility': {
                'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC'
            },
            'specificContent': {
                'com.linkedin.ugc.ShareContent': {
                    'shareCommentary': {
                        'text': creative.description
                    },
                    'shareMediaCategory': 'ARTICLE',
                    'media': [
                        {
                            'status': 'READY',
                            'description': {
                                'text': creative.description
                            },
                            'media': self._upload_media(creative.image_url) if creative.image_url else None,
                            'title': {
                                'text': creative.headline
                            }
                        }
                    ]
                }
            }
        }
        
        url = f"{self.base_url}/ugcPosts"
        content_response = self._make_request('POST', url, json=content_data)
        
        if not content_response or 'id' not in content_response:
            return {'success': False, 'error': 'Failed to create sponsored content'}
        
        # Create the creative
        creative_data = {
            'campaign': f'urn:li:sponsoredCampaign:{creative.ad_set.campaign.id}',
            'status': 'ACTIVE',
            'type': 'SPONSORED_CONTENT',
            'content': {
                'sponsoredContent': {
                    'share': content_response['id']
                }
            }
        }
        
        url = f"{self.base_url}/adCreativesV2"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id'], 'content_id': content_response['id']}
        
        return {'success': False, 'error': 'Failed to create sponsored content creative'}
    
    def _create_text_ad(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a LinkedIn text ad creative"""
        creative_data = {
            'campaign': f'urn:li:sponsoredCampaign:{creative.ad_set.campaign.id}',
            'status': 'ACTIVE',
            'type': 'TEXT_AD',
            'content': {
                'textAd': {
                    'headline': creative.headline[:25],  # LinkedIn headline limit
                    'description': creative.description[:75],  # LinkedIn description limit
                    'destinationUrl': creative.destination_url
                }
            }
        }
        
        url = f"{self.base_url}/adCreativesV2"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': 'Failed to create text ad'}
    
    def _create_single_image_ad(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a LinkedIn single image ad"""
        media_urn = self._upload_media(creative.image_url) if creative.image_url else None
        
        if not media_urn:
            return {'success': False, 'error': 'Failed to upload image'}
        
        creative_data = {
            'campaign': f'urn:li:sponsoredCampaign:{creative.ad_set.campaign.id}',
            'status': 'ACTIVE',
            'type': 'SPONSORED_CONTENT',
            'content': {
                'sponsoredContent': {
                    'directSponsoredContent': {
                        'media': media_urn,
                        'headline': creative.headline,
                        'description': creative.description,
                        'callToAction': {
                            'actionType': self._map_cta_to_linkedin(creative.call_to_action),
                            'label': creative.call_to_action
                        },
                        'destinationUrl': creative.destination_url
                    }
                }
            }
        }
        
        url = f"{self.base_url}/adCreativesV2"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': 'Failed to create single image ad'}
    
    def _create_video_ad(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a LinkedIn video ad"""
        video_urn = self._upload_video(creative.video_url) if creative.video_url else None
        
        if not video_urn:
            return {'success': False, 'error': 'Failed to upload video'}
        
        creative_data = {
            'campaign': f'urn:li:sponsoredCampaign:{creative.ad_set.campaign.id}',
            'status': 'ACTIVE',
            'type': 'SPONSORED_CONTENT',
            'content': {
                'sponsoredContent': {
                    'directSponsoredContent': {
                        'video': video_urn,
                        'headline': creative.headline,
                        'description': creative.description,
                        'callToAction': {
                            'actionType': self._map_cta_to_linkedin(creative.call_to_action),
                            'label': creative.call_to_action
                        },
                        'destinationUrl': creative.destination_url
                    }
                }
            }
        }
        
        url = f"{self.base_url}/adCreativesV2"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': 'Failed to create video ad'}
    
    def _create_carousel_ad(self, creative: AdCreative) -> Dict[str, Any]:
        """Create a LinkedIn carousel ad"""
        carousel_cards = []
        
        for i, asset in enumerate(creative.media_assets[:10]):  # Max 10 carousel cards
            media_urn = self._upload_media(asset.get('image_url', '')) if asset.get('image_url') else None
            if media_urn:
                carousel_cards.append({
                    'media': media_urn,
                    'headline': asset.get('headline', f"{creative.headline} - Card {i+1}"),
                    'description': asset.get('description', creative.description),
                    'destinationUrl': asset.get('destination_url', creative.destination_url)
                })
        
        creative_data = {
            'campaign': f'urn:li:sponsoredCampaign:{creative.ad_set.campaign.id}',
            'status': 'ACTIVE',
            'type': 'SPONSORED_CONTENT',
            'content': {
                'sponsoredContent': {
                    'directSponsoredContent': {
                        'carousel': {
                            'cards': carousel_cards
                        },
                        'headline': creative.headline,
                        'description': creative.description,
                        'callToAction': {
                            'actionType': self._map_cta_to_linkedin(creative.call_to_action),
                            'label': creative.call_to_action
                        }
                    }
                }
            }
        }
        
        url = f"{self.base_url}/adCreativesV2"
        response = self._make_request('POST', url, json=creative_data)
        
        if response and 'id' in response:
            return {'success': True, 'external_id': response['id']}
        
        return {'success': False, 'error': 'Failed to create carousel ad'}
    
    def update_campaign(self, campaign: Campaign, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update LinkedIn campaign settings"""
        update_data = {}
        
        if 'status' in updates:
            update_data['status'] = updates['status'].upper()
        if 'name' in updates:
            update_data['name'] = updates['name']
        if 'budget' in updates:
            update_data['dailyBudget'] = {
                'amount': str(int(float(updates['budget']) * 100)),
                'currencyCode': 'USD'
            }
        
        url = f"{self.base_url}/adCampaignsV2/{campaign.id}"
        response = self._make_request('POST', url, json=update_data)
        
        return {'success': bool(response)}
    
    def pause_campaign(self, campaign: Campaign) -> bool:
        """Pause a LinkedIn campaign"""
        return self.update_campaign(campaign, {'status': 'PAUSED'})['success']
    
    def resume_campaign(self, campaign: Campaign) -> bool:
        """Resume a LinkedIn campaign"""
        return self.update_campaign(campaign, {'status': 'ACTIVE'})['success']
    
    def update_budget(self, ad_set: AdSet, new_budget: float) -> bool:
        """Update LinkedIn campaign budget"""
        return self.update_campaign(ad_set.campaign, {'budget': new_budget})
    
    def get_campaign_metrics(self, campaign: Campaign, date_range: Dict[str, str]) -> Dict[str, Any]:
        """Get LinkedIn campaign performance metrics"""
        params = {
            'q': 'analytics',
            'pivot': 'CAMPAIGN',
            'dateRange.start.day': int(date_range['start_date'].split('-')[2]),
            'dateRange.start.month': int(date_range['start_date'].split('-')[1]),
            'dateRange.start.year': int(date_range['start_date'].split('-')[0]),
            'dateRange.end.day': int(date_range['end_date'].split('-')[2]),
            'dateRange.end.month': int(date_range['end_date'].split('-')[1]),
            'dateRange.end.year': int(date_range['end_date'].split('-')[0]),
            'campaigns[0]': f'urn:li:sponsoredCampaign:{campaign.id}',
            'fields': 'impressions,clicks,costInUsd,externalWebsiteConversions,videoViews,videoCompletions'
        }
        
        url = f"{self.base_url}/adAnalyticsV2"
        response = self._make_request('GET', url, params=params)
        
        if response and 'elements' in response:
            return self._parse_linkedin_metrics(response['elements'])
        
        return {}
    
    def get_targeting_options(self) -> Dict[str, List[Dict]]:
        """Get LinkedIn targeting options"""
        return {
            'job_titles': self._get_job_title_targeting(),
            'skills': self._get_skills_targeting(),
            'companies': self._get_company_targeting(),
            'industries': self._get_industry_targeting(),
            'seniority': self._get_seniority_targeting(),
            'locations': self._get_location_targeting(),
        }
    
    def _get_campaign_objective(self, campaign_type: str) -> str:
        """Map campaign type to LinkedIn objective"""
        mapping = {
            'awareness': 'BRAND_AWARENESS',
            'traffic': 'WEBSITE_VISITS',
            'engagement': 'ENGAGEMENT',
            'leads': 'LEAD_GENERATION',
            'conversions': 'WEBSITE_CONVERSIONS',
            'sales': 'WEBSITE_CONVERSIONS'
        }
        return mapping.get(campaign_type, 'WEBSITE_VISITS')
    
    def _get_campaign_format(self, campaign_type: str) -> str:
        """Map campaign type to LinkedIn format"""
        mapping = {
            'awareness': 'SPONSORED_CONTENT',
            'traffic': 'SPONSORED_CONTENT',
            'engagement': 'SPONSORED_CONTENT',
            'leads': 'SPONSORED_CONTENT',
            'conversions': 'SPONSORED_CONTENT',
            'sales': 'SPONSORED_CONTENT'
        }
        return mapping.get(campaign_type, 'SPONSORED_CONTENT')
    
    def _calculate_default_bid(self, campaign: Campaign) -> float:
        """Calculate default bid for LinkedIn campaign"""
        daily_budget = float(campaign.daily_budget or campaign.total_budget / 30)
        return daily_budget * 0.15  # 15% of daily budget as default bid
    
    def _build_linkedin_targeting(self, targeting_params: Dict) -> Dict:
        """Build LinkedIn targeting criteria"""
        include_criteria = []
        
        if 'job_titles' in targeting_params:
            include_criteria.append({
                'targetingType': 'JOB_TITLE',
                'targetingValue': targeting_params['job_titles']
            })
        
        if 'skills' in targeting_params:
            include_criteria.append({
                'targetingType': 'SKILL',
                'targetingValue': targeting_params['skills']
            })
        
        if 'companies' in targeting_params:
            include_criteria.append({
                'targetingType': 'COMPANY',
                'targetingValue': targeting_params['companies']
            })
        
        if 'industries' in targeting_params:
            include_criteria.append({
                'targetingType': 'INDUSTRY',
                'targetingValue': targeting_params['industries']
            })
        
        if 'locations' in targeting_params:
            include_criteria.append({
                'targetingType': 'LOCATION',
                'targetingValue': targeting_params['locations']
            })
        
        return {
            'include': {
                'and': include_criteria
            },
            'exclude': {
                'or': []
            }
        }
    
    def _map_cta_to_linkedin(self, cta: str) -> str:
        """Map call-to-action to LinkedIn action type"""
        mapping = {
            'Learn More': 'LEARN_MORE',
            'Sign Up': 'SIGN_UP',
            'Download': 'DOWNLOAD',
            'Apply Now': 'APPLY',
            'Contact Us': 'CONTACT_US',
            'Get Quote': 'GET_QUOTE',
            'Join Now': 'JOIN',
            'Register': 'REGISTER',
        }
        return mapping.get(cta, 'LEARN_MORE')
    
    def _get_or_create_campaign_group(self) -> str:
        """Get or create a campaign group"""
        # For simplicity, return a default campaign group URN
        # In a real implementation, you'd check if one exists or create it
        return f'urn:li:sponsoredCampaignGroup:default_{self.credentials.account_id}'
    
    def _get_organization_id(self) -> str:
        """Get LinkedIn organization ID for the user"""
        # This should be stored in user profile or fetched from LinkedIn
        return "dummy_organization_id"
    
    def _upload_media(self, media_url: str) -> Optional[str]:
        """Upload media to LinkedIn and return URN"""
        if not media_url:
            return None
        
        # In a real implementation, you would:
        # 1. Download the media from the URL
        # 2. Upload it to LinkedIn's media upload endpoint
        # 3. Return the media URN
        
        # Placeholder implementation
        logger.info(f"Would upload media from {media_url}")
        return "urn:li:digitalmediaAsset:dummy_media_id"
    
    def _upload_video(self, video_url: str) -> Optional[str]:
        """Upload video to LinkedIn and return URN"""
        if not video_url:
            return None
        
        # In a real implementation, you would:
        # 1. Download the video from the URL
        # 2. Upload it to LinkedIn's video upload endpoint
        # 3. Return the video URN
        
        # Placeholder implementation
        logger.info(f"Would upload video from {video_url}")
        return "urn:li:digitalmediaAsset:dummy_video_id"
    
    def _get_job_title_targeting(self) -> List[Dict]:
        """Get job title targeting options"""
        return [
            {'id': '25', 'name': 'Marketing Manager'},
            {'id': '26', 'name': 'Software Engineer'},
            {'id': '27', 'name': 'CEO'},
            # Add more job titles...
        ]
    
    def _get_skills_targeting(self) -> List[Dict]:
        """Get skills targeting options"""
        return [
            {'id': '2', 'name': 'Digital Marketing'},
            {'id': '3', 'name': 'Software Development'},
            {'id': '4', 'name': 'Project Management'},
            # Add more skills...
        ]
    
    def _get_company_targeting(self) -> List[Dict]:
        """Get company targeting options"""
        return [
            {'id': '1337', 'name': 'LinkedIn'},
            {'id': '1441', 'name': 'Microsoft'},
            {'id': '1586', 'name': 'Google'},
            # Add more companies...
        ]
    
    def _get_industry_targeting(self) -> List[Dict]:
        """Get industry targeting options"""
        return [
            {'id': '6', 'name': 'Information Technology and Services'},
            {'id': '7', 'name': 'Marketing and Advertising'},
            {'id': '8', 'name': 'Financial Services'},
            # Add more industries...
        ]
    
    def _get_seniority_targeting(self) -> List[Dict]:
        """Get seniority targeting options"""
        return [
            {'id': '1', 'name': 'Unpaid'},
            {'id': '2', 'name': 'Training'},
            {'id': '3', 'name': 'Entry'},
            {'id': '4', 'name': 'Associate'},
            {'id': '5', 'name': 'Mid-Senior level'},
            {'id': '6', 'name': 'Director'},
            {'id': '7', 'name': 'Executive'},
        ]
    
    def _get_location_targeting(self) -> List[Dict]:
        """Get location targeting options"""
        return [
            {'id': '103644278', 'name': 'United States'},
            {'id': '101174742', 'name': 'Canada'},
            {'id': '102277331', 'name': 'United Kingdom'},
            # Add more locations...
        ]
    
    def _parse_linkedin_metrics(self, elements: List[Dict]) -> Dict[str, Any]:
        """Parse LinkedIn analytics response"""
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
        
        for element in elements:
            if 'impressions' in element:
                metrics['impressions'] += element['impressions']
            if 'clicks' in element:
                metrics['clicks'] += element['clicks']
            if 'costInUsd' in element:
                metrics['spend'] += element['costInUsd']
            if 'externalWebsiteConversions' in element:
                metrics['conversions'] += element['externalWebsiteConversions']
            if 'videoViews' in element:
                metrics['video_views'] += element['videoViews']
        
        # Calculate derived metrics
        if metrics['impressions'] > 0:
            metrics['ctr'] = (metrics['clicks'] / metrics['impressions']) * 100
        
        if metrics['clicks'] > 0:
            metrics['cpc'] = metrics['spend'] / metrics['clicks']
        
        if metrics['conversions'] > 0:
            metrics['cpa'] = metrics['spend'] / metrics['conversions']
        
        return metrics