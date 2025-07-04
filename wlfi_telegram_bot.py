# 🦁 WLFI Early-Launch Watcher Bot — v2.1 (Hunter Edition)

import os
import requests
import logging
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import tweepy

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
WLFI_AUTHORITY = os.getenv("WLFI_AUTHORITY") or None

BIRDEYE_VOLUME_URL = "https://public-api.birdeye.so/public/tokenlist?sort_by=volume_24h_usd"
BIRDEYE_POOL_URL = "https://public-api.birdeye.so/public/pool/mapping"
HELIUS_METADATA_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
HEADERS_BIRDEYE = {"x-api-key": BIRDEYE_API_KEY}
HEADERS_TWITTER = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


def send_telegram_message(text):
    try:
        response = requests.post(TELEGRAM_API, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text
        })
        if response.status_code == 200:
            logging.info("✅ Telegram sent: %s", text)
        else:
            logging.error("❌ Telegram error: %s", response.text)
    except Exception as e:
        logging.error("Exception during Telegram send: %s", e)


def fetch_token_list():
    try:
        r = requests.get(BIRDEYE_VOLUME_URL, headers=HEADERS_BIRDEYE)
        data = r.json().get("data", [])
        return [t for t in data if 'wlfi' in json.dumps(t).lower()]
    except:
        return []


def fetch_volume(token_address):
    try:
        r = requests.get(BIRDEYE_POOL_URL.format(token_address), headers=HEADERS_BIRDEYE)
        return r.json().get("data", {}).get("volume_usd_24h", 0)
    except:
        return 0


def check_token_metadata(token_address):
    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "getAsset", 
        "params": {
            "id": token_address
        }
    }
    try:
        r = requests.post(HELIUS_METADATA_URL, json=body)
        return r.json()
    except:
        return {}


def twitter_search():
    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        query = "WLFI OR $WLFI lang:en"
        tweets = client.search_recent_tweets(query=query, max_results=10)
        results = []
        for tweet in tweets.data or []:
            results.append(tweet.text)
        return results
    except Exception as e:
        logging.warning("Twitter error: %s", e)
        return []


def wlfi_hunter_loop():
    known_ids = set()
    tweet_cache = set()

    while True:
        tokens = fetch_token_list()
        for t in tokens:
            addr = t.get("address")
            if addr and addr not in known_ids:
                known_ids.add(addr)
                vol = fetch_volume(addr)
                meta = check_token_metadata(addr)
                send_telegram_message(f"🔥 WLFI Token Found!\nAddress: {addr}\n24h Vol: ${vol}\nMeta: {meta}")

        tweets = twitter_search()
        for tw in tweets:
            if tw not in tweet_cache:
                tweet_cache.add(tw)
                send_telegram_message(f"🐦 New WLFI Tweet:\n{tw}")

        if WLFI_AUTHORITY:
            send_telegram_message(f"🧠 Authority known: {WLFI_AUTHORITY}")

        time.sleep(60)  # run every 1 minute


if __name__ == "__main__":
    send_telegram_message("🚀 WLFI Watcher запущен!")
    wlfi_hunter_loop()
