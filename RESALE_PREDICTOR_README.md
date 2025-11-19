# 💰 Resale Value Predictor - AI-Powered Feature

## Overview
The Resale Value Predictor is an AI-powered feature that analyzes Yahoo Japan auction listings and estimates their US resale value using the Anthropic Claude API. It helps users make informed purchasing decisions by predicting potential profit margins on platforms like Grailed, eBay, StockX, and Vestiaire Collective.

## Features

### 🤖 AI-Powered Analysis
- Uses Claude Sonnet 4.5 for sophisticated market analysis
- Analyzes brand reputation, item condition, rarity, and market trends
- Considers seasonal factors and current demand in US market

### 💵 Comprehensive Pricing Estimates
- **Price Range**: Low/High/Average resale estimates
- **Confidence Score**: High/Medium/Low based on data quality
- **Profit Calculations**: Gross and net profit after all costs

### 💸 Cost Breakdown
The predictor accounts for:
- **Shipping**: ~$40 from Japan to US
- **Platform Fees**: 10% (Grailed, eBay, etc.)
- **Proxy Service Fees**: 10% (Buyee, Zenmarket, etc.)

### 🎯 Smart Recommendations
- **🔥 STRONG BUY**: 50%+ net profit margin
- **✅ GOOD DEAL**: 20-50% net margin
- **⚠️ MARGINAL**: 0-20% net margin
- **❌ PASS**: Negative margin (likely unprofitable)

## Discord Commands

### `!resale <auction_id>`
Analyze a specific listing's resale value.

**Example:**
```
!resale yahoo_x1234567890
```

**Response Time:** ~10 seconds (AI processing)

**Output:**
- Purchase price (Yahoo Japan)
- Estimated US resale value range
- Net profit and margin calculations
- AI reasoning and market analysis
- Buy/Pass recommendation
- Detailed cost breakdown

### `!resale_help`
Display guide on how to use the resale predictor.

Shows:
- Command usage
- What the AI analyzes
- How to interpret results
- Confidence level meanings
- Cost assumptions

## Setup Instructions

### 1. Get Anthropic API Key
1. Visit: https://console.anthropic.com/settings/keys
2. Create a new API key
3. Copy the key (starts with `sk-ant-...`)

### 2. Add Environment Variable
Add to your Railway environment variables:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Deploy
The bot will automatically initialize the resale predictor on startup if the API key is present.

**Startup Messages:**
```
✅ Resale value predictor module imported successfully
💰 Resale value predictor initialized
```

If API key is missing:
```
⚠️ Resale predictor not available: No API key
⚠️ Resale predictor not initialized
```

## Implementation Details

### Files Modified
1. **`resale_predictor.py`** (NEW)
   - Main predictor class
   - Claude API integration
   - Profit calculation logic

2. **`secure_discordbot.py`** (MODIFIED)
   - Added import and initialization
   - Added `!resale` command
   - Added `!resale_help` command
   - Added `create_resale_embed()` helper

3. **`requirements.txt`** (MODIFIED)
   - Added `anthropic==0.39.0`

### Architecture

```
User runs: !resale yahoo_x1234567890
    ↓
Discord Bot (secure_discordbot.py)
    ↓
Query database for listing details
    ↓
ResaleValuePredictor.predict_resale_value()
    ↓
Build analysis prompt for Claude
    ↓
Claude API analyzes listing
    ↓
Parse JSON response
    ↓
Calculate profit metrics (gross/net)
    ↓
Create Discord embed with results
    ↓
Send to user
```

### Database Integration
The predictor queries the `listings` table for:
- `auction_id` (primary identifier)
- `title` (item description)
- `brand` (brand name)
- `price_usd` (purchase price in USD)
- `price_jpy` (purchase price in JPY)

## Cost Estimates

### Claude API Pricing
- **Model**: Claude Sonnet 4.5
- **Cost**: ~$0.01 per analysis
- **1000 analyses**: ~$10

### Budget Planning
- **10 analyses/day**: ~$3/month
- **100 analyses/day**: ~$30/month
- **Very affordable** for premium features

## Error Handling

### Graceful Degradation
If Claude API is unavailable:
1. Falls back to conservative 30% markup estimate
2. Marks confidence as "low"
3. Adds warning: "API unavailable - using conservative estimate"
4. Recommends manual verification

### User-Friendly Errors
- Invalid auction ID: "❌ Listing not found: `<id>`"
- Missing API key: "❌ Resale predictor not available"
- API errors: Uses fallback estimate

## Example Output

### Successful Analysis
```
💰 Resale Value Analysis
Rick Owens DRKSHDW Leather Jacket Size 50

📦 Purchase Details
Brand: Rick Owens
Yahoo Price: $300.50 USD

💵 Estimated US Resale
Range: $400 - $500
Average: $450
Confidence: HIGH

📊 Profit Analysis
Net Profit: $79.50
Margin: 26.5%
Est. Costs: $70.00

🤔 AI Analysis
Rick Owens DRKSHDW leather jackets are highly sought after in the US market.
Size 50 is popular and condition appears good. Strong demand on Grailed.

📈 Market Notes
High-end brand with consistent resale value. Leather pieces especially popular.
Winter seasonality may increase demand.

🎯 Recommendation
✅ GOOD DEAL - Solid profit margin

💸 Cost Breakdown
Shipping: $40.00
Platform Fees: $45.00
Proxy Fee: $30.05

Powered by Claude AI • Confidence: high • ID: yahoo_x1234567890
```

## Testing Checklist

After deployment:
- [ ] Verify ANTHROPIC_API_KEY is set in Railway
- [ ] Check bot startup logs for "✅ Resale value predictor initialized"
- [ ] Test `!resale_help` command
- [ ] Test `!resale` with a valid auction ID
- [ ] Test `!resale` with an invalid auction ID
- [ ] Verify embed formatting looks correct
- [ ] Check Claude API responses are parsed correctly
- [ ] Verify profit calculations are accurate
- [ ] Test with different brands (high-end, mid-range, unknown)
- [ ] Monitor API costs in Anthropic console

## Future Enhancements

### Potential Additions
1. **Caching**: Store predictions in database to avoid re-analyzing
2. **Batch Analysis**: `!resale_batch` for multiple listings
3. **Historical Data**: Track prediction accuracy over time
4. **Auto-Prediction**: Automatically add resale estimates to new listings
5. **Size-Specific Analysis**: Better predictions for specific sizes
6. **Condition Tracking**: More accurate based on item condition
7. **Rate Limiting**: Prevent abuse (e.g., 10 free analyses/day)
8. **Premium Feature**: Unlimited analyses for Instant tier users

### Auto-Embed in Listings (Optional)
To automatically show resale estimates in listing posts, modify `create_enhanced_listing_embed()`:

```python
# Optional: Add resale estimate if available
if listing_data.get('resale_estimate'):
    prediction = listing_data['resale_estimate']
    estimated_avg = prediction.get('estimated_avg', 0)
    profit_margin = prediction.get('net_margin', 0)

    if profit_margin > 20:
        embed.add_field(
            name="💰 Resale Opportunity",
            value=f"Est. US Value: ${estimated_avg:.0f} ({profit_margin:.0f}% profit)",
            inline=False
        )
```

## Troubleshooting

### "Resale predictor not available"
**Cause**: ANTHROPIC_API_KEY not set or invalid
**Fix**: Add API key to Railway environment variables

### "API unavailable - using conservative estimate"
**Cause**: Claude API request failed
**Fix**: Check API key validity and Anthropic service status

### "Listing not found"
**Cause**: Auction ID doesn't exist in database
**Fix**: Use exact auction ID from listing footer

### Slow responses
**Cause**: Claude API takes 5-10 seconds to analyze
**Fix**: This is normal - warn users to wait

## Support

For issues or questions:
- Check Railway logs for error messages
- Verify API key is set correctly
- Test with `!resale_help` first
- Ensure listing exists in database

## License

Part of Yahoo Japan Scraper Discord Bot
Uses Anthropic Claude API (requires separate API key)
