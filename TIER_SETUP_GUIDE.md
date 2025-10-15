# 🎯 Tier System Setup Guide

## **✅ WHAT'S WORKING NOW:**
- ✅ Daily digest (top 20 listings at 9 AM UTC)
- ✅ Standard feed (5 best listings per hour)
- ✅ `!tier` command (check your tier)
- ✅ `!setbrands` command (set preferred brands)
- ✅ Tier system database and routing

## **🔧 STEP 1: Set Up Discord Channel Permissions**

### **Create Discord Roles:**
1. **Free Role** (default for everyone)
   - Color: Gray
   - Permissions: View #daily-digest only

2. **Standard Role** ($12/month)
   - Color: Green
   - Permissions: View #daily-digest + #standard-feed

3. **Instant Role** ($25/month)
   - Color: Red
   - Permissions: View all channels + brand channels

### **Set Up Channel Permissions:**

#### **#daily-digest Channel:**
- **Free Role:** ✅ View Channel, ✅ Read Message History
- **@everyone:** ❌ View Channel

#### **#standard-feed Channel:**
- **Standard Role:** ✅ View Channel, ✅ Read Message History
- **Instant Role:** ✅ View Channel, ✅ Read Message History
- **@everyone:** ❌ View Channel

#### **Premium Channels (#auction-alerts, #ending-soon, etc.):**
- **Instant Role:** ✅ View Channel, ✅ Read Message History
- **@everyone:** ❌ View Channel

#### **Brand Channels (#raf-simons, #rick-owens, etc.):**
- **Instant Role:** ✅ View Channel, ✅ Read Message History
- **@everyone:** ❌ View Channel

## **🔧 STEP 2: Set Up Payment Integration**

### **Option A: Stripe Integration (Recommended)**

1. **Create Stripe Account:**
   - Go to https://stripe.com
   - Create account and get API keys

2. **Add Environment Variables to Railway:**
   ```bash
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_STANDARD_PRICE_ID=price_...
   STRIPE_INSTANT_PRICE_ID=price_...
   ```

3. **Create Stripe Products:**
   - Standard Tier: $12/month recurring
   - Instant Tier: $25/month recurring

### **Option B: Whop.com Integration**

1. **Create Whop Account:**
   - Go to https://whop.com
   - Create your bot listing

2. **Set Up Webhook:**
   - Configure Whop webhook to send to your bot
   - Handle subscription events

## **🔧 STEP 3: Test the System**

### **Test Commands:**
- `!tier` - Should show Free tier
- `!setbrands` - Should show "only for Standard/Instant users"
- `!subscribe standard` - Should create checkout session (when Stripe is set up)
- `!subscribe instant` - Should create checkout session (when Stripe is set up)

### **Test Channel Access:**
- Free users: Can only see #daily-digest
- Standard users: Can see #daily-digest + #standard-feed
- Instant users: Can see all channels

## **🔧 STEP 4: Manual Role Assignment (For Testing)**

### **Admin Commands (Add to your bot):**

```python
@bot.command(name='givetier')
@commands.has_permissions(administrator=True)
async def givetier(ctx, user: discord.Member, tier: str):
    """Manually assign tier to user (admin only)"""
    if tier not in ['free', 'standard', 'instant']:
        await ctx.send("❌ Invalid tier. Use: free, standard, instant")
        return
    
    discord_id = str(user.id)
    await tier_manager_new.set_user_tier(discord_id, tier)
    
    # Assign Discord role
    guild = ctx.guild
    free_role = discord.utils.get(guild.roles, name='Free')
    standard_role = discord.utils.get(guild.roles, name='Standard')
    instant_role = discord.utils.get(guild.roles, name='Instant')
    
    # Remove existing roles
    if free_role and free_role in user.roles:
        await user.remove_roles(free_role)
    if standard_role and standard_role in user.roles:
        await user.remove_roles(standard_role)
    if instant_role and instant_role in user.roles:
        await user.remove_roles(instant_role)
    
    # Add new role
    if tier == 'free' and free_role:
        await user.add_roles(free_role)
    elif tier == 'standard' and standard_role:
        await user.add_roles(standard_role)
    elif tier == 'instant' and instant_role:
        await user.add_roles(instant_role)
    
    await ctx.send(f"✅ Assigned {tier} tier to {user.mention}")
```

## **🔧 STEP 5: Payment Processing Flow**

### **When User Pays:**

1. **Stripe/Whop sends webhook** to your bot
2. **Bot updates user tier** in database
3. **Bot assigns Discord role** automatically
4. **User gains access** to premium channels

### **Payment Integration Code:**

The payment integration is already built into your bot:
- `stripe_integration.py` - Handles Stripe payments
- `subscription_commands.py` - Discord subscription commands
- `stripe_webhook_handler.py` - Processes payment events

## **🎯 QUICK START CHECKLIST:**

### **Immediate (Today):**
- [ ] Create Discord roles (Free, Standard, Instant)
- [ ] Set channel permissions
- [ ] Test `!tier` and `!setbrands` commands
- [ ] Test channel access with different roles

### **This Week:**
- [ ] Set up Stripe account
- [ ] Add Stripe environment variables
- [ ] Test payment flow
- [ ] Test automatic role assignment

### **Before Launch:**
- [ ] Test all tier functionality
- [ ] Set up customer support
- [ ] Create pricing page
- [ ] Start marketing

## **💰 REVENUE PROJECTIONS:**

- **100 Standard users** = $1,200/month
- **50 Instant users** = $1,250/month
- **Total potential:** ~$2,450/month

## **🚨 IMPORTANT NOTES:**

1. **Channel Permissions:** Make sure channels are locked down properly
2. **Role Assignment:** Test automatic role assignment works
3. **Payment Security:** Use Stripe's webhook signature verification
4. **Customer Support:** Be ready to handle subscription issues

## **🎯 NEXT STEPS:**

1. **Set up Discord roles and permissions**
2. **Test tier commands and channel access**
3. **Set up Stripe integration**
4. **Test payment flow end-to-end**
5. **Launch and start making money!**

Your bot is 95% ready - just need to set up the permissions and payments! 🚀
