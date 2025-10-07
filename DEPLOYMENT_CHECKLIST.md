# 🚀 Tier System Deployment Checklist

## Files to Deploy

### ✅ New Files (Must be uploaded to Railway):
- [x] `tier_manager.py` - User tier and database management
- [x] `priority_calculator.py` - Listing priority scoring
- [x] `channel_router.py` - Channel routing logic
- [x] `digest_manager.py` - Daily digest functionality
- [x] `setup_channels.py` - Discord server setup script
- [x] `TIER_SYSTEM_README.md` - Documentation

### ✅ Modified Files:
- [x] `secure_discordbot.py` - Updated with tier system integration
- [x] `requirements.txt` - Added aiosqlite==0.19.0

---

## 📦 GitHub Deployment

### Option 1: Complete the Merge (Recommended)
```bash
cd /Users/lukevogrin/Discord-Auction-Bot/newfiles

# Check current status
git status

# Complete the merge
git merge --continue

# Push to GitHub
git push origin main
```

### Option 2: Force Push (Use with caution)
```bash
cd /Users/lukevogrin/Discord-Auction-Bot/newfiles

# Force push with safety check
git push origin main --force-with-lease
```

### Option 3: Reset and Re-commit
```bash
cd /Users/lukevogrin/Discord-Auction-Bot/newfiles

# Fetch latest
git fetch origin

# Reset to remote
git reset --hard origin/main

# Add all tier system files
git add tier_manager.py priority_calculator.py channel_router.py
git add digest_manager.py setup_channels.py TIER_SYSTEM_README.md
git add secure_discordbot.py requirements.txt

# Commit
git commit -m "Add 3-tier notification system with 22 brand channels"

# Push
git push origin main
```

---

## 🚂 Railway Deployment

### Step 1: Push to GitHub First
Railway automatically deploys from GitHub, so push all changes first.

### Step 2: Verify Railway Auto-Deploy
1. Go to your Railway dashboard: https://railway.app
2. Find your Discord bot project
3. Check the "Deployments" tab
4. Verify that a new deployment started after your GitHub push

### Step 3: Check Build Logs
1. Click on the latest deployment
2. Watch the build logs for any errors
3. Ensure `aiosqlite` installs correctly

### Step 4: Environment Variables
Verify these environment variables exist in Railway:
- `DISCORD_BOT_TOKEN` - Your Discord bot token
- `GUILD_ID` - Your Discord server ID
- `DATABASE_URL` - Your PostgreSQL database URL (if using)

**No new environment variables are required for the tier system!**

---

## 🎮 Discord Server Setup

### Step 1: Run Setup Script (Optional - only for #standard-feed)
```bash
python setup_channels.py
```
**OR** use the Discord command:
```
!setup
```

This will:
- Create roles: Free, Standard, Instant
- Create only `#standard-feed` channel
- Update permissions for existing channels
- Skip all existing brand/alert channels

### Step 2: Verify Channel Setup
Use Discord command:
```
!check_setup
```

This shows:
- Missing roles
- Missing channels
- Status of existing channels

---

## 🧪 Testing After Deployment

### 1. Verify Bot Starts
Check Railway logs for:
```
✅ Bot connected as [YourBotName]!
🎯 Tier system initialized
📊 Priority calculator initialized
🛣️ Channel router initialized
📰 Digest manager initialized
```

### 2. Test Webhook
Send a test listing from any scraper and verify it routes correctly.

### 3. Test Bot Commands
```
!tier                    # Check your tier (should show 'free' by default)
!settier @user standard  # Admin: Set a user to standard tier
!digest_stats            # Admin: Check digest statistics
!channel_stats           # Admin: Check channel routing stats
```

### 4. Test Tier System
1. Set yourself to standard tier: `!settier @you standard`
2. Set brand preferences: `!setbrands raf simons, rick owens`
3. Send test listings and verify they appear in `#standard-feed`
4. Verify counter works: `!tier` (should show count/100)

---

## 📊 Database Files

The tier system creates a new SQLite database:
- **File**: `user_tiers.db`
- **Location**: Railway persistent storage (automatically created)
- **Tables**: users, listing_queue, user_reactions
- **No manual setup required!**

---

## ⚠️ Important Notes

### Railway Persistent Storage
- Railway may reset file storage on redeploy
- The `user_tiers.db` file will be recreated automatically
- User tier data will persist in the database
- Daily counters reset at midnight UTC automatically

### Existing Channels
- The setup script will **NOT** recreate existing channels
- Only `#standard-feed` needs to be created
- All 22 brand channels are already recognized
- Permissions will be updated for existing channels

### No Breaking Changes
- Old webhook system remains as fallback
- Bot will work even if tier system fails to initialize
- Graceful degradation to old batch buffer system

---

## 🐛 Troubleshooting

### If Railway deployment fails:
1. Check build logs for Python errors
2. Verify `requirements.txt` has `aiosqlite==0.19.0`
3. Ensure all new files are in the repository

### If bot doesn't start:
1. Check for import errors in Railway logs
2. Verify all 4 new Python files are deployed
3. Check that `brands.json` exists

### If tier system doesn't work:
1. Check Railway logs for "Tier system initialized"
2. Verify database file is created: `user_tiers.db`
3. Try running `!tier` command to test

### If channels don't route correctly:
1. Run `!channel_stats` to check channel detection
2. Verify channel names match exactly (case-sensitive)
3. Check that roles exist: Free, Standard, Instant

---

## ✅ Success Criteria

- [ ] All files pushed to GitHub
- [ ] Railway deployment completed successfully
- [ ] Bot starts and shows tier system messages in logs
- [ ] `!tier` command works
- [ ] Webhooks route listings correctly
- [ ] Daily digest channel exists
- [ ] Standard feed channel exists (or created by script)
- [ ] All 22 brand channels recognized
- [ ] Roles created: Free, Standard, Instant

---

## 📞 Post-Deployment

After successful deployment:
1. Monitor Railway logs for first 10-15 minutes
2. Test webhook with a real listing
3. Verify listings appear in correct channels
4. Set user tiers as needed: `!settier @user instant`
5. Monitor daily digest at 9 AM UTC
6. Monitor counter resets at midnight UTC

---

## 🎉 You're Done!

The tier system is now live and ready to use. Users can:
- Join as Free tier (daily digest only)
- Subscribe to Standard ($12/mo) for 100 listings/day
- Subscribe to Instant ($25/mo) for unlimited real-time alerts

Admin commands are available to manage user tiers and monitor system performance.


