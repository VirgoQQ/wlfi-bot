import os
import requests
import logging
import time
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
WLFI_AUTHORITY = os.getenv("WLFI_AUTHORITY")

BIRDEYE_TOKEN_LIST_URL = "https://public-api.birdeye.so/public/tokenlist?sort_by=volume_24h_usd"
BIRDEYE_TOKEN_LIQUIDITY_URL = "https://public-api.birdeye.so/public/token/{}/liquidity"
HELIUS_METADATA_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
RAYDIUM_PROGRAM_ID = "RVKd61ztZW9sSF2oSUWq4DqvF8BVzTcCB7zgwPjzWqk"
HELIUS_RAYDIUM_TXS = f"https://api.helius.xyz/v0/addresses/{RAYDIUM_PROGRAM_ID}/transactions?api-key={HELIUS_API_KEY}"
METEORA_POOLS_URL = "https://api.meteora.ag/pools"

HEADERS_BIRDEYE = {"X-API-KEY": BIRDEYE_API_KEY}
HEADERS_TWITTER = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def send_telegram_message(text):
    try:
        response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text
        })
        if response.status_code == 200:
            logging.info("✅ Telegram sent: %s", text)
        else:
            logging.error("❌ Telegram error: %s", response.text)
    except Exception as e:
        logging.error("Telegram send failed: %s", e)


def fetch_token_list():
    try:
        r = requests.get(BIRDEYE_TOKEN_LIST_URL, headers=HEADERS_BIRDEYE)
        data = r.json().get("data", [])
        return [t for t in data if 'wlfi' in t.get("address", "").lower() or 'wlfi' in t.get("name", "").lower() or 'wlfi' in t.get("symbol", "").lower()]
    except:
        return []


def fetch_volume(token_address):
    try:
        r = requests.get(BIRDEYE_TOKEN_LIQUIDITY_URL.format(token_address), headers=HEADERS_BIRDEYE)
        return r.json().get("data", {}).get("volume_24h_usd", 0)
    except:
        return 0


def check_token_metadata(token_address):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [token_address, {"encoding": "jsonParsed"}]
    }
    try:
        r = requests.post(HELIUS_METADATA_URL, json=body)
        result = r.json().get("result", {})
        authority = result.get("value", {}).get("data", {}).get("parsed", {}).get("info", {}).get("owner", "")
        return authority == WLFI_AUTHORITY if WLFI_AUTHORITY else False
    except:
        return False


async def monitor_raydium_activity():
    seen_tx = set()
    logging.info("📡 Monitoring Raydium...")
    while True:
