import anthropic
import os
import json
import re
from typing import Dict, Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)

class ResaleValuePredictor:
    """
    AI-powered resale value predictor using Anthropic Claude API.
    Analyzes Yahoo Japan auction listings and estimates US resale prices.
    """

    def __init__(self):
        """Initialize the predictor with Claude API client"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("⚠️ ANTHROPIC_API_KEY not found - resale predictor will use fallback estimates")
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info("✅ Claude API client initialized")

        self.model = "claude-sonnet-4-20250514"

    async def predict_resale_value(self, listing_data: Dict) -> Dict:
        """
        Predict US resale value for a Yahoo Japan auction listing

        Args:
            listing_data: Dictionary containing listing information

        Returns:
            Dictionary with prediction results:
            {
                'estimated_low': 400,
                'estimated_high': 500,
                'estimated_avg': 450,
                'confidence': 'high',  # high/medium/low
                'profit_margin': 50,  # percentage
                'reasoning': 'Rick Owens leather jackets in good condition...',
                'market_notes': 'High demand item, size 50 is popular...'
            }
        """

        # Extract data
        title = listing_data.get('title', '')
        brand = listing_data.get('brand', 'Unknown')
        price_usd = listing_data.get('price_usd', 0)
        price_jpy = listing_data.get('price_jpy', 0)
        condition = listing_data.get('condition', 'Used')
        sizes = listing_data.get('sizes', [])

        logger.info(f"🤔 Analyzing resale value for: {title[:50]}... (${price_usd})")

        # If API is not available, use fallback
        if not self.client:
            logger.warning("⚠️ Claude API not available, using fallback estimate")
            return self._get_fallback_estimate(price_usd)

        # Build prompt for Claude
        prompt = self._build_analysis_prompt(
            title=title,
            brand=brand,
            price_usd=price_usd,
            price_jpy=price_jpy,
            condition=condition,
            sizes=sizes
        )

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response
            result = self._parse_claude_response(response.content[0].text)

            # Add original purchase price for profit calc
            result['purchase_price_usd'] = price_usd

            logger.info(f"✅ Prediction complete: ${result['estimated_avg']:.0f} (confidence: {result['confidence']})")

            return result

        except Exception as e:
            logger.error(f"❌ Resale prediction error: {e}")
            return self._get_fallback_estimate(price_usd)

    def _build_analysis_prompt(self, title: str, brand: str, price_usd: float,
                               price_jpy: float, condition: str, sizes: list) -> str:
        """Build the prompt for Claude to analyze resale value"""

        sizes_str = ', '.join(sizes) if sizes else 'Not specified'

        prompt = f"""You are a fashion resale expert specializing in high-end Japanese and designer fashion.
Analyze this Yahoo Japan auction listing and estimate its US resale value.

LISTING DETAILS:
- Title: {title}
- Brand: {brand}
- Yahoo Japan Price: ${price_usd:.2f} USD (¥{price_jpy:,} JPY)
- Condition: {condition}
- Sizes: {sizes_str}

TASK:
Estimate the realistic resale price range for this item on US platforms (Grailed, eBay, StockX, Vestiaire Collective).

Consider:
1. Brand reputation and demand in US market
2. Item type and seasonality
3. Condition and size availability
4. Current market trends for this brand
5. Rarity and desirability
6. Typical markup from Japanese to US market
7. Popular brands include: Rick Owens, Raf Simons, Comme des Garcons, Yohji Yamamoto, Issey Miyake, Number (N)ine, undercover, visvim, etc.

IMPORTANT GUIDELINES:
- Be realistic - not everything is profitable
- If item seems overpriced or low-demand, estimated values can be BELOW purchase price
- Confidence should be "low" if insufficient info or unpopular item
- Consider shipping costs (~$30-50 from Japan) and proxy fees (~10%) are NOT included in your estimates
- Focus on actual market value, not wishful thinking

RESPOND IN THIS EXACT JSON FORMAT (no other text, no markdown):
{{
    "estimated_low": <number>,
    "estimated_high": <number>,
    "estimated_avg": <number>,
    "confidence": "<high/medium/low>",
    "reasoning": "<2-3 sentence explanation>",
    "market_notes": "<key factors affecting price>"
}}
"""
        return prompt

    def _parse_claude_response(self, response_text: str) -> Dict:
        """Parse Claude's JSON response"""

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)

                # Validate required fields
                required_fields = ['estimated_low', 'estimated_high', 'estimated_avg', 'confidence', 'reasoning']
                for field in required_fields:
                    if field not in data:
                        logger.warning(f"⚠️ Missing field in Claude response: {field}")
                        return self._get_fallback_estimate(0)

                # Add placeholders for profit calculations (will be updated later)
                data['profit_margin'] = 0
                data['profit_usd'] = 0

                return data
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.error(f"❌ Failed to parse Claude response: {e}")
            logger.error(f"Response was: {response_text}")
            return self._get_fallback_estimate(0)

    def _get_fallback_estimate(self, purchase_price: float) -> Dict:
        """Return conservative fallback estimate if API fails"""
        # Conservative 30% markup estimate
        estimated_avg = purchase_price * 1.3

        return {
            'estimated_low': purchase_price * 1.1,
            'estimated_high': purchase_price * 1.5,
            'estimated_avg': estimated_avg,
            'confidence': 'low',
            'profit_margin': 30,
            'profit_usd': purchase_price * 0.3,
            'reasoning': 'API unavailable - using conservative 30% markup estimate',
            'market_notes': 'Manual verification strongly recommended. Estimate based on typical Japanese to US markup.',
            'purchase_price_usd': purchase_price
        }

    def calculate_profit_metrics(self, prediction: Dict) -> Dict:
        """
        Calculate detailed profit metrics including costs

        Args:
            prediction: Dictionary from predict_resale_value()

        Returns:
            Updated dictionary with profit calculations
        """
        purchase_price = prediction.get('purchase_price_usd', 0)
        estimated_avg = prediction.get('estimated_avg', 0)

        # Calculate gross profit
        gross_profit = estimated_avg - purchase_price
        profit_margin_pct = (gross_profit / purchase_price * 100) if purchase_price > 0 else 0

        # Account for costs
        shipping_cost = 40  # Average Japan to US shipping via proxy
        platform_fees = estimated_avg * 0.10  # 10% platform fees (Grailed, eBay, etc.)
        proxy_fee = purchase_price * 0.10  # 10% proxy service fee

        total_costs = shipping_cost + platform_fees + proxy_fee

        # Calculate net profit (after all costs)
        net_profit = gross_profit - total_costs
        net_margin_pct = (net_profit / purchase_price * 100) if purchase_price > 0 else 0

        # Update prediction dictionary
        prediction['profit_usd'] = round(gross_profit, 2)
        prediction['profit_margin'] = round(profit_margin_pct, 1)
        prediction['net_profit_usd'] = round(net_profit, 2)
        prediction['net_margin'] = round(net_margin_pct, 1)
        prediction['estimated_costs'] = round(total_costs, 2)
        prediction['cost_breakdown'] = {
            'shipping': shipping_cost,
            'platform_fees': round(platform_fees, 2),
            'proxy_fee': round(proxy_fee, 2)
        }

        return prediction

    def get_recommendation(self, prediction: Dict) -> tuple:
        """
        Get buy recommendation based on profit margin

        Args:
            prediction: Dictionary with profit calculations

        Returns:
            Tuple of (emoji, recommendation_text, color_hex)
        """
        net_margin = prediction.get('net_margin', 0)
        confidence = prediction.get('confidence', 'low')

        if net_margin > 50:
            return ("🔥", "STRONG BUY - High profit potential", 0x00ff00)
        elif net_margin > 20:
            return ("✅", "GOOD DEAL - Solid profit margin", 0xffd700)
        elif net_margin > 0:
            return ("⚠️", "MARGINAL - Small profit, higher risk", 0xff9900)
        else:
            return ("❌", "PASS - Likely unprofitable", 0xff0000)
