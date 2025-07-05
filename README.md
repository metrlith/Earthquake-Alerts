# 🌍 Earthquake Alerts Discord Bot

Stay ahead of seismic activity with a real-time, globally aware earthquake alert bot for Discord — powered by [USGS](https://earthquake.usgs.gov/).

---

## 📦 Features

- **Live USGS Feed** — Checked every minute
- **Per-Server Configuration** — Custom alert channel, region, and minimum magnitude
- **DM Alerts** — Subscribe to personal alerts from anywhere in the world
- **Support for 195 Countries** — Filter alerts by country
- **Developer Tools** — Run a `/faketest` to preview alerts
- **Commands** — All via slash commands (no prefix required)

---

## 🚀 Commands

| Command         | Description                                        |
|----------------|----------------------------------------------------|
| `/setchannel`   | Set the alert channel, region, and magnitude      |
| `/removechannel`| Disable alerts in the current server              |
| `/subscribe`    | Get DMs for all earthquakes (global)              |
| `/unsubscribe`  | Stop DMs                                           |
| `/status`       | View current server configuration                 |
| `/help`         | View usage guide                                   |
| `/faketest`     | Send a fake alert (developer-only)                |

---

## ⚙️ Setup (Local Development)

1. Clone the repo:

   ```bash
   git clone https://github.com/<your-github-username>/Earthquake-Alerts.git
   # Replace <your-github-username> with the repository owner's GitHub username
   cd Earthquake-Alerts
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file:

   It should be like [the example environment file.](.env.example)

   ```env
   DISCORD_TOKEN=your-bot-token
   ```

4. Run the bot:

   ```bash
   python bot.py
   ```

---

## 🛠️ Tech Stack

- USGS Earthquake GeoJSON Feed
- Railway.app

---

## 📄 License

MIT License © 2025 Earthquake Alerts
