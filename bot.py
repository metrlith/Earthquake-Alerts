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
    DB_FILE,
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
intents.message_content = True
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

                # Server alerts (existing code)
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
                    if channel and isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
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

                # DM/GC alerts (NEW)
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT channel_id, min_magnitude, region FROM guild_channels WHERE guild_id = 0")
                dm_gc_configs = c.fetchall()
                conn.close()
                
                for channel_id, min_mag, region_name in dm_gc_configs:
                    if min_mag is None or region_name is None:
                        continue
                    if mag < min_mag:
                        continue

                    bounds = REGIONS.get(region_name)
                    if bounds:
                        lat_min, lat_max, lon_min, lon_max = bounds
                        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                            continue

                    try:
                        channel = bot.get_channel(channel_id)
                        if channel and isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread, discord.DMChannel, discord.GroupChannel)):
                            embed = discord.Embed(
                                title="🌍 Earthquake Alert!",
                                color=discord.Color.from_rgb(231, 76, 60),
                                timestamp=datetime.utcnow()
                            )
                            embed.set_thumbnail(url="https://yourcdn.com/Earthquake%20Alerts.webp")
                            embed.add_field(name="Magnitude", value=f"`{mag}`", inline=True)
                            embed.add_field(name="Region", value=f"{flag_emoji(region_name)} {region_name}", inline=True)
                            embed.add_field(name="Location", value=place or "Unknown", inline=False)
                            embed.add_field(name="Coordinates", value=f"`{lat}, {lon}`", inline=False)
                            embed.add_field(name="More Info", value=f"[USGS Details]({props['url']})", inline=False)
                            embed.add_field(name="Epicenter Map", value=f"[📍 View on Map]({map_url})", inline=False)
                            embed.set_footer(text="Stay alert. Stay safe.")

                            await channel.send(embed=embed)
                    except Exception as e:
                        print(f"❌ Failed to send to DM/GC {channel_id}: {e}")

                # User DM subscriptions (existing code)
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

@check_earthquakes.before_loop
async def before_check_earthquakes():
    await bot.wait_until_ready()

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
async def subscribe_region_autocomplete(interaction: discord.Interaction, current: str):
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
    if interaction.guild is None:
        await interaction.response.send_message(
            "⚠️ This command can only be used in servers.",
            ephemeral=True
        )
        return
        
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
async def setchannel_region_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=name, value=name)
        for name in sorted(REGIONS.keys())
        if current.lower() in name.lower()
    ][:25]

@tree.command(name="faketest", description="Send a fake earthquake alert (only for the developer)")
async def faketest(interaction: discord.Interaction):
    ALLOWED_TESTERS = [877557616094638112, 786150805773746197]

    if interaction.user.id not in ALLOWED_TESTERS:
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
    if interaction.guild is None:
        await interaction.response.send_message(
            "⚠️ This command can only be used in servers.",
            ephemeral=True
        )
        return
        
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
    if interaction.guild is None:
        await interaction.response.send_message(
            "⚠️ This command can only be used in servers.",
            ephemeral=True
        )
        return
        
    guild_id = interaction.guild.id

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM guild_channels WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        "🗑️ Earthquake alerts have been disabled for this server. Use `/setchannel` to re-enable.",
        ephemeral=True
    )

@tree.command(name="dmstatus", description="Check your current DM subscription settings")
async def dm_status(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    # Get user's subscription from database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT region, min_magnitude FROM subscribers WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await interaction.response.send_message(
            "📭 You are not currently subscribed to any earthquake alerts.\nUse `/subscribe` to get started!",
            ephemeral=True
        )
        return
    
    region, min_mag = result
    flag = flag_emoji(region) if region != "World" else "🌍"
    
    embed = discord.Embed(
        title="📬 Your DM Subscription Status",
        color=discord.Color.blue()
    )
    embed.add_field(name="Region", value=f"{flag} {region}", inline=True)
    embed.add_field(name="Minimum Magnitude", value=f"`{min_mag}`", inline=True)
    embed.set_footer(text="Use /unsubscribe to stop alerts or /subscribe to change settings")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="gcsetup", description="Set up earthquake alerts for this group chat or DM")
@app_commands.describe(
    min_magnitude="Minimum magnitude for alerts",
    region="Region to monitor"
)
async def gc_setup(interaction: discord.Interaction, min_magnitude: float, region: str):
    # Only works in DMs or group chats (not in servers)
    if interaction.guild is not None:
        await interaction.response.send_message(
            "⚠️ This command is only for DMs and group chats. Use `/setchannel` for servers.",
            ephemeral=True
        )
        return
    
    if interaction.channel is None:
        await interaction.response.send_message(
            "❌ Unable to determine the current channel.",
            ephemeral=True
        )
        return
    
    if region not in REGIONS:
        await interaction.response.send_message(
            "⚠️ Invalid region. Please choose a valid country name.",
            ephemeral=True
        )
        return
    
    channel_id = interaction.channel.id
    # Use 0 as guild_id for DMs/GCs to distinguish from servers
    set_alert_channel(0, channel_id, min_magnitude, region)
    
    flag = flag_emoji(region) if region != "World" else "🌍"
    
    await interaction.response.send_message(
        f"✅ Earthquake alerts set up for this chat!\n"
        f"**Region:** {flag} {region}\n"
        f"**Minimum Magnitude:** `{min_magnitude}`\n\n"
        f"You'll receive alerts here when earthquakes occur in {region} with magnitude ≥ {min_magnitude}."
    )

@tree.command(name="gcremove", description="Remove earthquake alerts from this group chat or DM")
async def gc_remove(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message(
            "⚠️ This command is only for DMs and group chats. Use `/removechannel` for servers.",
            ephemeral=True
        )
        return
    
    if interaction.channel is None:
        await interaction.response.send_message(
            "❌ Unable to determine the current channel.",
            ephemeral=True
        )
        return
    
    channel_id = interaction.channel.id
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM guild_channels WHERE guild_id = 0 AND channel_id = ?", (channel_id,))
    affected_rows = c.rowcount
    conn.commit()
    conn.close()
    
    if affected_rows > 0:
        await interaction.response.send_message(
            "🗑️ Earthquake alerts have been removed from this chat."
        )
    else:
        await interaction.response.send_message(
            "⚠️ This chat doesn't have any earthquake alerts set up."
        )

@tree.command(name="gcstatus", description="Check earthquake alert settings for this group chat or DM")
async def gc_status(interaction: discord.Interaction):
    if interaction.guild is not None:
        await interaction.response.send_message(
            "⚠️ This command is only for DMs and group chats. Use `/status` for servers.",
            ephemeral=True
        )
        return
    
    if interaction.channel is None:
        await interaction.response.send_message(
            "❌ Unable to determine the current channel.",
            ephemeral=True
        )
        return
    
    channel_id = interaction.channel.id
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT min_magnitude, region FROM guild_channels WHERE guild_id = 0 AND channel_id = ?", (channel_id,))
    result = c.fetchone()
    conn.close()
    
    if not result:
        await interaction.response.send_message(
            "📭 This chat doesn't have earthquake alerts set up.\nUse `/gcsetup` to configure alerts!"
        )
        return
    
    min_mag, region_name = result
    flag = flag_emoji(region_name) if region_name != "World" else "🌍"
    
    embed = discord.Embed(
        title="🔎 Earthquake Alert Settings",
        color=discord.Color.green()
    )
    embed.add_field(name="Region", value=f"{flag} {region_name}", inline=True)
    embed.add_field(name="Minimum Magnitude", value=f"`{min_mag}`", inline=True)
    embed.set_footer(text="Use /gcremove to disable or /gcsetup to change settings")
    
    await interaction.response.send_message(embed=embed)

@tree.command(name="recent", description="Show the 5 most recent earthquakes worldwide")
@app_commands.describe(min_magnitude="Minimum magnitude to show (optional)")
async def recent_earthquakes(interaction: discord.Interaction, min_magnitude: float = 1.0):
    try:
        response = requests.get(USGS_FEED_URL)
        data = response.json()
        
        earthquakes = []
        for feature in data["features"]:
            props = feature["properties"]
            coords = feature["geometry"]["coordinates"]
            
            mag = props["mag"]
            if mag is None or mag < min_magnitude:
                continue
                
            earthquakes.append({
                "magnitude": mag,
                "place": props["place"],
                "time": props["time"],
                "coords": (coords[1], coords[0]),  # lat, lon
                "url": props["url"]
            })
        
        # Sort by time (most recent first) and take top 5
        earthquakes.sort(key=lambda x: x["time"], reverse=True)
        earthquakes = earthquakes[:5]
        
        if not earthquakes:
            await interaction.response.send_message(
                f"🔍 No recent earthquakes found with magnitude ≥ {min_magnitude}",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📊 Recent Earthquakes",
            description=f"Showing {len(earthquakes)} most recent earthquakes ≥ M{min_magnitude}",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        for i, eq in enumerate(earthquakes, 1):
            time_str = datetime.fromtimestamp(eq["time"] / 1000).strftime("%m/%d %H:%M UTC")
            embed.add_field(
                name=f"{i}. M{eq['magnitude']} - {time_str}",
                value=f"📍 {eq['place']}\n🌐 [{eq['coords'][0]:.2f}, {eq['coords'][1]:.2f}]({eq['url']})",
                inline=False
            )
        
        embed.set_footer(text="Data from USGS • Click coordinates for details")
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(
            "❌ Failed to fetch recent earthquakes. Please try again later.",
            ephemeral=True
        )
        print(f"Error in recent_earthquakes: {e}")

@bot.event
async def on_ready():
    print(f'🤖 {bot.user} has connected to Discord!')
    init_db()
    if not check_earthquakes.is_running():
        check_earthquakes.start()
        print("🌍 Earthquake monitoring started!")

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN not found in environment variables!")
