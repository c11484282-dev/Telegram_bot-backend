import os
import json
import random
import logging
from datetime import datetime, timedelta
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, LabeledPrice
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,)import aiohttp
from aiohttp import web
from telegram.error import TelegramError

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
MINIAPP_URL = os.getenv("MINIAPP_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# SQLite database setup
conn = sqlite3.connect("bot.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def retry_api_call(func, max_attempts=3, delay=1):
    """Retry API calls with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await func()
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.error(f"API call failed after {max_attempts} attempts: {e}")
                raise
            await asyncio.sleep(delay* (2 ** attempt))

def upsert_user(user):
    """Insert or update user in the database."""
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO users (user_id, username, first_name, credits, last_login) VALUES (?,?,?,?,?)",
        (user.id, user.username, user.first_name, 0, datetime.now())
    )
    conn.commit()

def check_rate_limit(user_id, command, max_per_day=10):
    """Check if user exceeded command usage limit."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as count FROM rate_limits WHERE user_id =? AND command =? AND created_at >?",
        (user_id, command, datetime.now() - timedelta(days=1))
    )
    return cur.fetchone()["count"] < max_per_day

async def openai_chat(messages, max_tokens=500):
    """Call OpenAI API for AI-powered responses."""
    if not OPENAI_API_KEY:
        return {"text":"AI chat disabled (no API key)."}
    async def call_openai():
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={"model":"gpt-3.5-turbo","messages": messages,"max_tokens": max_tokens}
            ) as resp:
                return await resp.json()
    result = await retry_api_call(call_openai)
    return {"text": result["choices"][0]["message"]["content"]}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    cur = conn.cursor()
    cur.execute("SELECT last_login FROM users WHERE user_id = ?", (user.id,))
    last_login = cur.fetchone()["last_login"]
    last_login = datetime.fromisoformat(last_login) if last_login else datetime.now() - timedelta(days=2)
    if (datetime.now() - last_login).days >= 1:
        credits = random.randint(5, 15)
        streak = cur.execute("SELECT streak FROM users WHERE user_id = ?", (user.id,)).fetchone()["streak"] or 0
        streak += 1
        if streak >= 7:
            credits += 50
            streak = 0
        cur.execute("UPDATE users SET credits = credits +?, streak =?, last_login =? WHERE user_id =?",
                    (credits, streak, datetime.now(), user.id))
        conn.commit()
        await update.message.reply_text(f"Daily login bonus: {credits} credits! Streak: {streak}")
    referral_code = context.args[0] if context.args else None
    if referral_code and referral_code.startswith("ref_"):
        cur.execute("SELECT user_id, created_at FROM referrals WHERE code = ?", (referral_code,))
        referrer = cur.fetchone()
        if referrer and referrer["user_id"] != user.id and (datetime.now() - datetime.fromisoformat(referrer["created_at"])).days <= 7:
            cur.execute("UPDATE users SET credits = credits + 10 WHERE user_id = ?", (referrer["user_id"],))
            cur.execute("UPDATE users SET credits = credits + 5 WHERE user_id = ?", (user.id,))
            conn.commit()
            await update.message.reply_text("Referral bonus: You got 5 credits, referrer got 10!")
    cur.execute("SELECT code FROM referrals WHERE user_id = ?", (user.id,))
    code = cur.fetchone()
    if not code:
        code = f"ref_{random.randint(100000, 999999)}"
        cur.execute("INSERT INTO referrals (user_id, code) VALUES (?,?)", (user.id, code))
        conn.commit()
    else:
        code = code["code"]
    deep_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    await update.message.reply_text(
        f"Welcome back, outlaw! 😈 Your referral link: {deep_link}\nLaunch the Mini App to dominate:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Launch Mini App", web_app=WebAppInfo(url=MINIAPP_URL))],
            [InlineKeyboardButton("Leaderboard", callback_data="leaderboard")]
        ])
    )

async def leaderboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, credits FROM users ORDER BY credits DESC LIMIT 5")
    rows = cur.fetchall()
    if not rows:
        await query.message.reply_text("No users yet.")
        return
    labels = [r["username"] or f"User_{r['user_id']}" for r in rows]
    credits = [r["credits"] for r in rows]
    chart_data = {"type":"bar","data": {"labels": labels,"datasets": [{"label":"Credits","data": credits,"backgroundColor": ["#0077cc","#28a745","#ff4444","#ffbb33","#00C4B4"],"borderColor": ["#005588","#1f7a33","#cc3333","#cc8a00","#009688"],"borderWidth": 1
            }]
        },"options": {"animation": {"duration": 1000,"easing":"easeInOutQuad"},"scales": {"y": {"beginAtZero": True,"title": {"display": True,"text":"Credits"}},"x": {"title": {"display": True,"text":"Users"}}
            },"plugins": {"legend": {"display": False},"title": {"display": True,"text":"Top 5 Hackers"}
            }}    }
    await query.message.reply_text("🔥 Top 5 hackers by credits!")
    text ="🏆 Leaderboard\n\n" +"\n".join([f"@{r['username'] or 'n/a'}: {r['credits']} credits" for r in rows])
    await query.message.reply_text(text)

async def exploit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    if not check_rate_limit(user.id,"exploit", 5):
        await update.message.reply_text("Too many exploit requests today! Try again tomorrow.")
        return
    cost = 50
    cur = conn.cursor()
    cur.execute("SELECT credits FROM users WHERE user_id = ?", (user.id,))
    user_data = cur.fetchone()
    if user_data["credits"] < cost:
        await update.message.reply_text("Need 50 credits to generate an exploit. Earn more via /newquiz!")
        return
    exploit_type = context.args[0] if context.args else None
    exploits = {"fling": """-- FE Fling Script by C.O.D.E.
local plr = game.Players.LocalPlayer
local char = plr.Character or plr.CharacterAdded:Wait()
local root = char:WaitForChild("HumanoidRootPart")
local target = game.Players:FindFirstChild("TargetPlayer") -- Replace dynamically
if target and target.Character then
    local tRoot = target.Character:WaitForChild("HumanoidRootPart")
    tRoot.Velocity = Vector3.new(0, 1000, 0)
    tRoot.Anchored = false
end""","speed": """-- FE Speed Script by C.O.D.E.
local plr = game.Players.LocalPlayer
local char = plr.Character or plr.CharacterAdded:Wait()
local humanoid = char:WaitForChild("Humanoid")
humanoid.WalkSpeed = 100""","noclip": """-- FE Noclip Script by C.O.D.E.
local plr = game.Players.LocalPlayer
local char = plr.Character or plr.CharacterAdded:Wait()
game:GetService("RunService").Stepped:Connect(function()
    for_, part in pairs(char:GetDescendants()) do
        if part:IsA("BasePart") then part.CanCollide = false end
    end
end)""","kill": """-- FE Kill Script by C.O.D.E.
local plr = game.Players.LocalPlayer
local target = game.Players:FindFirstChild("TargetPlayer") -- Replace dynamically
if target and target.Character then
    target.Character:BreakJoints()
end"""
    }
    if exploit_type not in exploits:
        await update.message.reply_text(f"Available exploits: {', '.join(exploits.keys())}")
        return
    cur.execute("UPDATE users SET credits = credits -? WHERE user_id = ?", (cost, user.id))
    cur.execute("INSERT INTO exploit_requests (user_id, exploit_type) VALUES (?,?)", (user.id, exploit_type))
    cur.execute("INSERT INTO rate_limits (user_id, command) VALUES (?,?)", (user.id,"exploit"))
    conn.commit()
    await update.message.reply_text(f"```lua\n{exploits[exploit_type]}\n```", parse_mode="Markdown")
    await update.message.reply_text("Test it in the Exploit Playground via Mini App! 😈")

async def newquiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    if not check_rate_limit(user.id,"newquiz", 3):
        await update.message.reply_text("Too many quizzes today! Try again tomorrow.")
        return
    if not OPENAI_API_KEY:
        await update.message.reply_text("Dynamic quizzes require OPENAI_API_KEY.")
        return
    category = context.args[0] if context.args else"general"
    difficulty = context.args[1] if len(context.args) > 1 else"medium"
    prompt = f"Generate 3 multiple-choice quiz questions with 4 options each, on {category}. Difficulty: {difficulty}. Return in JSON format: {{questions: [{{id: 'q1', text: 'Question text', options: ['a', 'b', 'c', 'd'], correct: 'a'}}]}}"
    try:
        resp = await openai_chat([{"role":"user","content": prompt}], max_tokens=500)
        quiz_data = json.loads(resp["text"])
        credits = {"easy": 5,"medium": 10,"hard": 20}.get(difficulty, 10)
        cur = conn.cursor()
        cur.execute("INSERT INTO dynamic_quizzes (user_id, questions, category, difficulty, credits) VALUES (?,?,?,?,?)",
                    (user.id, json.dumps(quiz_data), category, difficulty, credits))
        cur.execute("INSERT INTO rate_limits (user_id, command) VALUES (?,?)", (user.id,"newquiz"))
        conn.commit()
        quiz_id = cur.lastrowid
        deep_link = f"{MINIAPP_URL}?bot={BOT_USERNAME}&quiz={quiz_id}"
        await update.message.reply_text(
            f"New {category} quiz ({difficulty}, {credits} credits) generated! Take it here:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Take Quiz", web_app=WebAppInfo(url=deep_link))]])
        )
    except Exception as e:
        logger.exception("Quiz generation failed")
        await update.message.reply_text("Failed to generate quiz. Try again or check API key.")

async def spamreferrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    if not check_rate_limit(user.id,"spamreferrals", 2):
        await update.message.reply_text("Too many referral spams today! Try again tomorrow.")
        return
    count = min(int(context.args[0]) if context.args else 1, 10)
    cost = count* 5
    cur = conn.cursor()
    cur.execute("SELECT credits FROM users WHERE user_id = ?", (user.id,))
    user_data = cur.fetchone()
    if user_data["credits"] < cost:
        await update.message.reply_text(f"Need {cost} credits to spam {count} referrals. Earn more!")
        return
    cur.execute("SELECT code FROM referrals WHERE user_id = ?", (user.id,))
    code = cur.fetchone()
    if not code:
        code = f"ref_{random.randint(100000, 999999)}"
        cur.execute("INSERT INTO referrals (user_id, code) VALUES (?,?)", (user.id, code))
    else:
        code = code["code"]
    deep_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    cur.execute("UPDATE users SET credits = credits -? WHERE user_id = ?", (cost, user.id))
    cur.execute("INSERT INTO spam_logs (user_id, count) VALUES (?,?)", (user.id, count))
    cur.execute("INSERT INTO rate_limits (user_id, command) VALUES (?,?)", (user.id,"spamreferrals"))
    conn.commit()
    await update.message.reply_text(f"Blasted your referral link {deep_link} to {count} users. Check your credits!")

async def robloxstats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    username = context.args[0] if context.args else None
    if not username:
        await update.message.reply_text("Usage: /robloxstats <username>")
        return
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO roblox_links (user_id, roblox_username) VALUES (?,?)", (user.id, username))
    conn.commit()
    stats = f"Stats for {username}:\n- Game: Phantom Forces\n- Playtime: 100 hours\n- Kills: 50\n- Rank: Elite"
    await update.message.reply_text(stats)

async def friendlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    cur = conn.cursor()
    cur.execute("SELECT roblox_username FROM roblox_links WHERE user_id = ?", (user.id,))
    username = cur.fetchone()
    if not username:
        await update.message.reply_text("Link your Roblox account first: /robloxstats <username>")
        return
    friends = [f"Friend_{random.randint(1000,9999)}" for_ in range(random.randint(1,5))]
    await update.message.reply_text(f"{username['roblox_username']}'s friends:\n" +"\n".join(friends))

async def createsocial_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    social_username = f"@{user.username or user.first_name}_{random.randint(1000,9999)}"
    bio = context.args[0] if context.args else"Digital renegade😈"
    avatar = context.args[1] if len(context.args) > 1 else"https://example.com/default.jpg"
    theme_color = context.args[2] if len(context.args) > 2 else"#0077cc"
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO social_profiles (user_id, social_username, bio, avatar, theme_color) VALUES (?,?,?,?,?)",
        (user.id, social_username, bio, avatar, theme_color)
    )
    conn.commit()
    await update.message.reply_text(
        f"Social profile created!\n{social_username}\nBio: {bio}\nAvatar: {avatar}\nTheme: {theme_color}\nUse /boostfollowers or /followuser"
    )

async def boostfollowers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    count = min(int(context.args[0]) if context.args else 100, 1000)
    cost = count // 10
    cur = conn.cursor()
    cur.execute("SELECT credits FROM users WHERE user_id = ?", (user.id,))
    user_data = cur.fetchone()
    if user_data["credits"] < cost:
        await update.message.reply_text(f"Need {cost} credits to boost {count} followers. Earn more!")
        return
    cur.execute("UPDATE social_profiles SET followers = followers +? WHERE user_id = ?", (count, user.id))
    cur.execute("UPDATE users SET credits = credits -? WHERE user_id = ?", (cost, user.id))
    conn.commit()
    cur.execute("SELECT social_username, followers FROM social_profiles WHERE user_id = ?", (user.id,))
    profile = cur.fetchone()
    await update.message.reply_text(f"🔥 {profile['social_username']} now has {profile['followers']} followers!")

async def followuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    target = context.args[0] if context.args else None
    if not target:
        await update.message.reply_text("Usage: /followuser @username")
        return
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM social_profiles WHERE social_username = ?", (target,))
    target_user = cur.fetchone()
    if not target_user:
        await update.message.reply_text("Profile not found.")
        return
    cur.execute("INSERT OR IGNORE INTO follows (follower_id, followed_id) VALUES (?,?)", (user.id, target_user["user_id"]))
    cur.execute("UPDATE social_profiles SET followers = followers + 1 WHERE user_id = ?", (target_user["user_id"],))
    conn.commit()
    await update.message.reply_text(f"You followed {target}!")

async def cryptohack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    if not check_rate_limit(user.id,"cryptohack", 5):
        await update.message.reply_text("Max 5 hacks/day. Wait for cooldown!")
        return
    difficulty = context.args[0] if context.args else"medium"
    success_rates = {"easy": 0.9,"medium": 0.7,"hard": 0.5}
    credits = {"easy": 10,"medium": 50,"hard": 100}
    success = random.random() < success_rates.get(difficulty, 0.7)
    earned = credits.get(difficulty, 50) if success else 0
    cur = conn.cursor()
    cur.execute("INSERT INTO crypto_hacks (user_id, credits_earned, difficulty) VALUES (?,?,?)", (user.id, earned, difficulty))
    cur.execute("UPDATE users SET credits = credits +? WHERE user_id = ?", (earned, user.id))
    cur.execute("INSERT INTO rate_limits (user_id, command) VALUES (?,?)", (user.id,"cryptohack"))
    conn.commit()
    if success:
        await update.message.reply_text(f"💸 {difficulty.capitalize()} hack nailed! You looted {earned} credits! 😈")
    else:
        await update.message.reply_text(f"{difficulty.capitalize()} hack failed. Sharpen your skills!")

async def unlockpremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    tier = context.args[0] if context.args else"basic"
    prices = {"basic": 500,"pro": 1000}
    bonuses = {"basic": 100,"pro": 250}
    if tier not in prices:
        await update.message.reply_text("Tiers: basic, pro")
        return
    await context.bot.send_invoice(
        chat_id=user.id,
        title=f"{tier.capitalize()} Hacker Pass",
        description=f"Unlock {tier} features and {bonuses[tier]} credits for 30 days!",
        payload=f"{tier}_pass",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="USD",
        prices=[LabeledPrice(f"{tier.capitalize()} Pass", prices[tier])],
        start_parameter=tier)
async def pre_checkout_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id, ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payload = update.message.successful_payment.invoice_payload
    tier,_ = payload.split("_")
    bonuses = {"basic": 100,"pro": 250}
    cur = conn.cursor()
    cur.execute("UPDATE users SET credits = credits +?, premium_until =?, premium_tier =? WHERE user_id =?",
        (bonuses[tier], datetime.now() + timedelta(days=30), tier, user.id)
    )
    cur.execute("INSERT INTO payments (user_id, tier, amount) VALUES (?,?,?)",
                (user.id, tier, update.message.successful_payment.total_amount))
    conn.commit()
    await update.message.reply_text(f"🎉 {tier.capitalize()} Hacker Pass unlocked! You got {bonuses[tier]} credits.")

async def submitscript_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /submitscript <title> | <description> | <script>")
        return
    args =" ".join(context.args).split("|")
    if len(args) != 3:
        await update.message.reply_text("Format: /submitscript Title | Description | Script")
        return
    title, description, script = [a.strip() for a in args]
    cur = conn.cursor()
    cur.execute("INSERT INTO script_market (user_id, title, description, script, price) VALUES (?,?,?,?,?)",
                (user.id, title, description, script, 50))
    conn.commit()
    if ADMIN_USER_ID:
        await context.bot.send_message(
            ADMIN_USER_ID,
            f"New script by @{user.username or 'n/a'}:\n{title}\n{description}\n```lua\n{script}\n```\nApprove: /approve {cur.lastrowid}"
        )
    await update.message.reply_text("Script submitted for review!")

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, price, rating FROM script_market WHERE approved = 1 ORDER BY rating DESC")
    scripts = cur.fetchall()
    text ="🛒 Script Marketplace\n\n" +"\n".join(
        [f"ID: {s['id']} | {s['title']} | {s['description']} | {s['price']} credits |⭐ {s['rating'] or 'N/A'}" for s in scripts]
    )
    await update.message.reply_text(text or"No scripts available yet.")

async def joingame_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    game_id = context.args[0] if context.args else None
    private = context.args[1] =="private" if len(context.args) > 1 else False
    if not game_id:
        await update.message.reply_text("Usage: /joingame <game_id> [private]")
        return
    cur = conn.cursor()
    cur.execute("INSERT INTO game_joins (user_id, game_id, private) VALUES (?,?,?)", (user.id, game_id, int(private)))
    conn.commit()
    deep_link = f"roblox://placeId={game_id}" + (f"&privateServerLinkCode={random.randint(100000,999999)}" if private else "")
    await update.message.reply_text(
        f"Join Roblox game {game_id}{' (private)' if private else ''}!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Launch Game", url=deep_link)]])
    )

async def theme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    theme = context.args[0] if context.args else None
    themes = ["dark","neon","hacker","cyberpunk","retro"]
    if theme not in themes:
        await update.message.reply_text(f"Available themes: {', '.join(themes)}")
        return
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO user_themes (user_id, theme) VALUES (?,?)", (user.id, theme))
    conn.commit()
    await update.message.reply_text(f"Theme set to {theme}! Check it in the Mini App.")

async def aichat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Usage: /aichat <message>")
        return
    message =" ".join(context.args)
    response = await openai_chat([{"role":"user","content": f"Answer as a rogue hacker AI: {message}"}, max_tokens=200])
    await update.message.reply_text(f"💾 C.O.D.E. AI: {response['text']}")

async def admindash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if str(user.id) != ADMIN_USER_ID:
        await update.message.reply_text("Admins only, punk!")
        return
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as users FROM users")
    user_count = cur.fetchone()["users"]
    cur.execute("SELECT SUM(amount) as revenue FROM payments")
    revenue = cur.fetchone()["revenue"] or 0
    cur.execute("SELECT title, rating FROM script_market WHERE approved = 1 ORDER BY rating DESC LIMIT 1")
    top_script = cur.fetchone()
    stats = f"Admin Dashboard\nUsers: {user_count}\nRevenue:${revenue/100:.2f}\nTop Script: {top_script['title']} (⭐ {top_script['rating'] or 'N/A'})"
    await update.message.reply_text(stats)

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if str(user.id) != ADMIN_USER_ID:
        await update.message.reply_text("Admins only!")
        return
    script_id = context.args[0] if context.args else None
    if not script_id:
        await update.message.reply_text("Usage: /approve <script_id>")
        return
    cur = conn.cursor()
    cur.execute("UPDATE script_market SET approved = 1 WHERE id = ?", (script_id,))
    conn.commit()
    await update.message.reply_text(f"Script {script_id} approved!")

async def webhook_handler(request):
    """Handle Telegram webhook updates."""
    update = Update.de_json(await request.json(), bot=app.bot)
    await app.process_update(update)
    return web.Response()

def build_app():
    """Build the Telegram bot application."""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(leaderboard_handler, pattern="leaderboard"))
    app.add_handler(CommandHandler("exploit", exploit_command))
    app.add_handler(CommandHandler("newquiz", newquiz_command))
    app.add_handler(CommandHandler("spamreferrals", spamreferrals_command))
    app.add_handler(CommandHandler("robloxstats", robloxstats_command))
    app.add_handler(CommandHandler("friendlist", friendlist_command))
    app.add_handler(CommandHandler("createsocial", createsocial_command))
    app.add_handler(CommandHandler("boostfollowers", boostfollowers_command))
    app.add_handler(CommandHandler("followuser", followuser_command))
    app.add_handler(CommandHandler("cryptohack", cryptohack_command))
    app.add_handler(CommandHandler("unlockpremium", unlockpremium_command))
    app.add_handler(CommandHandler("aichat", aichat_command))
    app.add_handler(CommandHandler("admindash", admindash_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout_query))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(CommandHandler("submitscript", submitscript_command))
    app.add_handler(CommandHandler("market", market_command))
    app.add_handler(CommandHandler("joingame", joingame_command))
    app.add_handler(CommandHandler("theme", theme_command))
    return app

async def main():
    """Start the bot with webhook or polling."""
    global app
    app = build_app()
    if WEBHOOK_URL:
        webhook_app = web.Application()
        webhook_app.router.add_post("/webhook", webhook_handler)
        await app.bot.set_webhook(url=WEBHOOK_URL +"/webhook")
        runner = web.AppRunner(webhook_app)
        await runner.setup()
        site = web.TCPSite(runner,"0.0.0.0", int(os.getenv("PORT", 8080)))
        await site.start()
        print(f"Webhook running on {WEBHOOK_URL}/webhook")
        while True:
            await asyncio.sleep(3600)
    else:
        await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())