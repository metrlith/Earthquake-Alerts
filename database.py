import sqlite3

DB_FILE = "botdata.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Update: store channel, region, and magnitude
    c.execute("""
    CREATE TABLE IF NOT EXISTS guild_channels (
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER,
        min_magnitude REAL,
        region TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        user_id INTEGER PRIMARY KEY
    )
    """)

    conn.commit()
    conn.close()

def init_db():
    conn = sqlite3.connect("config.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        user_id INTEGER PRIMARY KEY,
        region TEXT,
        min_magnitude REAL
    )
""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id INTEGER PRIMARY KEY,
            region TEXT,
            min_magnitude REAL
        )
    """)
    conn.commit()
    conn.close()

def set_alert_channel(guild_id, channel_id, min_magnitude, region):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        REPLACE INTO guild_channels (guild_id, channel_id, min_magnitude, region)
        VALUES (?, ?, ?, ?)
    """, (guild_id, channel_id, min_magnitude, region))
    conn.commit()
    conn.close()


def get_alert_channel(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT channel_id, min_magnitude, region FROM guild_channels WHERE guild_id = ?", (guild_id,))
    result = c.fetchone()
    conn.close()
    return result if result else None

def add_subscriber(user_id, region, min_magnitude):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "REPLACE INTO subscribers (user_id, region, min_magnitude) VALUES (?, ?, ?)",
        (user_id, region, min_magnitude)
    )
    conn.commit()
    conn.close()

def remove_subscriber(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM subscribers WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_subscribers_with_filters():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, region, min_magnitude FROM subscribers")
    result = c.fetchall()
    conn.close()
    return result