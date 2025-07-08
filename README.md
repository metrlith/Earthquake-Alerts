# Earthquake Alerts Discord Bot

A Discord bot that provides real-time earthquake alerts from the USGS feed. Users can subscribe to receive direct messages for earthquakes in specific regions and above a minimum magnitude, and server admins can configure alert channels for their communities.

## Features

- 🌍 Real-time earthquake alerts from USGS
- 📬 User subscriptions for region and magnitude-based DM alerts
- 🔔 Server channel alerts with region and magnitude filters
- 🗺️ Country-based region selection with autocomplete
- 🛡️ Admin-only configuration commands
- 📝 Easy setup with `.env` and SQLite database

## Setup

### 1. Clone the Repository

```sh
git clone https://github.com/yourusername/Earthquake-Alerts.git
cd Earthquake-Alerts
```

### 2. Install Dependencies

Make sure you have Python 3.8+ installed.

```sh
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and add your Discord bot token:

```sh
cp .env.example .env
```

Edit `.env`:

```env
DISCORD_TOKEN=your_bot_token_here
```

### 4. Run the Bot

```sh
python bot.py
```

## Usage

### Server Admin Commands

- `/setchannel` — Set the alert channel, region, and minimum magnitude for this server.
- `/removechannel` — Remove the alert channel configuration.
- `/status` — Show current alert settings for this server.

### User Commands

- `/subscribe` — Receive DMs for earthquakes in a selected region and above a minimum magnitude.
- `/unsubscribe` — Stop receiving DM alerts.
- `/help` — Show help and usage instructions.

### Developer/Test Commands

- `/faketest` — Send a fake earthquake alert (developer only).
- `/sync` — Force re-sync of slash commands (developer only).

## Data Files

- [countries.json](countries.json) — Country bounding boxes for region filtering.
- [countries.csv](countries.csv) — Reference for country bounding boxes.
- [botdata.db](botdata.db) / [config.db](config.db) — SQLite databases for storing configuration and subscriptions.

## Dependencies

See [`requirements.txt`](requirements.txt) for the full list.

Key packages:

- `discord.py`
- `requests`
- `python-dotenv`
- `pycountry`
- `sqlite3` (standard library)
- [Railway](https://railway.app/) for hosting (optional)

## License

MIT License. See [`LICENSE`](LICENSE) for details.

---

Made with 💙 to help you get the fastest earthquake information. Stay safe!
