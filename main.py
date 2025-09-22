from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import telebot
import os
from dotenv import load_dotenv
import requests
import json

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

# Set webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

# Helper function to call OpenAI for quiz generation
async def generate_quiz(topic, difficulty):
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}","Content-Type":"application/json"
    }
    payload = {"model":"gpt-4o-mini","messages": [
            {"role":"user","content": f"Generate a {difficulty} quiz question about {topic} with 4 answer options and the correct answer."}
        ]}    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"]
    return"Error generating quiz."

# Handle /start command
@bot.message_handler(commands=['start'])
def handle_start(message):
    user = message.from_user
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    webapp_button = telebot.types.KeyboardButton("Open Mini App", web_app=telebot.types.WebAppInfo(url=MINIAPP_URL))
    keyboard.add(webapp_button)
    bot.reply_to(message, f"Welcome, {user.username}! Click below to open the Mini App.", reply_markup=keyboard)

# Handle /newquiz command
@bot.message_handler(commands=['newquiz'])
def handle_newquiz(message):
    args = message.text.split()[1:]
    topic = args[0] if len(args) > 0 else"roblox"
    difficulty = args[1] if len(args) > 1 else"hard"
    quiz = generate_quiz(topic, difficulty)
    bot.reply_to(message, f"Quiz: {quiz}")

# Handle /admindash command
@bot.message_handler(commands=['admindash'])
def handle_admindash(message):
    if message.from_user.id == ADMIN_USER_ID:
        bot.reply_to(message,"Admin Dashboard: All systems operational. Use /newquiz or Mini App for quizzes.")
    else:
        bot.reply_to(message,"Access denied. Admin only.")

# Handle /getwebhookinfo command
@bot.message_handler(commands=['getwebhookinfo'])
def handle_webhookinfo(message):
    if message.from_user.id == ADMIN_USER_ID:
        webhook_info = bot.get_webhook_info()
        bot.reply_to(message, f"Webhook Info: {json.dumps(webhook_info.__dict__, indent=2)}")
    else:
        bot.reply_to(message,"Access denied. Admin only.")

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
    return {"status":"healthy"}