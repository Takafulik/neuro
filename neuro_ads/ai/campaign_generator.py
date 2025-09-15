"""
AI Campaign Generator for autonomous ad campaign creation
"""

import logging
import json
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.db import transaction
from ..models import Campaign, AdSet, AdCreative, AdPlatform
from ..services.google_ads import GoogleAdsService
from ..services.meta_ads import MetaAdsService
from ..services.linkedin_ads import LinkedInAdsService

logger = logging.getLogger(__name__)


class CampaignGenerator:
    """AI-powered campaign generation system"""
    
    def __init__(self, user: User):
        self.user = user
        self.platforms = {
            'google': GoogleAdsService(user),
            'meta': MetaAdsService(user),
            'linkedin': LinkedInAdsService(user)
        }
    
    def generate_autonomous_campaign(
        self, 
        campaign_brief: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a complete autonomous campaign across multiple platforms
        
        Args:
            campaign_brief: {
                'business_description': str,
                'target_audience': str,
                'campaign_goal': str,
                'total_budget': float,
                'duration_days': int,
                'product_service': str,
                'website_url': str,
                'preferred_platforms': List[str]
            }
        """
        try:
            with transaction.atomic():
                # 1. Analyze campaign brief and generate strategy
                campaign_strategy = self._analyze_campaign_brief(campaign_brief)
                
                # 2. Create master campaign
                campaign = self._create_master_campaign(campaign_brief, campaign_strategy)
                
                # 3. Generate platform-specific campaigns
                platform_campaigns = {}
                for platform_name in campaign_brief.get('preferred_platforms', ['google', 'meta', 'linkedin']):
                    if platform_name in self.platforms:
                        platform_campaign = self._generate_platform_campaign(
                            campaign, platform_name, campaign_strategy
                        )
                        platform_campaigns[platform_name] = platform_campaign
                
                # 4. Generate AI-optimized content variations
                content_variations = self._generate_content_variations(campaign_brief, campaign_strategy)
                
                # 5. Create A/B test configurations
                ab_test_configs = self._create_ab_test_configurations(campaign, content_variations)
                
                return {
                    'success': True,
                    'campaign': campaign,
                    'platform_campaigns': platform_campaigns,
                    'content_variations': content_variations,
                    'ab_test_configs': ab_test_configs,
                    'strategy': campaign_strategy
                }
                
        except Exception as e:
            logger.error(f"Campaign generation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _analyze_campaign_brief(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze campaign brief and generate AI strategy"""
        
        # AI analysis of business description and goals
        business_type = self._classify_business_type(brief['business_description'])
        audience_segments = self._identify_audience_segments(brief['target_audience'])
        campaign_objectives = self._map_campaign_objectives(brief['campaign_goal'])
        
        # Budget allocation strategy
        budget_allocation = self._calculate_budget_allocation(
            brief['total_budget'], 
            brief.get('preferred_platforms', ['google', 'meta', 'linkedin'])
        )
        
        # Content strategy
        content_themes = self._generate_content_themes(brief)
        
        # Targeting strategy
        targeting_strategy = self._generate_targeting_strategy(brief, audience_segments)
        
        return {
            'business_type': business_type,
            'audience_segments': audience_segments,
            'campaign_objectives': campaign_objectives,
            'budget_allocation': budget_allocation,
            'content_themes': content_themes,
            'targeting_strategy': targeting_strategy,
            'optimization_goals': self._set_optimization_goals(brief['campaign_goal']),
            'bidding_strategy': self._recommend_bidding_strategy(brief)
        }
    
    def _classify_business_type(self, description: str) -> Dict[str, Any]:
        """AI classification of business type from description"""
        
        # Keywords for different business types
        b2b_keywords = ['software', 'saas', 'enterprise', 'business', 'professional', 'consulting']
        b2c_keywords = ['consumer', 'retail', 'ecommerce', 'shop', 'buy', 'product']
        service_keywords = ['service', 'agency', 'consulting', 'professional']
        product_keywords = ['product', 'manufacturing', 'retail', 'ecommerce']
        
        description_lower = description.lower()
        
        # Simple keyword-based classification (can be enhanced with ML)
        b2b_score = sum(1 for keyword in b2b_keywords if keyword in description_lower)
        b2c_score = sum(1 for keyword in b2c_keywords if keyword in description_lower)
        service_score = sum(1 for keyword in service_keywords if keyword in description_lower)
        product_score = sum(1 for keyword in product_keywords if keyword in description_lower)
        
        primary_type = 'B2B' if b2b_score > b2c_score else 'B2C'
        secondary_type = 'Service' if service_score > product_score else 'Product'
        
        return {
            'primary': primary_type,
            'secondary': secondary_type,
            'confidence': max(b2b_score, b2c_score) / len(description.split()),
            'characteristics': {
                'b2b_indicators': b2b_score,
                'b2c_indicators': b2c_score,
                'service_indicators': service_score,
                'product_indicators': product_score
            }
        }
    
    def _identify_audience_segments(self, target_audience: str) -> List[Dict[str, Any]]:
        """Identify and segment target audience"""
        
        # Parse audience description for demographics, interests, behaviors
        audience_lower = target_audience.lower()
        
        # Age identification
        age_ranges = []
        if 'young' in audience_lower or '18-25' in audience_lower or 'gen z' in audience_lower:
            age_ranges.append({'min': 18, 'max': 25, 'label': 'Gen Z'})
        if 'millennial' in audience_lower or '25-35' in audience_lower or '26-40' in audience_lower:
            age_ranges.append({'min': 25, 'max': 40, 'label': 'Millennials'})
        if 'gen x' in audience_lower or '35-50' in audience_lower or '40-55' in audience_lower:
            age_ranges.append({'min': 35, 'max': 55, 'label': 'Gen X'})
        if 'boomer' in audience_lower or '50+' in audience_lower or 'senior' in audience_lower:
            age_ranges.append({'min': 50, 'max': 65, 'label': 'Baby Boomers'})
        
        # Default age range if none specified
        if not age_ranges:
            age_ranges = [{'min': 25, 'max': 55, 'label': 'Adults'}]
        
        # Interest identification
        interests = []
        interest_keywords = {
            'technology': ['tech', 'software', 'digital', 'innovation'],
            'business': ['business', 'professional', 'entrepreneur', 'startup'],
            'lifestyle': ['lifestyle', 'wellness', 'health', 'fitness'],
            'entertainment': ['entertainment', 'music', 'movies', 'gaming'],
            'education': ['education', 'learning', 'courses', 'training']
        }
        
        for category, keywords in interest_keywords.items():
            if any(keyword in audience_lower for keyword in keywords):
                interests.append(category)
        
        # Behavior identification
        behaviors = []
        if 'online' in audience_lower or 'digital' in audience_lower:
            behaviors.append('online_shoppers')
        if 'mobile' in audience_lower or 'app' in audience_lower:
            behaviors.append('mobile_users')
        if 'social' in audience_lower or 'facebook' in audience_lower:
            behaviors.append('social_media_users')
        
        return [{
            'age_ranges': age_ranges,
            'interests': interests,
            'behaviors': behaviors,
            'segment_name': 'Primary Audience',
            'size_estimate': 'medium'
        }]
    
    def _map_campaign_objectives(self, goal: str) -> Dict[str, Any]:
        """Map campaign goal to platform-specific objectives"""
        
        goal_lower = goal.lower()
        
        objective_mapping = {
            'awareness': {
                'google': 'DISPLAY',
                'meta': 'BRAND_AWARENESS',
                'linkedin': 'BRAND_AWARENESS',
                'primary_kpi': 'impressions',
                'secondary_kpi': 'reach'
            },
            'traffic': {
                'google': 'SEARCH',
                'meta': 'LINK_CLICKS',
                'linkedin': 'WEBSITE_VISITS',
                'primary_kpi': 'clicks',
                'secondary_kpi': 'ctr'
            },
            'leads': {
                'google': 'SEARCH',
                'meta': 'LEAD_GENERATION',
                'linkedin': 'LEAD_GENERATION',
                'primary_kpi': 'conversions',
                'secondary_kpi': 'cpa'
            },
            'sales': {
                'google': 'SHOPPING',
                'meta': 'CONVERSIONS',
                'linkedin': 'WEBSITE_CONVERSIONS',
                'primary_kpi': 'conversions',
                'secondary_kpi': 'roas'
            }
        }
        
        # Determine primary objective
        if any(keyword in goal_lower for keyword in ['awareness', 'brand', 'visibility']):
            return objective_mapping['awareness']
        elif any(keyword in goal_lower for keyword in ['traffic', 'visits', 'website']):
            return objective_mapping['traffic']
        elif any(keyword in goal_lower for keyword in ['leads', 'signup', 'contact']):
            return objective_mapping['leads']
        elif any(keyword in goal_lower for keyword in ['sales', 'purchase', 'buy', 'revenue']):
            return objective_mapping['sales']
        else:
            return objective_mapping['traffic']  # Default
    
    def _calculate_budget_allocation(self, total_budget: float, platforms: List[str]) -> Dict[str, float]:
        """Calculate optimal budget allocation across platforms"""
        
        # Platform allocation weights based on typical performance
        platform_weights = {
            'google': 0.4,  # Generally high intent traffic
            'meta': 0.35,   # Good for awareness and targeting
            'linkedin': 0.25  # Best for B2B but more expensive
        }
        
        # Adjust weights based on selected platforms
        selected_weights = {p: platform_weights.get(p, 0.33) for p in platforms}
        total_weight = sum(selected_weights.values())
        
        # Normalize weights
        normalized_weights = {p: w/total_weight for p, w in selected_weights.items()}
        
        # Allocate budget
        allocation = {}
        for platform, weight in normalized_weights.items():
            allocation[platform] = total_budget * weight
        
        return allocation
    
    def _generate_content_themes(self, brief: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate content themes based on campaign brief"""
        
        business_desc = brief['business_description'].lower()
        goal = brief['campaign_goal'].lower()
        
        themes = []
        
        # Problem-solution theme
        themes.append({
            'theme': 'problem_solution',
            'headline_template': "Solve {problem} with {solution}",
            'description_template': "Discover how {product_service} helps {target_audience} achieve {benefit}",
            'cta_options': ['Learn More', 'Get Started', 'Try Now']
        })
        
        # Benefit-focused theme
        themes.append({
            'theme': 'benefit_focused',
            'headline_template': "{benefit} for {target_audience}",
            'description_template': "Experience {key_benefit} with our {product_service}. Join thousands of satisfied customers.",
            'cta_options': ['See Benefits', 'Start Today', 'Learn How']
        })
        
        # Urgency theme
        themes.append({
            'theme': 'urgency',
            'headline_template': "Limited Time: {offer}",
            'description_template': "Don't miss out! Get {benefit} with {product_service}. Offer expires soon.",
            'cta_options': ['Act Now', 'Claim Offer', 'Get Started']
        })
        
        # Trust/social proof theme
        themes.append({
            'theme': 'social_proof',
            'headline_template': "Join {number}+ Happy Customers",
            'description_template': "See why {number}+ businesses trust {product_service} for {benefit}",
            'cta_options': ['Join Now', 'See Reviews', 'Get Started']
        })
        
        return themes
    
    def _generate_targeting_strategy(self, brief: Dict[str, Any], audience_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate platform-specific targeting strategies"""
        
        strategy = {}
        
        for platform in ['google', 'meta', 'linkedin']:
            if platform == 'google':
                strategy[platform] = self._generate_google_targeting(brief, audience_segments)
            elif platform == 'meta':
                strategy[platform] = self._generate_meta_targeting(brief, audience_segments)
            elif platform == 'linkedin':
                strategy[platform] = self._generate_linkedin_targeting(brief, audience_segments)
        
        return strategy
    
    def _generate_google_targeting(self, brief: Dict[str, Any], audience_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate Google Ads targeting strategy"""
        
        # Keywords based on business description
        keywords = self._extract_keywords_from_description(brief['business_description'])
        
        # Location targeting (default to major markets)
        locations = ['2840']  # United States
        
        # Demographics
        age_ranges = []
        for segment in audience_segments:
            for age_range in segment['age_ranges']:
                age_ranges.append(f"AGE_RANGE_{age_range['min']}_{age_range['max']}")
        
        return {
            'keywords': keywords,
            'locations': locations,
            'age_ranges': age_ranges,
            'match_types': ['EXACT', 'PHRASE', 'BROAD']
        }
    
    def _generate_meta_targeting(self, brief: Dict[str, Any], audience_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate Meta targeting strategy"""
        
        # Interest targeting
        interests = []
        for segment in audience_segments:
            interests.extend(segment.get('interests', []))
        
        # Behavior targeting
        behaviors = []
        for segment in audience_segments:
            behaviors.extend(segment.get('behaviors', []))
        
        # Demographics
        age_min = min(r['min'] for s in audience_segments for r in s['age_ranges'])
        age_max = max(r['max'] for s in audience_segments for r in s['age_ranges'])
        
        return {
            'interests': interests,
            'behaviors': behaviors,
            'age_min': age_min,
            'age_max': age_max,
            'locations': ['US', 'CA'],  # Default locations
            'genders': [1, 2]  # All genders
        }
    
    def _generate_linkedin_targeting(self, brief: Dict[str, Any], audience_segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate LinkedIn targeting strategy"""
        
        business_type = brief.get('business_description', '').lower()
        
        # Job titles based on business type
        job_titles = []
        if 'marketing' in business_type:
            job_titles.extend(['25', '26'])  # Marketing roles
        if 'technology' in business_type or 'software' in business_type:
            job_titles.extend(['26', '27'])  # Tech roles
        
        # Industries
        industries = []
        if 'technology' in business_type:
            industries.append('6')  # IT and Services
        if 'marketing' in business_type:
            industries.append('7')  # Marketing and Advertising
        
        # Seniority levels
        seniority = ['4', '5', '6']  # Associate to Director level
        
        return {
            'job_titles': job_titles,
            'industries': industries,
            'seniority': seniority,
            'locations': ['103644278']  # United States
        }
    
    def _set_optimization_goals(self, campaign_goal: str) -> Dict[str, str]:
        """Set optimization goals for each platform"""
        
        goal_lower = campaign_goal.lower()
        
        if 'awareness' in goal_lower:
            return {
                'google': 'MAXIMIZE_IMPRESSIONS',
                'meta': 'REACH',
                'linkedin': 'BRAND_AWARENESS'
            }
        elif 'traffic' in goal_lower:
            return {
                'google': 'MAXIMIZE_CLICKS',
                'meta': 'LINK_CLICKS',
                'linkedin': 'WEBSITE_VISITS'
            }
        elif 'leads' in goal_lower:
            return {
                'google': 'MAXIMIZE_CONVERSIONS',
                'meta': 'LEAD_GENERATION',
                'linkedin': 'LEAD_GENERATION'
            }
        else:
            return {
                'google': 'MAXIMIZE_CONVERSION_VALUE',
                'meta': 'CONVERSIONS',
                'linkedin': 'WEBSITE_CONVERSIONS'
            }
    
    def _recommend_bidding_strategy(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend bidding strategy based on campaign goals and budget"""
        
        budget = brief['total_budget']
        goal = brief['campaign_goal'].lower()
        
        if budget < 1000:  # Small budget
            return {
                'strategy': 'automated',
                'google': 'MAXIMIZE_CLICKS',
                'meta': 'LOWEST_COST_WITHOUT_CAP',
                'linkedin': 'CPC'
            }
        elif 'conversion' in goal or 'sales' in goal:
            return {
                'strategy': 'conversion_focused',
                'google': 'TARGET_CPA',
                'meta': 'LOWEST_COST_WITH_CAP',
                'linkedin': 'CPC'
            }
        else:
            return {
                'strategy': 'traffic_focused',
                'google': 'MAXIMIZE_CLICKS',
                'meta': 'LOWEST_COST_WITHOUT_CAP',
                'linkedin': 'CPC'
            }
    
    def _extract_keywords_from_description(self, description: str) -> List[str]:
        """Extract relevant keywords from business description"""
        
        # Simple keyword extraction (can be enhanced with NLP)
        words = description.lower().split()
        
        # Filter out common words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'a', 'an'}
        keywords = [word.strip('.,!?') for word in words if word not in stop_words and len(word) > 3]
        
        # Return top keywords
        return keywords[:20]
    
    def _create_master_campaign(self, brief: Dict[str, Any], strategy: Dict[str, Any]) -> Campaign:
        """Create the master campaign object"""
        
        campaign = Campaign.objects.create(
            user=self.user,
            name=f"AI Campaign - {brief.get('product_service', 'Product')}",
            description=f"Auto-generated campaign for {brief['business_description']}",
            campaign_type=self._map_goal_to_type(brief['campaign_goal']),
            target_audience=strategy['audience_segments'],
            total_budget=brief['total_budget'],
            daily_budget=brief['total_budget'] / brief.get('duration_days', 30),
            ai_generated_copy={},
            ai_generated_keywords=self._extract_keywords_from_description(brief['business_description']),
            ai_target_suggestions=strategy['targeting_strategy'],
            auto_optimization=True,
            auto_budget_reallocation=True,
            auto_ab_testing=True,
            status='draft'
        )
        
        return campaign
    
    def _map_goal_to_type(self, goal: str) -> str:
        """Map campaign goal to campaign type"""
        
        goal_lower = goal.lower()
        
        if 'awareness' in goal_lower or 'brand' in goal_lower:
            return 'awareness'
        elif 'traffic' in goal_lower or 'visits' in goal_lower:
            return 'traffic'
        elif 'engagement' in goal_lower:
            return 'engagement'
        elif 'leads' in goal_lower or 'signup' in goal_lower:
            return 'leads'
        elif 'sales' in goal_lower or 'purchase' in goal_lower:
            return 'sales'
        else:
            return 'conversions'
    
    def _generate_platform_campaign(self, campaign: Campaign, platform_name: str, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Generate platform-specific campaign configuration"""
        
        platform = AdPlatform.objects.get(name=platform_name)
        budget_allocation = strategy['budget_allocation'][platform_name]
        
        # Create ad set for this platform
        ad_set = AdSet.objects.create(
            campaign=campaign,
            platform=platform,
            name=f"{campaign.name} - {platform.get_name_display()}",
            allocated_budget=budget_allocation,
            targeting_parameters=strategy['targeting_strategy'][platform_name]
        )
        
        return {
            'ad_set': ad_set,
            'budget': budget_allocation,
            'targeting': strategy['targeting_strategy'][platform_name],
            'optimization_goal': strategy['optimization_goals'][platform_name]
        }
    
    def _generate_content_variations(self, brief: Dict[str, Any], strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate AI-optimized content variations for A/B testing"""
        
        variations = []
        themes = strategy['content_themes']
        
        for i, theme in enumerate(themes[:3]):  # Generate 3 main variations
            
            # Generate headlines
            headlines = self._generate_headlines(brief, theme)
            
            # Generate descriptions
            descriptions = self._generate_descriptions(brief, theme)
            
            # Generate CTAs
            ctas = theme['cta_options']
            
            variation = {
                'variation_id': i + 1,
                'theme': theme['theme'],
                'headlines': headlines,
                'descriptions': descriptions,
                'ctas': ctas,
                'confidence_score': random.uniform(0.7, 0.95)  # Simulated AI confidence
            }
            
            variations.append(variation)
        
        return variations
    
    def _generate_headlines(self, brief: Dict[str, Any], theme: Dict[str, Any]) -> List[str]:
        """Generate headline variations based on theme"""
        
        product_service = brief.get('product_service', 'Our Solution')
        target_audience = brief.get('target_audience', 'Businesses')
        
        # Template-based generation (can be enhanced with AI/NLP)
        templates = {
            'problem_solution': [
                f"Solve Your Biggest Challenge with {product_service}",
                f"The Solution {target_audience} Have Been Waiting For",
                f"Transform Your Business with {product_service}"
            ],
            'benefit_focused': [
                f"Increase Efficiency with {product_service}",
                f"Save Time and Money with {product_service}",
                f"Get Better Results with {product_service}"
            ],
            'urgency': [
                f"Limited Time: Special Offer on {product_service}",
                f"Don't Miss Out - {product_service} Available Now",
                f"Act Fast: Exclusive {product_service} Deal"
            ],
            'social_proof': [
                f"Join 10,000+ Happy Customers",
                f"Trusted by Industry Leaders",
                f"The #1 Choice for {target_audience}"
            ]
        }
        
        return templates.get(theme['theme'], templates['benefit_focused'])
    
    def _generate_descriptions(self, brief: Dict[str, Any], theme: Dict[str, Any]) -> List[str]:
        """Generate description variations based on theme"""
        
        product_service = brief.get('product_service', 'our solution')
        business_desc = brief.get('business_description', 'your business')
        
        # Template-based generation
        templates = {
            'problem_solution': [
                f"Discover how {product_service} solves your biggest challenges and drives real results.",
                f"Stop struggling with inefficient processes. {product_service.title()} streamlines everything.",
                f"Get the solution that actually works. Proven results for businesses like yours."
            ],
            'benefit_focused': [
                f"Experience the benefits that matter most to your business success.",
                f"Save time, reduce costs, and improve outcomes with {product_service}.",
                f"Get more done in less time with our proven {product_service}."
            ],
            'urgency': [
                f"Limited time offer - don't miss your chance to save and improve your results.",
                f"Special pricing available now. Join thousands of satisfied customers today.",
                f"Exclusive offer ends soon. Start transforming your business now."
            ],
            'social_proof': [
                f"See why thousands of businesses trust us for their {product_service} needs.",
                f"Join the community of successful businesses that chose {product_service}.",
                f"Proven track record with industry-leading customer satisfaction."
            ]
        }
        
        return templates.get(theme['theme'], templates['benefit_focused'])
    
    def _create_ab_test_configurations(self, campaign: Campaign, content_variations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create A/B test configurations for content variations"""
        
        from ..models import ABTest
        
        ab_tests = []
        
        # Create headline A/B test
        headline_test = ABTest.objects.create(
            campaign=campaign,
            name=f"{campaign.name} - Headline Test",
            test_type='headline',
            confidence_level=0.95,
            minimum_sample_size=1000,
            test_duration_days=7,
            status='draft'
        )
        
        ab_tests.append({
            'test': headline_test,
            'variations': [var['headlines'] for var in content_variations],
            'type': 'headline'
        })
        
        # Create description A/B test
        description_test = ABTest.objects.create(
            campaign=campaign,
            name=f"{campaign.name} - Description Test",
            test_type='description',
            confidence_level=0.95,
            minimum_sample_size=1000,
            test_duration_days=7,
            status='draft'
        )
        
        ab_tests.append({
            'test': description_test,
            'variations': [var['descriptions'] for var in content_variations],
            'type': 'description'
        })
        
        # Create CTA A/B test
        cta_test = ABTest.objects.create(
            campaign=campaign,
            name=f"{campaign.name} - CTA Test",
            test_type='cta',
            confidence_level=0.95,
            minimum_sample_size=500,
            test_duration_days=5,
            status='draft'
        )
        
        ab_tests.append({
            'test': cta_test,
            'variations': [var['ctas'] for var in content_variations],
            'type': 'cta'
        })
        
        return ab_tests