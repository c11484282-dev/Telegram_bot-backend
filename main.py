from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import telebot
import os
from dotenv import load_dotenv
import requests
import json
from collections import defaultdict
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MINIAPP_URL = os.getenv("MINIAPP_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize FastAPI and Telebot
app = FastAPI()
bot = telebot.TeleBot(BOT_TOKEN)

# Database setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# In-memory leaderboard (user_id: quiz_count)
leaderboard = defaultdict(int)

# Available quiz topics
QUIZ_TOPICS = ["roblox", "minecraft", "python", "hacking", "general knowledge"]

# Set webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# Helper function to call OpenAI for quiz generation
async def generate_quiz(topic, difficulty):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "gpt-4o-mini", "messages": [
        {"role": "user", "content": f"Generate a {difficulty} quiz question about {topic} with 4 answer options and the correct answer."}
    ]}
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    return "Error generating quiz."

# Handle /start command
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    webapp_button = telebot.types.KeyboardButton("Open Mini App", web_app=telebot.types.WebAppInfo(url=MINIAPP_URL))
    keyboard.add(webapp_button)
    bot.reply_to(message, f"Welcome, {user.username}! Click below to open the Mini App or use /help for commands.", reply_markup=keyboard)

# Handle /newquiz command
@bot.message_handler(commands=['newquiz'])
def handle_newquiz(message):
    args = message.text.split()[1:]
    topic = args[0] if len(args) > 0 else "roblox"
    difficulty = args[1] if len(args) > 1 else "hard"
    if topic.lower() not in QUIZ_TOPICS:
        bot.reply_to(message, f"Invalid topic. Use /categories to see available topics.")
        return
    quiz = generate_quiz(topic, difficulty)
    bot.reply_to(message, f"Quiz: {quiz}")
    # Increment leaderboard
    leaderboard[message.from_user.id] += 1

# Handle /admindash command
@bot.message_handler(commands=['admindash'])
def handle_admindash(message):
    if message.from_user.id == ADMIN_USER_ID:
        bot.reply_to(message, "Admin Dashboard: All systems operational. Use /newquiz, /leaderboard, or Mini App for quizzes.")
    else:
        bot.reply_to(message, "Access denied. Admin only.")

# Handle /getwebhookinfo command
@bot.message_handler(commands=['getwebhookinfo'])
def handle_webhookinfo(message):
    if message.from_user.id == ADMIN_USER_ID:
        webhook_info = bot.get_webhook_info()
        bot.reply_to(message, f"Webhook Info: {json.dumps(webhook_info.__dict__, indent=2)}")
    else:
        bot.reply_to(message, "Access denied. Admin only.")

# Handle /leaderboard command
@bot.message_handler(commands=['leaderboard'])
def handle_leaderboard(message):
    if not leaderboard:
        bot.reply_to(message, "No quiz completions yet. Start with /newquiz!")
        return
    sorted_leaders = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    response = "🏆 Leaderboard (Top 5 Quiz Takers):\n"
    for user_id, count in sorted_leaders:
        user_info = bot.get_chat_member(message.chat.id, user_id).user
        username = user_info.username or user_info.first_name
        response += f"- {username}: {count} quizzes\n"
    bot.reply_to(message, response)

# Handle /categories command
@bot.message_handler(commands=['categories'])
def handle_categories(message):
    response = "Available quiz topics:\n" + "\n".join(f"- {topic}" for topic in QUIZ_TOPICS)
    bot.reply_to(message, response)

# Handle /help command
@bot.message_handler(commands=['help'])
def handle_help(message):
    response = ("🤖 @empire01_bot Commands:\n"
        "/start - Open the Mini App\n"
        "/newquiz [topic] [difficulty] - Get a quiz (e.g., /newquiz roblox hard)\n"
        "/leaderboard - See top quiz takers\n"
        "/categories - List quiz topics\n"
        "/hack - Unleash a fun Roblox-themed 'hack'\n"
        "/admindash - Admin dashboard (admin only)\n"
        "/getwebhookinfo - Check webhook status (admin only)"
    )
    bot.reply_to(message, response)

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

# FastAPI endpoint for webhook
@app.post("/")
async def webhook(request: Request):
    json_str = await request.json()
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return JSONResponse(content={"ok": True})

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "healthy"}
