from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import telebot
import os
from dotenv import load_dotenv
import requests
import json
import random
import time
from datetime import datetime, timedelta
import logging
import sqlite3

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MINIAPP_URL = os.getenv("MINIAPP_URL")

# Initialize FastAPI and Telebot
app = FastAPI()
bot = telebot.TeleBot(BOT_TOKEN)

# SQLite connection
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

# Available quiz topics
QUIZ_TOPICS = ["roblox","minecraft","python","hacking","general knowledge"]

# Set webhook
try:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook set to {WEBHOOK_URL}")
except Exception as e:
    logger.error(f"Error setting webhook: {e}")

# Helper function to call OpenAI for quiz generation
async def generate_quiz(topic, difficulty):
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"}
        payload = {"model":"gpt-4o-mini","messages": [
                {"role":"user","content": f"Generate a {difficulty} quiz question about {topic} with 4 answer options and the correct answer."}
            ]}        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        return f"Error generating quiz: {str(e)}"

# Helper function to check rate limit
def check_rate_limit(user_id, command):
    cur.execute("SELECT COUNT(*) FROM rate_limits WHERE user_id =? AND command =? AND created_at > ?", 
                (user_id, command, (datetime.now() - timedelta(hours=1)).isoformat()))
    count = cur.fetchone()[0]
    if count >= 5:
        return False,"Rate limit exceeded. Try again in an hour."
    cur.execute("INSERT INTO rate_limits (user_id, command, created_at) VALUES (?,?,?)", 
                (user_id, command, datetime.now().isoformat()))
    conn.commit()
    return True, ""

# Helper function to register user
def register_user(user):
    cur.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, credits, last_login) VALUES (?,?,?,?,?)",
                (user.id, user.username or"Unknown", user.first_name, 0, datetime.now().isoformat()))
    conn.commit()

# Handle /start command
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    register_user(user)
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    webapp_button = telebot.types.KeyboardButton("Open Mini App", web_app=telebot.types.WebAppInfo(url=MINIAPP_URL))
    keyboard.add(webapp_button)
    bot.reply_to(message, f"Welcome, {user.username}! Click below to open the Mini App or use /help for commands.", reply_markup=keyboard)
    logger.info(f"User {user.id} started bot")

# Handle /newquiz command
@bot.message_handler(commands=['newquiz'])
def handle_newquiz(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    can_proceed, error_msg = check_rate_limit(user_id,"newquiz")
    if not can_proceed:
        bot.reply_to(message, error_msg)
        return
    args = message.text.split()[1:]
    topic = args[0].lower() if len(args) > 0 else"roblox"
    difficulty = args[1].lower() if len(args) > 1 else"hard"
    if topic not in QUIZ_TOPICS:
        bot.reply_to(message, f"Invalid topic. Use /categories to see available topics.")
        return
    quiz = generate_quiz(topic, difficulty)
    cur.execute("INSERT INTO dynamic_quizzes (user_id, questions, category, difficulty, credits, created_at) VALUES (?,?,?,?,?,?)",
                (user_id, quiz, topic, difficulty, 10, datetime.now().isoformat()))
    cur.execute("UPDATE users SET credits = credits + 10 WHERE user_id = ?", (user_id,))
    conn.commit()
    bot.reply_to(message, f"Quiz: {quiz}\nEarned 10 credits!")
    logger.info(f"User {user_id} requested quiz: {topic}, {difficulty}")

# Handle /profile command
@bot.message_handler(commands=['profile'])
def handle_profile(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    cur.execute("SELECT username, credits, streak, premium_tier FROM users WHERE user_id = ?", (user_id,))
    user_data = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM dynamic_quizzes WHERE user_id = ?", (user_id,))
    quiz_count = cur.fetchone()[0]
    cur.execute("SELECT name FROM achievements WHERE user_id = ?", (user_id,))
    achievements = [row[0] for row in cur.fetchall()]
    response = (
        f"👤 Profile: {user_data[0]}\n"
        f"🆔 Telegram ID: {user_id}\n"
        f"💰 Credits: {user_data[1]}\n"
        f"🔥 Streak: {user_data[2]}\n"
        f"🏆 Quizzes Completed: {quiz_count}\n"
        f"🎖 Achievements: {', '.join(achievements) or 'None'}\n"
        f"🌟 Premium: {user_data[3] or 'None'}"
    )
    bot.reply_to(message, response)
    logger.info(f"User {user_id} accessed /profile")

# Handle /dailyquiz command
@bot.message_handler(commands=['dailyquiz'])
def handle_dailyquiz(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    cur.execute("SELECT created_at FROM dynamic_quizzes WHERE user_id =? AND category = 'daily' ORDER BY created_at DESC LIMIT 1", (user_id,))
    last_quiz = cur.fetchone()
    if last_quiz and datetime.fromisoformat(last_quiz[0]).date() == datetime.now().date():
        bot.reply_to(message,"You've already taken today's daily quiz! Try again tomorrow.")
        return
    topic = random.choice(QUIZ_TOPICS)
    difficulty = random.choice(["easy","medium","hard"])
    quiz = generate_quiz(topic, difficulty)
    cur.execute("INSERT INTO dynamic_quizzes (user_id, questions, category, difficulty, credits, created_at) VALUES (?,?,?,?,?,?)",
                (user_id, quiz,"daily", difficulty, 20, datetime.now().isoformat()))
    cur.execute("UPDATE users SET credits = credits + 20, streak = streak + 1 WHERE user_id = ?", (user_id,))
    if cur.execute("SELECT streak FROM users WHERE user_id = ?", (user_id,)).fetchone()[0] >= 5:
        cur.execute("INSERT INTO achievements (user_id, name, credits, created_at) VALUES (?,?,?,?)",
                    (user_id,"Quiz Streaker", 50, datetime.now().isoformat()))
        cur.execute("UPDATE users SET credits = credits + 50 WHERE user_id = ?", (user_id,))
    conn.commit()
    bot.reply_to(message, f"📅 Daily Quiz ({topic}, {difficulty}): {quiz}\nEarned 20 credits!")
    logger.info(f"User {user_id} accessed /dailyquiz")

# Handle /scriptmarket command
@bot.message_handler(commands=['scriptmarket'])
def handle_scriptmarket(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    cur.execute("SELECT id, title, description, price FROM script_market WHERE approved = 1 LIMIT 5")
    scripts = cur.fetchall()
    response ="📜 Script Market (Top 5):\n"
    for script in scripts:
        response += f"ID: {script[0]} | {script[1]} - {script[2][:50]}... | Price: {script[3]} credits\n"
    response +="Use /buy_script <id> to purchase."
    bot.reply_to(message, response)
    logger.info(f"User {user_id} accessed /scriptmarket")

# Handle /buy_script command
@bot.message_handler(commands=['buy_script'])
def handle_buy_script(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    args = message.text.split()[1:]
    if not args:
        bot.reply_to(message,"Usage: /buy_script <script_id>")
        return
    script_id = args[0]
    cur.execute("SELECT price, script FROM script_market WHERE id =? AND approved = 1", (script_id,))
    script = cur.fetchone()
    if not script:
        bot.reply_to(message,"Invalid script ID or not approved.")
        return
    cur.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    user_credits = cur.fetchone()[0]
    if user_credits < script[0]:
        bot.reply_to(message,"Not enough credits!")
        return
    cur.execute("UPDATE users SET credits = credits -? WHERE user_id = ?", (script[0], user_id))
    conn.commit()
    bot.reply_to(message, f"Purchased script:\n```{script[1]}```")
    logger.info(f"User {user_id} purchased script {script_id}")

# Handle /setbio command
@bot.message_handler(commands=['setbio'])
def handle_setbio(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    args = message.text.split(maxsplit=1)[1:]
    if not args:
        bot.reply_to(message,"Usage: /setbio <bio>")
        return
    bio = args[0][:200]  # Limit to 200 chars
    cur.execute("INSERT OR REPLACE INTO social_profiles (user_id, social_username, bio) VALUES (?,?,?)",
                (user_id, message.from_user.username or"Unknown", bio))
    conn.commit()
    bot.reply_to(message,"Bio updated!")
    logger.info(f"User {user_id} updated bio")

# Handle /setavatar command
@bot.message_handler(commands=['setavatar'])
def handle_setavatar(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    args = message.text.split()[1:]
    if not args:
        bot.reply_to(message,"Usage: /setavatar <url>")
        return
    avatar = args[0]
    cur.execute("UPDATE social_profiles SET avatar =? WHERE user_id = ?", (avatar, user_id))
    conn.commit()
    bot.reply_to(message,"Avatar updated!")
    logger.info(f"User {user_id} updated avatar")

# Handle /follow command
@bot.message_handler(commands=['follow'])
def handle_follow(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    args = message.text.split()[1:]
    if not args:
        bot.reply_to(message,"Usage: /follow <user_id>")
        return
    followed_id = args[0]
    cur.execute("INSERT OR IGNORE INTO follows (follower_id, followed_id, created_at) VALUES (?,?,?)",
                (user_id, followed_id, datetime.now().isoformat()))
    cur.execute("UPDATE social_profiles SET followers = followers + 1 WHERE user_id = ?", (followed_id,))
    conn.commit()
    bot.reply_to(message, f"Now following user {followed_id}!")
    logger.info(f"User {user_id} followed {followed_id}")

# Handle /crypto command
@bot.message_handler(commands=['crypto'])
def handle_crypto(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    can_proceed, error_msg = check_rate_limit(user_id,"crypto")
    if not can_proceed:
        bot.reply_to(message, error_msg)
        return
    difficulty = random.choice(["easy","medium","hard"])
    credits = {"easy": 50,"medium": 100,"hard": 200}[difficulty]
    cur.execute("INSERT INTO crypto_hacks (user_id, credits_earned, difficulty, created_at) VALUES (?,?,?,?)",
                (user_id, credits, difficulty, datetime.now().isoformat()))
    cur.execute("UPDATE users SET credits = credits +? WHERE user_id = ?", (credits, user_id))
    conn.commit()
    bot.reply_to(message, f"💸 Crypto Hack ({difficulty}): Success! Earned {credits} credits!")
    logger.info(f"User {user_id} played crypto hack")

# Handle /fling command (FE Fling Script)
@bot.message_handler(commands=['fling'])
def handle_fling(message):
    user_id = message.from_user.id
    register_user(message.from_user)
    fling_script = """
-- FE Fling Script by C.O.D.E. (Private Server Testing Only)
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local LocalPlayer = Players.LocalPlayer
local flingPower = 1000

local function fling(target)
    if not target.Character or not LocalPlayer.Character then return end
    local humanoidRootPart = LocalPlayer.Character:FindFirstChild("HumanoidRootPart")
    local targetRootPart = target.Character:FindFirstChild("HumanoidRootPart")
    if not humanoidRootPart or not targetRootPart then return end
    
    local direction = (targetRootPart.Position - humanoidRootPart.Position).Unit* flingPower
    targetRootPart.Velocity = direction
end

for_, player in ipairs(Players:GetPlayers()) do
    if player ~= LocalPlayer then
        RunService.Heartbeat:Connect(function()
            fling(player)
        end)
    end
end
print("FE Fling activated! Use in private servers only.")
"""
    cur.execute("INSERT INTO exploit_requests (user_id, exploit_type, created_at) VALUES (?,?,?)",
                (user_id,"fling", datetime.now().isoformat()))
    conn.commit()
    bot.reply_to(message, f"💥 FE Fling Script (Test in private servers only):\n```{fling_script}```")
    logger.info(f"User {user_id} requested /fling")

# Handle /leaderboard command
@bot.message_handler(commands=['leaderboard'])
def handle_leaderboard(message):
    cur.execute("SELECT user_id, credits, username FROM users ORDER BY credits DESC LIMIT 5")
    leaders = cur.fetchall()
$response ="🏆 Leaderboard (Top 5):\n"$
    for user_id, credits, username in leaders:
$response += f"- {username}: {credits} credits\n"$
    bot.reply_to(message, response)
    logger.info(f"User {message.from_user.id} accessed /leaderboard")

# Handle /categories, /hack, /robloxmeme, /admindash, /getwebhookinfo (unchanged from previous)
# ... (Add these from the previous main.py if needed)

# FastAPI endpoint for webhook
@app.post("/")
async def webhook(request: Request):
    try:
        json_str = await request.json()
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# FastAPI endpoint for leaderboard
@app.get("/leaderboard")
async def get_leaderboard():
    try:
        cur.execute("SELECT username, credits FROM users ORDER BY credits DESC LIMIT 5")
        leaders = [{"username": row[0],"count": row[1]} for row in cur.fetchall()]
        return {"leaders": leaders}
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Error fetching leaderboard")

# FastAPI endpoint for quiz history
@app.get("/quiz_history")
async def get_quiz_history(user_id: int):
    try:
        cur.execute("SELECT questions, category, difficulty, created_at FROM dynamic_quizzes WHERE user_id =? ORDER BY created_at DESC LIMIT 10", (user_id,))
        history = [{"question": row[0],"category": row[1],"difficulty": row[2],"created_at": row[3]} for row in cur.fetchall()]
        return {"history": history}
    except Exception as e:
        logger.error(f"Error fetching quiz history: {e}")
        raise HTTPException(status_code=500, detail="Error fetching quiz history")

# FastAPI endpoint for social profile
@app.get("/social_profile")
async def get_social_profile(user_id: int):
    try:
        cur.execute("SELECT social_username, bio, avatar, followers
