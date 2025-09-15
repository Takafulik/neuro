"""
Budget optimization engine for autonomous campaign management
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from django.db.models import Sum, Avg, Q
from django.utils import timezone
from ..models import Campaign, AdSet, CampaignAnalytics, BudgetOptimization

logger = logging.getLogger(__name__)


class BudgetOptimizer:
    """AI-powered budget optimization engine"""
    
    def __init__(self):
        self.min_budget_change_threshold = 0.05  # 5% minimum change
        self.max_budget_change_per_day = 0.20    # 20% maximum change per day
        self.performance_lookback_days = 7        # Days to analyze for performance
        self.confidence_threshold = 0.7          # Minimum confidence for changes
    
    def optimize_campaign_budgets(self, campaign: Campaign) -> Dict[str, Any]:
        """
        Optimize budget allocation across ad sets for a campaign
        
        Returns:
            Dict with optimization results and new budget allocations
        """
        try:
            # Get current performance data
            performance_data = self._get_performance_data(campaign)
            
            if not performance_data:
                return {'success': False, 'reason': 'Insufficient performance data'}
            
            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(performance_data)
            
            # Determine optimization opportunities
            opportunities = self._identify_optimization_opportunities(metrics)
            
            if not opportunities:
                return {'success': False, 'reason': 'No optimization opportunities found'}
            
            # Calculate new budget allocation
            new_allocation = self._calculate_optimal_allocation(campaign, metrics, opportunities)
            
            # Validate and apply budget changes
            if self._should_apply_changes(campaign, new_allocation):
                return self._apply_budget_optimization(campaign, new_allocation, opportunities)
            else:
                return {'success': False, 'reason': 'Budget changes below threshold or too risky'}
                
        except Exception as e:
            logger.error(f"Budget optimization failed for campaign {campaign.id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_performance_data(self, campaign: Campaign) -> List[Dict[str, Any]]:
        """Get recent performance data for campaign ad sets"""
        
        end_date = date.today()
        start_date = end_date - timedelta(days=self.performance_lookback_days)
        
        analytics = CampaignAnalytics.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        ).select_related('ad_set')
        
        performance_data = []
        
        for ad_set in campaign.adset_set.all():
            ad_set_analytics = analytics.filter(ad_set=ad_set)
            
            if ad_set_analytics.exists():
                # Aggregate metrics for this ad set
                totals = ad_set_analytics.aggregate(
                    total_impressions=Sum('impressions'),
                    total_clicks=Sum('clicks'),
                    total_conversions=Sum('conversions'),
                    total_spend=Sum('spend'),
                    total_revenue=Sum('revenue')
                )
                
                # Calculate derived metrics
                impressions = totals['total_impressions'] or 0
                clicks = totals['total_clicks'] or 0
                conversions = totals['total_conversions'] or 0
                spend = float(totals['total_spend'] or 0)
                revenue = float(totals['total_revenue'] or 0)
                
                ctr = (clicks / impressions * 100) if impressions > 0 else 0
                cpc = (spend / clicks) if clicks > 0 else 0
                cpa = (spend / conversions) if conversions > 0 else 0
                roas = (revenue / spend) if spend > 0 else 0
                conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0
                
                performance_data.append({
                    'ad_set': ad_set,
                    'impressions': impressions,
                    'clicks': clicks,
                    'conversions': conversions,
                    'spend': spend,
                    'revenue': revenue,
                    'ctr': ctr,
                    'cpc': cpc,
                    'cpa': cpa,
                    'roas': roas,
                    'conversion_rate': conversion_rate,
                    'allocated_budget': float(ad_set.allocated_budget),
                    'platform': ad_set.platform.name
                })
        
        return performance_data
    
    def _calculate_performance_metrics(self, performance_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance metrics and rankings"""
        
        if not performance_data:
            return {}
        
        # Calculate campaign totals
        campaign_totals = {
            'total_spend': sum(data['spend'] for data in performance_data),
            'total_revenue': sum(data['revenue'] for data in performance_data),
            'total_conversions': sum(data['conversions'] for data in performance_data),
            'total_clicks': sum(data['clicks'] for data in performance_data),
            'total_impressions': sum(data['impressions'] for data in performance_data)
        }
        
        # Calculate campaign averages
        campaign_averages = {
            'avg_ctr': campaign_totals['total_clicks'] / campaign_totals['total_impressions'] * 100 if campaign_totals['total_impressions'] > 0 else 0,
            'avg_cpc': campaign_totals['total_spend'] / campaign_totals['total_clicks'] if campaign_totals['total_clicks'] > 0 else 0,
            'avg_cpa': campaign_totals['total_spend'] / campaign_totals['total_conversions'] if campaign_totals['total_conversions'] > 0 else 0,
            'avg_roas': campaign_totals['total_revenue'] / campaign_totals['total_spend'] if campaign_totals['total_spend'] > 0 else 0,
            'avg_conversion_rate': campaign_totals['total_conversions'] / campaign_totals['total_clicks'] * 100 if campaign_totals['total_clicks'] > 0 else 0
        }
        
        # Score each ad set performance
        for data in performance_data:
            data['performance_score'] = self._calculate_performance_score(data, campaign_averages)
            data['efficiency_score'] = self._calculate_efficiency_score(data)
            data['spend_utilization'] = data['spend'] / data['allocated_budget'] if data['allocated_budget'] > 0 else 0
        
        # Rank ad sets by performance
        performance_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return {
            'ad_sets': performance_data,
            'campaign_totals': campaign_totals,
            'campaign_averages': campaign_averages
        }
    
    def _calculate_performance_score(self, ad_set_data: Dict[str, Any], campaign_averages: Dict[str, Any]) -> float:
        """Calculate a composite performance score for an ad set"""
        
        score = 0.0
        
        # ROAS contribution (40% weight)
        if campaign_averages['avg_roas'] > 0:
            roas_ratio = ad_set_data['roas'] / campaign_averages['avg_roas']
            score += min(roas_ratio, 2.0) * 0.4
        
        # Conversion rate contribution (25% weight)
        if campaign_averages['avg_conversion_rate'] > 0:
            conv_rate_ratio = ad_set_data['conversion_rate'] / campaign_averages['avg_conversion_rate']
            score += min(conv_rate_ratio, 2.0) * 0.25
        
        # CTR contribution (20% weight)
        if campaign_averages['avg_ctr'] > 0:
            ctr_ratio = ad_set_data['ctr'] / campaign_averages['avg_ctr']
            score += min(ctr_ratio, 2.0) * 0.2
        
        # CPA efficiency (15% weight) - lower is better
        if campaign_averages['avg_cpa'] > 0 and ad_set_data['cpa'] > 0:
            cpa_efficiency = campaign_averages['avg_cpa'] / ad_set_data['cpa']
            score += min(cpa_efficiency, 2.0) * 0.15
        
        return score
    
    def _calculate_efficiency_score(self, ad_set_data: Dict[str, Any]) -> float:
        """Calculate efficiency score based on spend utilization and performance"""
        
        utilization = ad_set_data['spend_utilization']
        roas = ad_set_data['roas']
        
        # Ideal utilization is between 80-95%
        if 0.8 <= utilization <= 0.95:
            utilization_score = 1.0
        elif utilization < 0.8:
            utilization_score = utilization / 0.8
        else:  # utilization > 0.95
            utilization_score = max(0.5, 1.0 - (utilization - 0.95) * 2)
        
        # ROAS score (normalized)
        roas_score = min(roas / 3.0, 1.0) if roas > 0 else 0
        
        return (utilization_score * 0.6) + (roas_score * 0.4)
    
    def _identify_optimization_opportunities(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify budget optimization opportunities"""
        
        opportunities = []
        ad_sets = metrics.get('ad_sets', [])
        
        if len(ad_sets) < 2:
            return opportunities
        
        # Find high performers that could use more budget
        high_performers = [ad_set for ad_set in ad_sets if ad_set['performance_score'] > 1.2 and ad_set['spend_utilization'] > 0.8]
        
        # Find low performers that should have budget reduced
        low_performers = [ad_set for ad_set in ad_sets if ad_set['performance_score'] < 0.8]
        
        # Find underutilized budget
        underutilized = [ad_set for ad_set in ad_sets if ad_set['spend_utilization'] < 0.6]
        
        for high_performer in high_performers:
            opportunities.append({
                'type': 'increase_budget',
                'ad_set': high_performer['ad_set'],
                'current_budget': high_performer['allocated_budget'],
                'reason': f"High performance score ({high_performer['performance_score']:.2f}) with high utilization",
                'confidence': min(high_performer['performance_score'] / 1.5, 1.0),
                'suggested_increase': min(0.2, high_performer['performance_score'] - 1.0)
            })
        
        for low_performer in low_performers:
            if low_performer['spend_utilization'] > 0.3:  # Only if actually spending
                opportunities.append({
                    'type': 'decrease_budget',
                    'ad_set': low_performer['ad_set'],
                    'current_budget': low_performer['allocated_budget'],
                    'reason': f"Low performance score ({low_performer['performance_score']:.2f})",
                    'confidence': min((1.0 - low_performer['performance_score']), 1.0),
                    'suggested_decrease': min(0.3, 1.0 - low_performer['performance_score'])
                })
        
        for underutil in underutilized:
            if underutil not in low_performers:  # Don't double-penalize
                opportunities.append({
                    'type': 'decrease_budget',
                    'ad_set': underutil['ad_set'],
                    'current_budget': underutil['allocated_budget'],
                    'reason': f"Low budget utilization ({underutil['spend_utilization']:.1%})",
                    'confidence': 1.0 - underutil['spend_utilization'],
                    'suggested_decrease': min(0.4, 1.0 - underutil['spend_utilization'])
                })
        
        # Filter opportunities by confidence threshold
        opportunities = [opp for opp in opportunities if opp['confidence'] >= self.confidence_threshold]
        
        return opportunities
    
    def _calculate_optimal_allocation(self, campaign: Campaign, metrics: Dict[str, Any], opportunities: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate new optimal budget allocation"""
        
        current_total_budget = float(campaign.total_budget)
        ad_sets = metrics['ad_sets']
        
        # Start with current allocation
        new_allocation = {ad_set['ad_set'].id: ad_set['allocated_budget'] for ad_set in ad_sets}
        
        # Calculate total budget to redistribute
        budget_to_redistribute = 0.0
        
        # First, calculate decreases
        for opportunity in opportunities:
            if opportunity['type'] == 'decrease_budget':
                ad_set_id = opportunity['ad_set'].id
                current_budget = new_allocation[ad_set_id]
                decrease_amount = current_budget * opportunity['suggested_decrease']
                
                # Apply limits
                decrease_amount = min(decrease_amount, current_budget * self.max_budget_change_per_day)
                
                new_allocation[ad_set_id] = current_budget - decrease_amount
                budget_to_redistribute += decrease_amount
        
        # Then, distribute increases proportionally to performance
        increase_opportunities = [opp for opp in opportunities if opp['type'] == 'increase_budget']
        
        if increase_opportunities and budget_to_redistribute > 0:
            total_performance_weight = sum(opp['confidence'] * opp['suggested_increase'] for opp in increase_opportunities)
            
            for opportunity in increase_opportunities:
                if total_performance_weight > 0:
                    weight = (opportunity['confidence'] * opportunity['suggested_increase']) / total_performance_weight
                    increase_amount = budget_to_redistribute * weight
                    
                    # Apply limits
                    ad_set_id = opportunity['ad_set'].id
                    current_budget = new_allocation[ad_set_id]
                    max_increase = current_budget * self.max_budget_change_per_day
                    increase_amount = min(increase_amount, max_increase)
                    
                    new_allocation[ad_set_id] = current_budget + increase_amount
        
        return new_allocation
    
    def _should_apply_changes(self, campaign: Campaign, new_allocation: Dict[str, float]) -> bool:
        """Determine if budget changes should be applied"""
        
        # Check if changes are significant enough
        total_change = 0.0
        total_budget = 0.0
        
        for ad_set in campaign.adset_set.all():
            current_budget = float(ad_set.allocated_budget)
            new_budget = new_allocation.get(ad_set.id, current_budget)
            
            change = abs(new_budget - current_budget)
            total_change += change
            total_budget += current_budget
        
        # Calculate percentage change
        if total_budget > 0:
            change_percentage = total_change / total_budget
            return change_percentage >= self.min_budget_change_threshold
        
        return False
    
    def _apply_budget_optimization(self, campaign: Campaign, new_allocation: Dict[str, float], opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply the budget optimization changes"""
        
        try:
            # Store previous allocation for history
            previous_allocation = {}
            changes_made = []
            
            for ad_set in campaign.adset_set.all():
                previous_allocation[ad_set.id] = float(ad_set.allocated_budget)
                new_budget = new_allocation.get(ad_set.id, previous_allocation[ad_set.id])
                
                if abs(new_budget - previous_allocation[ad_set.id]) >= previous_allocation[ad_set.id] * self.min_budget_change_threshold:
                    ad_set.allocated_budget = new_budget
                    ad_set.save()
                    
                    changes_made.append({
                        'ad_set': ad_set.name,
                        'platform': ad_set.platform.name,
                        'previous_budget': previous_allocation[ad_set.id],
                        'new_budget': new_budget,
                        'change_amount': new_budget - previous_allocation[ad_set.id],
                        'change_percentage': (new_budget - previous_allocation[ad_set.id]) / previous_allocation[ad_set.id] * 100
                    })
            
            # Calculate expected improvement
            expected_roas_improvement = self._calculate_expected_improvement(opportunities)
            
            # Create optimization record
            optimization_reason = self._generate_optimization_summary(opportunities)
            
            budget_optimization = BudgetOptimization.objects.create(
                campaign=campaign,
                previous_allocation=previous_allocation,
                new_allocation={ad_set_id: new_allocation.get(ad_set_id, previous_allocation[ad_set_id]) for ad_set_id in previous_allocation},
                optimization_reason=optimization_reason,
                performance_metrics=self._get_current_metrics_summary(campaign),
                expected_roas_improvement=expected_roas_improvement
            )
            
            return {
                'success': True,
                'optimization_id': budget_optimization.id,
                'changes_made': changes_made,
                'expected_improvement': expected_roas_improvement,
                'reason': optimization_reason,
                'opportunities_count': len(opportunities)
            }
            
        except Exception as e:
            logger.error(f"Failed to apply budget optimization: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_expected_improvement(self, opportunities: List[Dict[str, Any]]) -> float:
        """Calculate expected ROAS improvement from optimization"""
        
        improvement = 0.0
        
        for opportunity in opportunities:
            if opportunity['type'] == 'increase_budget':
                # Expect positive impact from increasing budget for high performers
                improvement += opportunity['confidence'] * 0.1  # 10% potential improvement
            elif opportunity['type'] == 'decrease_budget':
                # Expect savings from reducing budget for low performers
                improvement += opportunity['confidence'] * 0.05  # 5% potential improvement
        
        return min(improvement, 0.5)  # Cap at 50% expected improvement
    
    def _generate_optimization_summary(self, opportunities: List[Dict[str, Any]]) -> str:
        """Generate a summary of optimization decisions"""
        
        increases = len([opp for opp in opportunities if opp['type'] == 'increase_budget'])
        decreases = len([opp for opp in opportunities if opp['type'] == 'decrease_budget'])
        
        summary = f"Budget optimization applied: {increases} budget increases for high-performing ad sets, {decreases} budget decreases for underperforming ad sets."
        
        if opportunities:
            avg_confidence = sum(opp['confidence'] for opp in opportunities) / len(opportunities)
            summary += f" Average confidence: {avg_confidence:.1%}"
        
        return summary
    
    def _get_current_metrics_summary(self, campaign: Campaign) -> Dict[str, Any]:
        """Get current performance metrics summary for the campaign"""
        
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        analytics = CampaignAnalytics.objects.filter(
            campaign=campaign,
            date__gte=start_date,
            date__lte=end_date
        )
        
        totals = analytics.aggregate(
            total_spend=Sum('spend'),
            total_revenue=Sum('revenue'),
            total_conversions=Sum('conversions'),
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions')
        )
        
        return {
            'period': f"{start_date} to {end_date}",
            'total_spend': float(totals['total_spend'] or 0),
            'total_revenue': float(totals['total_revenue'] or 0),
            'total_conversions': totals['total_conversions'] or 0,
            'total_clicks': totals['total_clicks'] or 0,
            'total_impressions': totals['total_impressions'] or 0,
            'roas': float(totals['total_revenue'] or 0) / float(totals['total_spend'] or 1)
        }