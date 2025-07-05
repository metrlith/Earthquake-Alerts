import os
import requests
from dotenv import load_dotenv
import discord
import json
import pycountry
import random
from datetime import datetime
from discord.ext import tasks
from discord.ext.commands import Bot
from discord import app_commands
from database import (
    init_db,
    set_alert_channel,
    get_alert_channel,
    add_subscriber,
    remove_subscriber,
    get_all_subscribers
)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = False
intents.members = True

bot = Bot(command_prefix="!", intents=intents)
tree = bot.tree

USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
last_earthquake_time = None

with open("countries.json", "r") as f:
    loaded_regions = json.load(f)

REGIONS = {"World": None, **loaded_regions}

def flag_emoji(country_name):
    try:
        country = pycountry.countries.get(name=country_name)
        if not country or not hasattr(country, "alpha_2"):
            return ""
        code = country.alpha_2.upper()
        return "".join([chr(ord(c) + 127397) for c in code])
    except:
        return ""

# Remove the old region_choices definition
# region_choices = [...]

# Add autocomplete function for region
async def region_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    # Return up to 25 matching regions
    return [
        app_commands.Choice(
            name=f"{flag_emoji(name)} {name}" if name != "World" else "🌍 World",
            value=name
        )
        for name in sorted(REGIONS.keys())
        if current.lower() in name.lower()
    ][:25]

# -------------- Earthquake Checker -----------------

@tasks.loop(minutes=1)
async def check_earthquakes():
    global last_earthquake_time

    try:
        response = requests.get(USGS_FEED_URL)
        data = response.json()

        for feature in data["features"]:
            props = feature["properties"]
            geom = feature["geometry"]
            place = props["place"]
            mag = props["mag"]
            quake_time = props["time"]
            coords = geom["coordinates"]  # [longitude, latitude, depth]
            lon, lat = coords[0], coords[1]

            if mag is None:
                continue

            if last_earthquake_time is None or quake_time > last_earthquake_time:
                last_earthquake_time = quake_time

                # Send alerts to each configured guild based on region + magnitude
                for guild in bot.guilds:
                    result = get_alert_channel(guild.id)
                    if not result:
                        continue

                    channel_id, min_mag, region_name = result
                    if min_mag is None or region_name is None:
                        continue

                    # Filter by magnitude
                    if mag < min_mag:
                        continue

                    # Filter by region
                    bounds = REGIONS.get(region_name)
                    if bounds:  # Not "World"
                        lat_min, lat_max, lon_min, lon_max = bounds
                        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                            continue

                    # Passed all filters → send alert
                    channel = bot.get_channel(channel_id)
                    if channel:
                        try:
                            # Log to file before sending
                            with open("logs.txt", "a") as log:
                                log.write(f"[{datetime.utcnow()}] Magnitude {mag} | {place} | {lat}, {lon} | URL: {props['url']}\n")

                            # Build the embed for the channel
                            embed = discord.Embed(
                                title="🌍 Earthquake Alert!",
                                color=discord.Color.from_rgb(231, 76, 60),
                                timestamp=datetime.utcnow()
                            )
                            embed.set_thumbnail(url="https://yourcdn.com/Earthquake%20Alerts.webp")
                            embed.add_field(name="Region", value=f"{flag_emoji(region_name)} {region_name}", inline=True)
                            embed.add_field(name="Magnitude", value=f"`{mag}`", inline=True)
                            embed.add_field(name="Location", value=place or "Unknown", inline=False)
                            embed.add_field(name="Coordinates", value=f"`{lat}, {lon}`", inline=False)
                            embed.add_field(name="More Info", value=f"[USGS Details]({props['url']})", inline=False)
                            embed.set_footer(text="Stay alert. Stay safe.")

                            await channel.send(embed=embed)

                        except Exception as e:
                            print(f"❌ Failed to send to {channel_id}: {e}")

                # DM subscribers (no region filtering)
                for user_id in get_all_subscribers():
                    user = await bot.fetch_user(user_id)
                    try:
                        embed = discord.Embed(
                            title="🔔 Earthquake Detected!",
                            color=discord.Color.from_rgb(231, 76, 60),
                            timestamp=datetime.utcnow()
                        )
                        embed.set_thumbnail(url="https://yourcdn.com/Earthquake%20Alerts.webp")
                        embed.add_field(name="Magnitude", value=f"`{mag}`", inline=True)
                        embed.add_field(name="Location", value=place or "Unknown", inline=False)
                        embed.add_field(name="Coordinates", value=f"`{lat}, {lon}`", inline=False)
                        embed.add_field(name="More Info", value=f"[USGS Details]({props['url']})", inline=False)
                        embed.set_footer(text="Stay alert. Stay safe.")

                        await user.send(embed=embed)
                    except Exception as e:
                        print(f"❌ Failed to DM {user_id}: {e}")

                break  # Only notify for the most recent quake

    except Exception as e:
        print("❌ Error fetching earthquake data:", e)

# -------------- Slash Commands ----------------------

@tree.command(name="subscribe", description="Subscribe to earthquake alerts via DM")
async def subscribe(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in get_all_subscribers():
        await interaction.response.send_message("✅ You are already subscribed!", ephemeral=True)
    else:
        add_subscriber(user_id)
        await interaction.response.send_message("📬 Subscribed to global earthquake alerts via DM!", ephemeral=True)

@tree.command(name="unsubscribe", description="Unsubscribe from alerts")
async def unsubscribe(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in get_all_subscribers():
        remove_subscriber(user_id)
        await interaction.response.send_message("❎ Unsubscribed from alerts.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ You are not subscribed.", ephemeral=True)

@tree.command(name="setchannel", description="Set this channel to receive earthquake alerts")
@app_commands.describe(
    min_magnitude="Minimum magnitude to receive alerts for",
    region="Region to monitor earthquakes in"
)
@app_commands.autocomplete(region=region_autocomplete)
@app_commands.checks.has_permissions(administrator=True)
async def setchannel(
    interaction: discord.Interaction,
    min_magnitude: float,
    region: str  # Use str, not Choice[str]
):
    guild_id = interaction.guild.id
    channel_id = interaction.channel_id
    region_name = region

    set_alert_channel(guild_id, channel_id, min_magnitude, region_name)
    await interaction.response.send_message(
        f"✅ Alerts will be sent to this channel for `{region_name}` with magnitude ≥ `{min_magnitude}`.",
        ephemeral=True
    )

@tree.command(name="faketest", description="Send a fake earthquake alert (only for the developer)")
async def faketest(interaction: discord.Interaction):
    if interaction.user.id != 877557616094638112:
        await interaction.response.send_message("⛔ You are not authorized to use this command.", ephemeral=True)
        return

    # Pick a random country
    country = random.choice(list(REGIONS.keys()))
    bounds = REGIONS[country]

    # Random magnitude
    mag = round(random.uniform(1.0, 9.9), 1)

    # Random coordinates
    if bounds:
        lat = round(random.uniform(bounds[0], bounds[1]), 4)
        lon = round(random.uniform(bounds[2], bounds[3]), 4)
    else:  # World
        lat = round(random.uniform(-90.0, 90.0), 4)
        lon = round(random.uniform(-180.0, 180.0), 4)

    # Build the message
    embed = discord.Embed(
        title="🌍 **Earthquake Alert!**",
        description=f"**Magnitude:** `{mag}`\n**Location:** `{country}`\n**Coordinates:** `{lat}, {lon}`",
        color=discord.Color.orange()
    )
    embed.set_footer(text="⚠️ This is a fake alert for testing purposes only.")
    embed.timestamp = datetime.utcnow()

    await interaction.response.send_message(embed=embed)

@tree.command(name="status", description="Show current earthquake alert settings for this server")
@app_commands.checks.has_permissions(administrator=True)
async def status(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    result = get_alert_channel(guild_id)
    
    if not result:
        await interaction.response.send_message("⚠️ This server has no alert configuration yet. Use `/setchannel` to set one up.", ephemeral=True)
        return

    channel_id, min_mag, region_name = result
    channel_mention = f"<#{channel_id}>"

    await interaction.response.send_message(
        f"🔎 **Earthquake Alert Settings for This Server:**\n"
        f"**Region:** `{region_name}`\n"
        f"**Minimum Magnitude:** `{min_mag}`\n"
        f"**Alert Channel:** {channel_mention}",
        ephemeral=True
    )

@tree.command(name="help", description="Learn how to use the Earthquake Alert bot")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📘 Earthquake Alert Bot Help",
        description="Here's how to use this bot:",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="/setchannel",
        value="Admin-only. Set the channel, region, and minimum magnitude for alerts.",
        inline=False
    )
    embed.add_field(
        name="/subscribe",
        value="Receive DMs for global earthquake alerts.",
        inline=False
    )
    embed.add_field(
        name="/unsubscribe",
        value="Stop receiving DM alerts.",
        inline=False
    )
    embed.add_field(
        name="/status",
        value="Check the current alert settings for this server.",
        inline=False
    )
    embed.set_footer(text="Made with 💙 to help you get the fastest information. Stay safe!")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------- Ready Event -------------------------

@bot.event
async def on_ready():
    init_db()
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="USGS Earthquakes")
    )
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")
    check_earthquakes.start()
    print("🔄 Earthquake checker started.")

bot.run(TOKEN)
