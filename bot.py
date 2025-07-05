import os
import json
import requests
from dotenv import load_dotenv
import discord
from discord.ext import tasks
from discord.ext.commands import Bot
from discord import app_commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = False
intents.members = True

bot = Bot(command_prefix="!", intents=intents)
tree = bot.tree

USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
last_earthquake_time = None
SUBSCRIBER_FILE = "subscribers.json"

# -------------- Subscriber Management --------------

def load_subscribers():
    if os.path.exists(SUBSCRIBER_FILE):
        with open(SUBSCRIBER_FILE, "r") as f:
            return json.load(f)
    return []

def save_subscribers(subscribers):
    with open(SUBSCRIBER_FILE, "w") as f:
        json.dump(subscribers, f)

# -------------- Earthquake Checker -----------------

@tasks.loop(minutes=1)
async def check_earthquakes():
    global last_earthquake_time

    try:
        response = requests.get(USGS_FEED_URL)
        data = response.json()

        for feature in data["features"]:
            props = feature["properties"]
            place = props["place"]
            mag = props["mag"]
            quake_time = props["time"]

            # FILTER: only Turkey + magnitude >= 3.0 (because I want something specific)
            if mag is None or mag < 3.0:
                continue
            if "turkey" not in place.lower():
                continue

            if last_earthquake_time is None or quake_time > last_earthquake_time:
                last_earthquake_time = quake_time

                # Send to channel (optional)
                channel = discord.utils.get(bot.get_all_channels(), name="earthquake-alerts")
                if channel:
                    await channel.send(
                        f"🌍 **Earthquake Alert!**\n"
                        f"**Magnitude:** `{mag}`\n"
                        f"**Location:** `{place}`\n"
                        f"[More Info]({props['url']})"
                    )

                # Send to subscribed users
                subscribers = load_subscribers()
                for user_id in subscribers:
                    user = await bot.fetch_user(user_id)
                    try:
                        await user.send(
                            f"🔔 **Earthquake in Turkey!**\n"
                            f"**Magnitude:** `{mag}`\n"
                            f"**Location:** `{place}`\n"
                            f"[More Info]({props['url']})"
                        )
                    except Exception as e:
                        print(f"❌ Failed to send DM to {user_id}: {e}")
                break

    except Exception as e:
        print("❌ Error fetching earthquake data:", e)

# -------------- Slash Commands ----------------------

@tree.command(name="subscribe", description="Subscribe to earthquake alerts via DM")
async def subscribe(interaction: discord.Interaction):
    subscribers = load_subscribers()
    if interaction.user.id in subscribers:
        await interaction.response.send_message("✅ You are already subscribed!", ephemeral=True)
    else:
        subscribers.append(interaction.user.id)
        save_subscribers(subscribers)
        await interaction.response.send_message("📬 Subscribed to earthquake alerts in Turkey!", ephemeral=True)

@tree.command(name="unsubscribe", description="Unsubscribe from alerts")
async def unsubscribe(interaction: discord.Interaction):
    subscribers = load_subscribers()
    if interaction.user.id in subscribers:
        subscribers.remove(interaction.user.id)
        save_subscribers(subscribers)
        await interaction.response.send_message("❎ Unsubscribed from alerts.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ You are not subscribed.", ephemeral=True)

# -------------- Ready Event -------------------------

@bot.event
async def on_ready():
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="USGS Earthquakes")
    )
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")
    check_earthquakes.start()

bot.run(TOKEN)