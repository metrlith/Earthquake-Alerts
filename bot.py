import os
import sqlite3
import requests
import json
import random
from datetime import datetime

import discord
from discord.ext import tasks
from discord.ext.commands import Bot
from discord import app_commands

import pycountry
from dotenv import load_dotenv

from database import (
    init_db,
    set_alert_channel,
    get_alert_channel,
    add_subscriber,
    remove_subscriber,
    get_all_subscribers_with_filters
)

# =======================================================
# Configuration & Globals
# =======================================================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
last_earthquake_time = None

intents = discord.Intents.default()
intents.message_content = False
intents.members = True

bot = Bot(command_prefix="/", intents=intents)
tree = bot.tree

# =======================================================
# Regions & Flags
# =======================================================

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

async def region_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(
            name=f"{flag_emoji(name)} {name}" if name != "World" else "🌍 World",
            value=name
        )
        for name in sorted(REGIONS.keys())
        if current.lower() in name.lower()
    ][:25]

# =======================================================
# Earthquake Checker Task
# =======================================================

@tasks.loop(minutes=1)
async def check_earthquakes():
    global last_earthquake_time
    try:
        response = requests.get(USGS_FEED_URL)
        data = response.json()

        for feature in data["features"]:
            event_id = feature["id"]
            map_url = f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}/map"
            props = feature["properties"]
            geom = feature["geometry"]
            place = props["place"]
            mag = props["mag"]
            quake_time = props["time"]
            coords = geom["coordinates"]
            lon, lat = coords[0], coords[1]

            if mag is None:
                continue

            if last_earthquake_time is None or quake_time > last_earthquake_time:
                last_earthquake_time = quake_time

                # Guild alerts
                for guild in bot.guilds:
                    result = get_alert_channel(guild.id)
                    if not result:
                        continue

                    channel_id, min_mag, region_name = result
                    if min_mag is None or region_name is None:
                        continue
                    if mag < min_mag:
                        continue

                    bounds = REGIONS.get(region_name)
                    if bounds:
                        lat_min, lat_max, lon_min, lon_max = bounds
                        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                            continue

                    channel = bot.get_channel(channel_id)
                    if channel:
                        try:
                            with open("logs.txt", "a") as log:
                                log.write(f"[{datetime.utcnow()}] Magnitude {mag} | {place} | {lat}, {lon} | URL: {props['url']}\n")

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
                            embed.add_field(name="Epicenter Map", value=f"[📍 View on Map]({map_url})", inline=False)
                            embed.set_footer(text="Stay alert. Stay safe.")

                            await channel.send(embed=embed)
                        except Exception as e:
                            print(f"❌ Failed to send to {channel_id}: {e}")

                # DM subscribers
                for user_id, sub_region, sub_mag in get_all_subscribers_with_filters():
                    if mag < sub_mag:
                        continue

                    sub_bounds = REGIONS.get(sub_region)
                    if sub_bounds:
                        lat_min, lat_max, lon_min, lon_max = sub_bounds
                        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                            continue

                    try:
                        user = await bot.fetch_user(user_id)
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

                break

    except Exception as e:
        print("❌ Error fetching earthquake data:", e)

# =======================================================
# Slash Commands
# =======================================================

@tree.command(name="subscribe", description="Receive DMs for earthquakes matching your region and minimum magnitude")
@app_commands.describe(
    region="Country you want alerts for",
    min_magnitude="Minimum magnitude to receive DMs"
)
async def subscribe(interaction: discord.Interaction, region: str, min_magnitude: float):
    if region not in REGIONS:
        await interaction.response.send_message("⚠️ Invalid region. Please choose a valid country name.", ephemeral=True)
        return

    add_subscriber(interaction.user.id, region, min_magnitude)
    await interaction.response.send_message(
        f"📬 You are now subscribed to DMs for `{region}` earthquakes ≥ `{min_magnitude}`!",
        ephemeral=True
    )

@subscribe.autocomplete("region")
async def region_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in sorted(REGIONS.keys())
        if current.lower() in name.lower()
    ][:25]

@tree.command(name="unsubscribe", description="Unsubscribe from alerts")
async def unsubscribe(interaction: discord.Interaction):
    user_id = interaction.user.id
    remove_subscriber(user_id)
    await interaction.response.send_message("❎ You have been unsubscribed from alerts.", ephemeral=True)

@tree.command(name="setchannel", description="Configure earthquake alerts for this server")
@app_commands.describe(
    channel="Which channel should receive earthquake alerts?",
    min_magnitude="Minimum magnitude to receive alerts for",
    region="Region to monitor earthquakes in"
)
@app_commands.checks.has_permissions(administrator=True)
async def setchannel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    min_magnitude: float,
    region: str
):
    guild_id = interaction.guild.id

    if region not in REGIONS:
        await interaction.response.send_message(
            "⚠️ Invalid region. Please choose a valid country name.",
            ephemeral=True
        )
        return

    set_alert_channel(guild_id, channel.id, min_magnitude, region)

    await interaction.response.send_message(
        f"✅ Alerts will be sent to {channel.mention} for `{region}` with magnitude ≥ `{min_magnitude}`.",
        ephemeral=True
    )

@setchannel.autocomplete("region")
async def region_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in sorted(REGIONS.keys())
        if current.lower() in name.lower()
    ][:25]

@tree.command(name="faketest", description="Send a fake earthquake alert (only for the developer)")
async def faketest(interaction: discord.Interaction):
    if interaction.user.id != 877557616094638112:
        await interaction.response.send_message("⛔ You are not authorized to use this command.", ephemeral=True)
        return

    country = random.choice(list(REGIONS.keys()))
    bounds = REGIONS[country]
    mag = round(random.uniform(1.0, 9.9), 1)

    if bounds:
        lat = round(random.uniform(bounds[0], bounds[1]), 4)
        lon = round(random.uniform(bounds[2], bounds[3]), 4)
    else:
        lat = round(random.uniform(-90.0, 90.0), 4)
        lon = round(random.uniform(-180.0, 180.0), 4)

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

@tree.command(name="removechannel", description="Remove the earthquake alert channel for this server")
@app_commands.checks.has_permissions(administrator=True)
async def removechannel(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    # Remove config from DB
    conn = sqlite3.connect("config.db")
    c = conn.cursor()
    c.execute("DELETE FROM guild_channels WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        "🗑️ Earthquake alerts have been disabled for this server. Use `/setchannel` to re-enable.",
        ephemeral=True
    )

# =======================================================
# Bot Events
# =======================================================

@bot.event
async def on_ready():
    init_db()

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="USGS Earthquakes")
    )

    try:
        synced = await tree.sync()
        print(f"🔧 Synced {len(synced)} commands globally.")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

    await bot.wait_until_ready()

    print(f"✅ Logged in as {bot.user}")
    check_earthquakes.start()
    print("🔄 Earthquake checker started.")

@tree.command(name="sync", description="Force re-sync of slash commands (dev only)")
async def force_sync(interaction: discord.Interaction):
    if interaction.user.id != 877557616094638112:
        await interaction.response.send_message("⛔ You are not authorized to sync.", ephemeral=True)
        return

    try:
        synced = await tree.sync()
        await interaction.response.send_message(f"✅ Synced {len(synced)} commands globally.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Sync failed: {e}", ephemeral=True)

# =======================================================
# Run Bot
# =======================================================

bot.run(TOKEN)
