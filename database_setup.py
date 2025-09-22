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
    last_login TIMESTAMP,
    email TEXT UNIQUE,
    phone_number TEXT UNIQUE,
    notification_preferences TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

# Referrals table
cur.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER PRIMARY KEY,
    code TEXT UNIQUE,
    referred_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (referred_by) REFERENCES users(user_id)
)""")

# Exploit requests table
cur.execute("""
CREATE TABLE IF NOT EXISTS exploit_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    exploit_type TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Dynamic quizzes table
cur.execute("""
CREATE TABLE IF NOT EXISTS dynamic_quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    questions TEXT,
    category TEXT,
    difficulty TEXT,
    credits INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Spam logs table
cur.execute("""
CREATE TABLE IF NOT EXISTS spam_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Roblox links table
cur.execute("""
CREATE TABLE IF NOT EXISTS roblox_links (
    user_id INTEGER PRIMARY KEY,
    roblox_username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Follows table
cur.execute("""
CREATE TABLE IF NOT EXISTS follows (
    follower_id INTEGER,
    followed_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id),
    FOREIGN KEY (follower_id) REFERENCES users(user_id),
    FOREIGN KEY (followed_id) REFERENCES users(user_id)
)""")

# Crypto hacks table
cur.execute("""
CREATE TABLE IF NOT EXISTS crypto_hacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    credits_earned INTEGER,
    difficulty TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Game joins table
cur.execute("""
CREATE TABLE IF NOT EXISTS game_joins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    game_id TEXT,
    private INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# User themes table
cur.execute("""
CREATE TABLE IF NOT EXISTS user_themes (
    user_id INTEGER PRIMARY KEY,
    theme TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Rate limits table
cur.execute("""
CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    command TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Payments table
cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    tier TEXT,
    amount INTEGER,
    payment_method TEXT,
    transaction_id TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Achievements table
cur.execute("""
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    credits INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)""")

# Indexes for performance
cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_users_phone_number ON users(phone_number);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(code);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_exploit_requests_user_id ON exploit_requests(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_dynamic_quizzes_user_id ON dynamic_quizzes(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_spam_logs_user_id ON spam_logs(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_roblox_links_user_id ON roblox_links(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_social_profiles_user_id ON social_profiles(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_follows_follower_id ON follows(follower_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_follows_followed_id ON follows(followed_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_crypto_hacks_user_id ON crypto_hacks(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_script_market_user_id ON script_market(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_game_joins_user_id ON game_joins(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_user_themes_user_id ON user_themes(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_rate_limits_user_id ON rate_limits(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_achievements_user_id ON achievements(user_id);")

conn.commit()
conn.close()
