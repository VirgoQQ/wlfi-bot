# WLFI Watcher Bot

A 24/7 Telegram bot that tracks the earliest signs of the WLFI token launch on Solana using Birdeye, Dexscreener, Meteora, Helius, Raydium logs, and Twitter.

## 🧩 Files
- `wlfi_telegram_bot.py`: The main bot code
- `.env.example`: Environment variables template
- `requirements.txt`: Python dependencies

## 🚀 How to run locally

```bash
git clone https://github.com/YOUR_USERNAME/wlfi-bot.git
cd wlfi-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your real keys
python wlfi_telegram_bot.py
```

## ☁️ How to deploy on Render.com
1. Go to https://render.com
2. Click “New +” → “Web Service”
3. Connect this GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `python wlfi_telegram_bot.py`
6. Set up all `.env` variables from `.env.example`

Ready to hunt WLFI first 🦅
