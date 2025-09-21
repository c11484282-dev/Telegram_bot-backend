import sqlite3

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

# Users table
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    credits INTEGER DEFAULT 0,
    premium_until TIMESTAMP,
    premium_tier TEXT,
    streak INTEGER DEFAULT 0,
    last_login TIMESTAMP)""")

# Referrals table
cur.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER PRIMARY KEY,
    code TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Exploit requests table
cur.execute("""
CREATE TABLE IF NOT EXISTS exploit_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    exploit_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Dynamic quizzes table
cur.execute("""
CREATE TABLE IF NOT EXISTS dynamic_quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    questions TEXT,
    category TEXT,
    difficulty TEXT,
    credits INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Spam logs table
cur.execute("""
CREATE TABLE IF NOT EXISTS spam_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Roblox links table
cur.execute("""
CREATE TABLE IF NOT EXISTS roblox_links (
    user_id INTEGER PRIMARY KEY,
    roblox_username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Social profiles table
cur.execute("""
CREATE TABLE IF NOT EXISTS social_profiles (
    user_id INTEGER PRIMARY KEY,
    social_username TEXT,
    bio TEXT,
    avatar TEXT,
    theme_color TEXT,
    followers INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Follows table
cur.execute("""
CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER,
    followed_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id)
)""")

# Crypto hacks table
cur.execute("""
CREATE TABLE IF NOT EXISTS crypto_hacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    credits_earned INTEGER,
    difficulty TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Script market table
cur.execute("""
CREATE TABLE IF NOT EXISTS script_market (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    description TEXT,
    script TEXT,
    price INTEGER,
    rating REAL,
    approved INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Game joins table
cur.execute("""
CREATE TABLE IF NOT EXISTS game_joins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    game_id TEXT,
    private INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# User themes table
cur.execute("""
CREATE TABLE IF NOT EXISTS user_themes (
    user_id INTEGER PRIMARY KEY,
    theme TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Rate limits table
cur.execute("""
CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    command TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Payments table
cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tier TEXT,
    amount INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

# Achievements table
cur.execute("""
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    credits INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

conn.commit()
conn.close()