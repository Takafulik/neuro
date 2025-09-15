"""
Automated A/B Testing Engine for ad creatives and copy optimization
"""

import logging
import math
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from scipy import stats
from ..models import Campaign, AdCreative, ABTest, CampaignAnalytics

logger = logging.getLogger(__name__)


class ABTestEngine:
    """Automated A/B testing engine for ad optimization"""
    
    def __init__(self):
        self.min_sample_size = 100           # Minimum sample size per variant
        self.max_test_duration_days = 14     # Maximum test duration
        self.significance_threshold = 0.05   # Statistical significance threshold (95% confidence)
        self.minimum_effect_size = 0.1       # Minimum effect size to declare winner (10% improvement)
        self.early_stopping_threshold = 0.01 # Stop early if very significant (99% confidence)
    
    def run_ab_test_analysis(self, ab_test: ABTest) -> Dict[str, Any]:
        """
        Run statistical analysis on an A/B test
        
        Returns:
            Dict with test results, winner, and recommendations
        """
        try:
            if ab_test.status not in ['running']:
                return {'success': False, 'reason': f'Test is not running (status: {ab_test.status})'}
            
            # Get test data
            test_data = self._get_test_data(ab_test)
            
            if not test_data or len(test_data) < 2:
                return {'success': False, 'reason': 'Insufficient test data'}
            
            # Perform statistical analysis
            statistical_results = self._perform_statistical_analysis(test_data, ab_test.test_type)
            
            # Check if test should be stopped
            should_stop, stop_reason = self._should_stop_test(ab_test, statistical_results)
            
            if should_stop:
                winner_result = self._declare_winner(ab_test, statistical_results)
                return self._finalize_test(ab_test, statistical_results, winner_result, stop_reason)
            else:
                return {
                    'success': True,
                    'status': 'continue',
                    'statistical_results': statistical_results,
                    'recommendation': 'Continue test - insufficient data for conclusion'
                }
                
        except Exception as e:
            logger.error(f"A/B test analysis failed for test {ab_test.id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_automated_ab_test(self, campaign: Campaign, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create and launch an automated A/B test
        
        Args:
            campaign: Campaign to test
            test_config: {
                'test_type': str ('headline', 'description', 'cta', 'creative'),
                'variants': List[Dict],
                'traffic_split': float (0.5 for 50/50 split),
                'primary_metric': str ('ctr', 'conversions', 'cpa'),
                'duration_days': int
            }
        """
        try:
            # Validate test configuration
            validation_result = self._validate_test_config(test_config)
            if not validation_result['valid']:
                return {'success': False, 'reason': validation_result['error']}
            
            # Create A/B test record
            ab_test = ABTest.objects.create(
                campaign=campaign,
                name=f"{campaign.name} - {test_config['test_type'].title()} Test",
                test_type=test_config['test_type'],
                confidence_level=0.95,
                minimum_sample_size=test_config.get('min_sample_size', self.min_sample_size),
                test_duration_days=test_config.get('duration_days', 7),
                status='draft'
            )
            
            # Create test variants (ad creatives)
            variants = self._create_test_variants(ab_test, test_config['variants'])
            
            # Launch test
            launch_result = self._launch_test(ab_test, variants, test_config)
            
            if launch_result['success']:
                ab_test.status = 'running'
                ab_test.started_at = timezone.now()
                ab_test.save()
                
                return {
                    'success': True,
                    'ab_test': ab_test,
                    'variants': variants,
                    'launch_details': launch_result
                }
            else:
                ab_test.delete()
                return {'success': False, 'reason': launch_result.get('error', 'Failed to launch test')}
                
        except Exception as e:
            logger.error(f"Failed to create A/B test: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_test_data(self, ab_test: ABTest) -> List[Dict[str, Any]]:
        """Get performance data for A/B test variants"""
        
        # Get all ad creatives for this test
        test_creatives = AdCreative.objects.filter(
            ad_set__campaign=ab_test.campaign,
            created_at__gte=ab_test.started_at
        ) if ab_test.started_at else AdCreative.objects.none()
        
        test_data = []
        
        for creative in test_creatives:
            # Get performance metrics for this creative
            end_date = date.today()
            start_date = ab_test.started_at.date() if ab_test.started_at else end_date - timedelta(days=7)
            
            analytics = CampaignAnalytics.objects.filter(
                campaign=ab_test.campaign,
                date__gte=start_date,
                date__lte=end_date
            )
            
            # Aggregate metrics (simplified - in real implementation, you'd track creative-specific metrics)
            metrics = analytics.aggregate(
                total_impressions=Sum('impressions'),
                total_clicks=Sum('clicks'),
                total_conversions=Sum('conversions'),
                total_spend=Sum('spend')
            )
            
            impressions = metrics['total_impressions'] or 0
            clicks = metrics['total_clicks'] or 0
            conversions = metrics['total_conversions'] or 0
            spend = float(metrics['total_spend'] or 0)
            
            test_data.append({
                'creative_id': creative.id,
                'creative_name': creative.name,
                'variant_type': self._get_variant_type(creative, ab_test.test_type),
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
                'spend': spend,
                'ctr': (clicks / impressions * 100) if impressions > 0 else 0,
                'conversion_rate': (conversions / clicks * 100) if clicks > 0 else 0,
                'cpc': (spend / clicks) if clicks > 0 else 0,
                'cpa': (spend / conversions) if conversions > 0 else 0
            })
        
        return test_data
    
    def _perform_statistical_analysis(self, test_data: List[Dict[str, Any]], test_type: str) -> Dict[str, Any]:
        """Perform statistical analysis on test data"""
        
        if len(test_data) < 2:
            return {'error': 'Need at least 2 variants for analysis'}
        
        # Group data by variant
        variants = {}
        for data in test_data:
            variant = data['variant_type']
            if variant not in variants:
                variants[variant] = []
            variants[variant].append(data)
        
        # Calculate aggregate metrics for each variant
        variant_results = {}
        
        for variant_name, variant_data in variants.items():
            total_impressions = sum(d['impressions'] for d in variant_data)
            total_clicks = sum(d['clicks'] for d in variant_data)
            total_conversions = sum(d['conversions'] for d in variant_data)
            total_spend = sum(d['spend'] for d in variant_data)
            
            variant_results[variant_name] = {
                'impressions': total_impressions,
                'clicks': total_clicks,
                'conversions': total_conversions,
                'spend': total_spend,
                'ctr': (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
                'conversion_rate': (total_conversions / total_clicks * 100) if total_clicks > 0 else 0,
                'cpc': (total_spend / total_clicks) if total_clicks > 0 else 0,
                'cpa': (total_spend / total_conversions) if total_conversions > 0 else 0,
                'sample_size': total_impressions  # Using impressions as sample size
            }
        
        # Perform pairwise statistical tests
        statistical_tests = self._perform_pairwise_tests(variant_results, test_type)
        
        # Determine overall significance
        is_significant = any(test['p_value'] < self.significance_threshold for test in statistical_tests)
        
        return {
            'variant_results': variant_results,
            'statistical_tests': statistical_tests,
            'is_significant': is_significant,
            'analysis_date': datetime.now().isoformat()
        }
    
    def _perform_pairwise_tests(self, variant_results: Dict[str, Dict], test_type: str) -> List[Dict[str, Any]]:
        """Perform pairwise statistical tests between variants"""
        
        tests = []
        variant_names = list(variant_results.keys())
        
        # Determine primary metric based on test type
        if test_type in ['headline', 'description', 'cta']:
            primary_metric = 'ctr'
        elif test_type == 'creative':
            primary_metric = 'conversion_rate'
        else:
            primary_metric = 'ctr'
        
        # Perform tests between all pairs
        for i in range(len(variant_names)):
            for j in range(i + 1, len(variant_names)):
                variant_a = variant_names[i]
                variant_b = variant_names[j]
                
                data_a = variant_results[variant_a]
                data_b = variant_results[variant_b]
                
                # Perform appropriate statistical test
                if primary_metric in ['ctr', 'conversion_rate']:
                    test_result = self._two_proportion_z_test(
                        data_a['clicks'], data_a['impressions'],
                        data_b['clicks'], data_b['impressions']
                    )
                else:
                    # For continuous metrics like CPA, CPC
                    test_result = self._welch_t_test(data_a, data_b, primary_metric)
                
                tests.append({
                    'variant_a': variant_a,
                    'variant_b': variant_b,
                    'metric': primary_metric,
                    'p_value': test_result['p_value'],
                    'confidence_interval': test_result.get('confidence_interval'),
                    'effect_size': test_result.get('effect_size', 0),
                    'winner': test_result.get('winner'),
                    'is_significant': test_result['p_value'] < self.significance_threshold
                })
        
        return tests
    
    def _two_proportion_z_test(self, successes_a: int, trials_a: int, successes_b: int, trials_b: int) -> Dict[str, Any]:
        """Perform two-proportion z-test"""
        
        if trials_a == 0 or trials_b == 0:
            return {'p_value': 1.0, 'effect_size': 0, 'winner': 'inconclusive'}
        
        p_a = successes_a / trials_a
        p_b = successes_b / trials_b
        
        # Pooled proportion
        p_pool = (successes_a + successes_b) / (trials_a + trials_b)
        
        # Standard error
        se = math.sqrt(p_pool * (1 - p_pool) * (1/trials_a + 1/trials_b))
        
        if se == 0:
            return {'p_value': 1.0, 'effect_size': 0, 'winner': 'inconclusive'}
        
        # Z-score
        z_score = (p_a - p_b) / se
        
        # P-value (two-tailed)
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
        
        # Effect size (relative improvement)
        effect_size = abs(p_a - p_b) / p_b if p_b > 0 else 0
        
        # Determine winner
        winner = 'A' if p_a > p_b else 'B' if p_b > p_a else 'tie'
        
        # Confidence interval for difference in proportions
        se_diff = math.sqrt((p_a * (1-p_a) / trials_a) + (p_b * (1-p_b) / trials_b))
        margin_error = 1.96 * se_diff
        diff = p_a - p_b
        ci_lower = diff - margin_error
        ci_upper = diff + margin_error
        
        return {
            'p_value': p_value,
            'z_score': z_score,
            'effect_size': effect_size,
            'winner': winner,
            'confidence_interval': [ci_lower, ci_upper],
            'p_a': p_a,
            'p_b': p_b
        }
    
    def _welch_t_test(self, data_a: Dict, data_b: Dict, metric: str) -> Dict[str, Any]:
        """Perform Welch's t-test for continuous metrics"""
        
        # For simplicity, we'll estimate variance from the data we have
        # In a real implementation, you'd need actual sample data points
        
        mean_a = data_a.get(metric, 0)
        mean_b = data_b.get(metric, 0)
        
        # Estimate variance (simplified)
        var_a = (mean_a * 0.2) ** 2  # Assume 20% coefficient of variation
        var_b = (mean_b * 0.2) ** 2
        
        n_a = max(data_a.get('sample_size', 1), 1)
        n_b = max(data_b.get('sample_size', 1), 1)
        
        # Standard error of difference
        se_diff = math.sqrt(var_a/n_a + var_b/n_b)
        
        if se_diff == 0:
            return {'p_value': 1.0, 'effect_size': 0, 'winner': 'inconclusive'}
        
        # T-score
        t_score = (mean_a - mean_b) / se_diff
        
        # Degrees of freedom (Welch's formula)
        df = (var_a/n_a + var_b/n_b)**2 / ((var_a/n_a)**2/(n_a-1) + (var_b/n_b)**2/(n_b-1))
        df = max(df, 1)
        
        # P-value (two-tailed)
        p_value = 2 * (1 - stats.t.cdf(abs(t_score), df))
        
        # Effect size
        effect_size = abs(mean_a - mean_b) / max(mean_b, 0.001) if mean_b > 0 else 0
        
        # Winner (for CPA and CPC, lower is better)
        if metric in ['cpa', 'cpc']:
            winner = 'A' if mean_a < mean_b else 'B' if mean_b < mean_a else 'tie'
        else:
            winner = 'A' if mean_a > mean_b else 'B' if mean_b > mean_a else 'tie'
        
        return {
            'p_value': p_value,
            't_score': t_score,
            'effect_size': effect_size,
            'winner': winner,
            'mean_a': mean_a,
            'mean_b': mean_b
        }
    
    def _should_stop_test(self, ab_test: ABTest, statistical_results: Dict[str, Any]) -> Tuple[bool, str]:
        """Determine if test should be stopped"""
        
        # Check minimum duration
        if ab_test.started_at:
            days_running = (timezone.now() - ab_test.started_at).days
            if days_running < 3:  # Minimum 3 days
                return False, "Test running less than minimum duration"
        
        # Check maximum duration
        if ab_test.started_at:
            days_running = (timezone.now() - ab_test.started_at).days
            if days_running >= self.max_test_duration_days:
                return True, "Maximum test duration reached"
        
        # Check sample size
        variant_results = statistical_results.get('variant_results', {})
        min_sample_size_met = all(
            result['sample_size'] >= ab_test.minimum_sample_size 
            for result in variant_results.values()
        )
        
        if not min_sample_size_met:
            return False, "Minimum sample size not reached"
        
        # Check statistical significance
        statistical_tests = statistical_results.get('statistical_tests', [])
        
        # Early stopping for very significant results
        very_significant = any(
            test['p_value'] < self.early_stopping_threshold and test['effect_size'] > self.minimum_effect_size 
            for test in statistical_tests
        )
        
        if very_significant:
            return True, "Early stopping - very significant result"
        
        # Regular significance check
        significant = any(
            test['p_value'] < self.significance_threshold and test['effect_size'] > self.minimum_effect_size 
            for test in statistical_tests
        )
        
        if significant and ab_test.started_at:
            days_running = (timezone.now() - ab_test.started_at).days
            if days_running >= 5:  # Minimum 5 days for regular significance
                return True, "Statistically significant result"
        
        # Check if test has been running for the planned duration
        if ab_test.started_at:
            days_running = (timezone.now() - ab_test.started_at).days
            if days_running >= ab_test.test_duration_days:
                return True, "Planned test duration completed"
        
        return False, "Continue test"
    
    def _declare_winner(self, ab_test: ABTest, statistical_results: Dict[str, Any]) -> Dict[str, Any]:
        """Declare the winning variant"""
        
        statistical_tests = statistical_results.get('statistical_tests', [])
        variant_results = statistical_results.get('variant_results', {})
        
        # Find the most significant test
        significant_tests = [test for test in statistical_tests if test['is_significant']]
        
        if not significant_tests:
            return {
                'winner': None,
                'winner_name': 'No clear winner',
                'confidence': 0.0,
                'improvement': 0.0,
                'reason': 'No statistically significant difference found'
            }
        
        # Get the test with the highest confidence (lowest p-value)
        best_test = min(significant_tests, key=lambda x: x['p_value'])
        
        # Determine winner details
        winner_variant = best_test['winner']
        if winner_variant == 'A':
            winner_name = best_test['variant_a']
        elif winner_variant == 'B':
            winner_name = best_test['variant_b']
        else:
            winner_name = 'Tie'
        
        confidence = 1 - best_test['p_value']
        improvement = best_test['effect_size'] * 100  # Convert to percentage
        
        return {
            'winner': winner_variant,
            'winner_name': winner_name,
            'confidence': confidence,
            'improvement': improvement,
            'p_value': best_test['p_value'],
            'metric': best_test['metric'],
            'reason': f"Statistically significant improvement in {best_test['metric']}"
        }
    
    def _finalize_test(self, ab_test: ABTest, statistical_results: Dict[str, Any], winner_result: Dict[str, Any], stop_reason: str) -> Dict[str, Any]:
        """Finalize the A/B test and apply results"""
        
        try:
            # Update test status
            ab_test.status = 'completed'
            ab_test.completed_at = timezone.now()
            ab_test.statistical_significance = winner_result.get('confidence', 0.0)
            
            # Set winner if available
            if winner_result.get('winner') and winner_result['winner'] != 'Tie':
                # Find the winning creative
                winner_creative = self._find_winning_creative(ab_test, winner_result['winner_name'])
                if winner_creative:
                    ab_test.winner_creative = winner_creative
                    winner_creative.is_winner = True
                    winner_creative.save()
            
            ab_test.save()
            
            # Pause losing variants
            self._pause_losing_variants(ab_test, winner_result)
            
            return {
                'success': True,
                'status': 'completed',
                'winner': winner_result,
                'statistical_results': statistical_results,
                'stop_reason': stop_reason,
                'recommendations': self._generate_recommendations(ab_test, winner_result, statistical_results)
            }
            
        except Exception as e:
            logger.error(f"Failed to finalize A/B test {ab_test.id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _validate_test_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate A/B test configuration"""
        
        required_fields = ['test_type', 'variants']
        
        for field in required_fields:
            if field not in config:
                return {'valid': False, 'error': f'Missing required field: {field}'}
        
        if config['test_type'] not in ['headline', 'description', 'cta', 'creative']:
            return {'valid': False, 'error': 'Invalid test type'}
        
        if len(config['variants']) < 2:
            return {'valid': False, 'error': 'Need at least 2 variants for A/B test'}
        
        return {'valid': True}
    
    def _create_test_variants(self, ab_test: ABTest, variants: List[Dict[str, Any]]) -> List[AdCreative]:
        """Create ad creative variants for the test"""
        
        created_variants = []
        
        # Get the first ad set from the campaign to attach creatives
        ad_set = ab_test.campaign.adset_set.first()
        
        if not ad_set:
            raise ValueError("No ad set found for campaign")
        
        for i, variant in enumerate(variants):
            creative = AdCreative.objects.create(
                ad_set=ad_set,
                name=f"{ab_test.name} - Variant {i+1}",
                creative_type=variant.get('creative_type', 'text'),
                headline=variant.get('headline', 'Test Headline'),
                description=variant.get('description', 'Test Description'),
                call_to_action=variant.get('call_to_action', 'Learn More'),
                destination_url=variant.get('destination_url', 'https://example.com'),
                image_url=variant.get('image_url', ''),
                video_url=variant.get('video_url', ''),
                ai_confidence_score=variant.get('confidence_score', 0.8),
                is_active=True
            )
            created_variants.append(creative)
        
        return created_variants
    
    def _launch_test(self, ab_test: ABTest, variants: List[AdCreative], config: Dict[str, Any]) -> Dict[str, Any]:
        """Launch the A/B test on advertising platforms"""
        
        try:
            # In a real implementation, this would:
            # 1. Create the ad creatives on the advertising platforms
            # 2. Set up traffic splitting
            # 3. Start the campaigns
            
            # For now, we'll simulate a successful launch
            logger.info(f"Launching A/B test {ab_test.id} with {len(variants)} variants")
            
            return {
                'success': True,
                'variants_launched': len(variants),
                'traffic_split': config.get('traffic_split', 0.5),
                'platforms': ['google', 'meta', 'linkedin']  # Simulated
            }
            
        except Exception as e:
            logger.error(f"Failed to launch A/B test: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_variant_type(self, creative: AdCreative, test_type: str) -> str:
        """Determine variant type based on creative and test type"""
        
        # Simple implementation - in reality, you'd track this more systematically
        if 'Variant 1' in creative.name:
            return 'A'
        elif 'Variant 2' in creative.name:
            return 'B'
        elif 'Variant 3' in creative.name:
            return 'C'
        else:
            return 'A'  # Default
    
    def _find_winning_creative(self, ab_test: ABTest, winner_name: str) -> Optional[AdCreative]:
        """Find the creative corresponding to the winning variant"""
        
        # Simple implementation - find creative by name pattern
        creatives = AdCreative.objects.filter(
            ad_set__campaign=ab_test.campaign,
            created_at__gte=ab_test.started_at
        )
        
        for creative in creatives:
            variant_type = self._get_variant_type(creative, ab_test.test_type)
            if (winner_name == 'A' and variant_type == 'A') or \
               (winner_name == 'B' and variant_type == 'B') or \
               (winner_name == 'C' and variant_type == 'C'):
                return creative
        
        return None
    
    def _pause_losing_variants(self, ab_test: ABTest, winner_result: Dict[str, Any]):
        """Pause losing ad variants"""
        
        if not winner_result.get('winner') or winner_result['winner'] == 'Tie':
            return
        
        # Get all test creatives
        creatives = AdCreative.objects.filter(
            ad_set__campaign=ab_test.campaign,
            created_at__gte=ab_test.started_at
        )
        
        winner_name = winner_result['winner_name']
        
        for creative in creatives:
            variant_type = self._get_variant_type(creative, ab_test.test_type)
            
            # Pause non-winning variants
            if not ((winner_name == 'A' and variant_type == 'A') or \
                   (winner_name == 'B' and variant_type == 'B') or \
                   (winner_name == 'C' and variant_type == 'C')):
                creative.is_active = False
                creative.save()
    
    def _generate_recommendations(self, ab_test: ABTest, winner_result: Dict[str, Any], statistical_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results"""
        
        recommendations = []
        
        if winner_result.get('winner') and winner_result['winner'] != 'Tie':
            improvement = winner_result.get('improvement', 0)
            confidence = winner_result.get('confidence', 0)
            
            recommendations.append(
                f"Winner found with {improvement:.1f}% improvement at {confidence:.1%} confidence. "
                f"Scale the winning variant across all campaigns."
            )
            
            if improvement > 20:
                recommendations.append(
                    "Significant improvement detected. Consider testing similar variations "
                    "to further optimize performance."
                )
            
            recommendations.append(
                f"Apply learnings from {ab_test.test_type} test to future campaign creation."
            )
        else:
            recommendations.append(
                "No clear winner found. Consider testing more distinct variations "
                "or running the test longer with more traffic."
            )
        
        # Add specific recommendations based on test type
        if ab_test.test_type == 'headline':
            recommendations.append(
                "Test headline variations with different value propositions, "
                "emotional appeals, or urgency elements."
            )
        elif ab_test.test_type == 'cta':
            recommendations.append(
                "Continue testing different call-to-action phrases that match "
                "your campaign objective and audience intent."
            )
        
        return recommendations