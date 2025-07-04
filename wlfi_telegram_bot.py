import os
import requests
import logging
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
WLFI_AUTHORITY = os.getenv("WLFI_AUTHORITY")  # может быть пустой

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
BIRDEYE_TOKEN_URL = "https://public-api.birdeye.so/public/tokenlist?sort_by=volume_24h_usd"
HELIUS_METADATA_URL = f"https://mainnet.helius.rpcpool.com/?api-key={HELIUS_API_KEY}"
HEADERS_BIRDEYE = {"x-api-key": BIRDEYE_API_KEY}
HEADERS_TWITTER = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

def send_telegram_message(text):
    try:
        response = requests.post(TELEGRAM_API, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text})
        if response.status_code == 200:
            logging.info("✅ Telegram sent: %s", text)
        else:
            logging.error("❌ Telegram error: %s", response.text)
    except Exception as e:
        logging.error("Exception during Telegram send: %s", e)

def fetch_token_list():
    try:
        r = requests.get(BIRDEYE_TOKEN_URL, headers=HEADERS_BIRDEYE)
        data = r.json().get("data", [])
        return [t for t in data if "wlfi" in t.get("name", "").lower() or "wlfi" in t.get("symbol", "").lower()]
    except:
        return []

def fetch_volume(token_address):
    try:
        url = f"https://public-api.birdeye.so/public/token/{token_address}?include=volume_24h_usd"
        r = requests.get(url, headers=HEADERS_BIRDEYE)
        return r.json().get("data", {}).get("volume_24h_usd", 0)
    except:
        return 0

def check_token_metadata(token_address):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": {
            "encoding": "jsonParsed",
            "account": token_address
        }
    }
    try:
        r = requests.post(HELIUS_METADATA_URL, json=body)
        return r.json()
    except:
        return {}

def twitter_search():
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": "WLFI",   # 👈 убрали "$WLFI", чтобы обойти ограничение
        "max_results": 10,
        "tweet.fields": "created_at,author_id"
    }
    try:
        r = requests.get(url, headers=HEADERS_TWITTER, params=params)
        if r.status_code == 200:
            tweets = r.json().get("data", [])
            for tweet in tweets:
                text = tweet.get("text", "")
                created = tweet.get("created_at", "")
                send_telegram_message(f"📣 Tweet about WLFI:\n{text}\n🕓 {created}")
        else:
            logging.warning("Twitter response: %s", r.text)
    except Exception as e:
        logging.error("❌ Twitter exception: %s", e)

def main():
    logging.info("🚀 WLFI Watcher Hunter запущен")

    # Проверка токена в списке с Birdeye
    wlfi_tokens = fetch_token_list()
    if wlfi_tokens:
        for token in wlfi_tokens:
            name = token.get("name")
            symbol = token.get("symbol")
            address = token.get("address")
            volume = fetch_volume(address)
            send_telegram_message(f"🔥 Обнаружен WLFI Token!\n🔹Name: {name}\n🔹Symbol: {symbol}\n🔹Address: {address}\n💸 Volume 24h: ${volume:,.0f}")
    else:
        logging.info("WLFI токен пока не найден в Birdeye.")

    # Twitter поиск
    twitter_search()

if __name__ == "__main__":
    main()
