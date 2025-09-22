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
from collections import defaultdict

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

# Available quiz topics
QUIZ_TOPICS = ["roblox","minecraft","python","hacking","general knowledge"]

# Persistent leaderboard storage
LEADERBOARD_FILE ="leaderboard.json"
RATE_LIMIT_FILE ="rate_limits.json"

# Load leaderboard from file
def load_leaderboard():
    try:
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, 'r') as f:
                return defaultdict(int, json.load(f))
        return defaultdict(int)
    except Exception as e:
        logger.error(f"Error loading leaderboard: {e}")
        return defaultdict(int)

# Save leaderboard to file
def save_leaderboard(leaderboard):
    try:
        with open(LEADERBOARD_FILE, 'w') as f:
            json.dump(dict(leaderboard), f)
    except Exception as e:
        logger.error(f"Error saving leaderboard: {e}")

# Load rate limits from file
def load_rate_limits():
    try:
        if os.path.exists(RATE_LIMIT_FILE):
            with open(RATE_LIMIT_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading rate limits: {e}")
        return {}

# Save rate limits to file
def save_rate_limits(rate_limits):
    try:
        with open(RATE_LIMIT_FILE, 'w') as f:
            json.dump(rate_limits, f)
    except Exception as e:
        logger.error(f"Error saving rate limits: {e}")

# Initialize data
leaderboard = load_leaderboard()
rate_limits = load_rate_limits()

# Rate limiting: 5 quizzes per hour per user
MAX_QUIZZES_PER_HOUR = 5
RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds

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
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        return f"Error generating quiz: {str(e)}"

# Check rate limit
def check_rate_limit(user_id):
    user_id = str(user_id)
    now = time.time()
    if user_id not in rate_limits:
        rate_limits[user_id] = {"count": 0,"reset_time": now}
    user_data = rate_limits[user_id]
    if now > user_data["reset_time"] + RATE_LIMIT_WINDOW:
        user_data["count"] = 0
        user_data["reset_time"] = now
    if user_data["count"] >= MAX_QUIZZES_PER_HOUR:
        reset_time = datetime.fromtimestamp(user_data["reset_time"] + RATE_LIMIT_WINDOW)
        return False, f"Rate limit exceeded. Try again at {reset_time.strftime('%H:%M:%S')}."
    user_data["count"] += 1
    save_rate_limits(rate_limits)
    return True, ""

# Handle /start command
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    webapp_button = telebot.types.KeyboardButton("Open Mini App", web_app=telebot.types.WebAppInfo(url=MINIAPP_URL))
    keyboard.add(webapp_button)
    bot.reply_to(message, f"Welcome, {user.username}! Click below to open the Mini App or use /help for commands.", reply_markup=keyboard)
    logger.info(f"User {user.id} started bot")

# Handle /newquiz command
@bot.message_handler(commands=['newquiz'])
def handle_newquiz(message):
    user_id = message.from_user.id
    can_proceed, error_msg = check_rate_limit(user_id)
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
    bot.reply_to(message, f"Quiz: {quiz}")
    leaderboard[str(user_id)] += 1
    save_leaderboard(leaderboard)
    logger.info(f"User {user_id} requested quiz: {topic}, {difficulty}")

# Handle /admindash command
@bot.message_handler(commands=['admindash'])
def handle_admindash(message):
    if message.from_user.id == ADMIN_USER_ID:
        bot.reply_to(message,"Admin Dashboard: All systems operational. Use /newquiz, /leaderboard, or Mini App for quizzes.")
    else:
        bot.reply_to(message,"Access denied. Admin only.")
    logger.info(f"User {message.from_user.id} accessed /admindash")

# Handle /getwebhookinfo command
@bot.message_handler(commands=['getwebhookinfo'])
def handle_webhookinfo(message):
    if message.from_user.id == ADMIN_USER_ID:
        webhook_info = bot.get_webhook_info()
        bot.reply_to(message, f"Webhook Info: {json.dumps(webhook_info.__dict__, indent=2)}")
    else:
        bot.reply_to(message,"Access denied. Admin only.")
    logger.info(f"User {message.from_user.id} accessed /getwebhookinfo")

# Handle /leaderboard command
@bot.message_handler(commands=['leaderboard'])
def handle_leaderboard(message):
    if not leaderboard:
        bot.reply_to(message,"No quiz completions yet. Start with /newquiz!")
        return
    sorted_leaders = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    response ="🏆 Leaderboard (Top 5 Quiz Takers):\n"
    for user_id, count in sorted_leaders:
        try:
            user_info = bot.get_chat_member(message.chat.id, int(user_id)).user
            username = user_info.username or user_info.first_name
            response += f"- {username}: {count} quizzes\n"
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            response += f"- User_{user_id}: {count} quizzes\n"
    bot.reply_to(message, response)
    logger.info(f"User {message.from_user.id} accessed /leaderboard")

# Handle /categories command
@bot.message_handler(commands=['categories'])
def handle_categories(message):
    response ="Available quiz topics:\n" +"\n".join(f"- {topic}" for topic in QUIZ_TOPICS)
    bot.reply_to(message, response)
    logger.info(f"User {message.from_user.id} accessed /categories")

# Handle /help command
@bot.message_handler(commands=['help'])
def handle_help(message):
    response = ("🤖 @empire01_bot Commands:\n"
        "/start - Open the Mini App\n"
        "/newquiz [topic] [difficulty] - Get a quiz (e.g., /newquiz roblox hard)\n"
        "/leaderboard - See top quiz takers\n"
        "/categories - List quiz topics\n"
        "/profile - View your quiz stats\n"
        "/dailyquiz - Get a daily quiz challenge\n"
        "/hack - Unleash a fun Roblox-themed 'hack'\n"
        "/robloxmeme - Get a random Roblox meme\n"
        "/admindash - Admin dashboard (admin only)\n"
        "/getwebhookinfo - Check webhook status (admin only)"
    )
    bot.reply_to(message, response)
    logger.info(f"User {message.from_user.id} accessed /help")

# Handle /hack command
@bot.message_handler(commands=['hack'])
def handle_hack(message):
    hack_art = """
    💾 Roblox Hack Activated! 💾
    ╔════════════════════╗
    ║ 0101 VIRUS LOADED  ║
    ╚════════════════════╝
    Injecting fun... [██████████] 100%
    """
    bot.reply_to(message, hack_art)
    logger.info(f"User {message.from_user.id} accessed /hack")

# Handle /robloxmeme command
@bot.message_handler(commands=['robloxmeme'])
def handle_robloxmeme(message):
    memes = ["https://i.imgur.com/roblox_meme1.jpg","https://i.imgur.com/roblox_meme2.jpg","https://i.imgur.com/roblox_meme3.jpg"
    ]
    meme_url = random.choice(memes)
    bot.reply_to(message, f"🔥 Roblox Meme Alert! 🔥 Check this out: {meme_url}")
    logger.info(f"User {message.from_user.id} accessed /robloxmeme")

# Handle /profile command
@bot.message_handler(commands=['profile'])
def handle_profile(message):
    user_id = str(message.from_user.id)
    quiz_count = leaderboard.get(user_id, 0)
    username = message.from_user.username or message.from_user.first_name
    response = (
        f"👤 Profile: {username}\n"
        f"🆔 Telegram ID: {user_id}\n"
        f"🏆 Quizzes Completed: {quiz_count}\n"
        f"📊 Leaderboard Rank: {get_leaderboard_rank(user_id)}"
    )
    bot.reply_to(message, response)
    logger.info(f"User {user_id} accessed /profile")

# Helper function for leaderboard rank
def get_leaderboard_rank(user_id):
    sorted_leaders = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    for i, (uid, _) in enumerate(sorted_leaders, 1):
        if uid == user_id:
            return i
    return"Unranked"

# Handle /dailyquiz command
@bot.message_handler(commands=['dailyquiz'])
def handle_dailyquiz(message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    last_quiz = rate_limits.get(user_id, {}).get("daily_quiz_time")
    if last_quiz:
        last_quiz_time = datetime.fromisoformat(last_quiz)
        if now.date() == last_quiz_time.date():
            bot.reply_to(message,"You've already taken today's daily quiz! Try again tomorrow.")
            return
    topic = random.choice(QUIZ_TOPICS)
    difficulty = random.choice(["easy","medium","hard"])
    quiz = generate_quiz(topic, difficulty)
    bot.reply_to(message, f"📅 Daily Quiz ({topic}, {difficulty}): {quiz}")
    leaderboard[user_id] += 1
    save_leaderboard(leaderboard)
    rate_limits[user_id] = rate_limits.get(user_id, {})
    rate_limits[user_id]["daily_quiz_time"] = now.isoformat()
    save_rate_limits(rate_limits)
    logger.info(f"User {user_id} accessed /dailyquiz")

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

# Health check endpoint
@app.get("/health")
async def health():
    return {"status":"healthy"}
