import os
import requests
import logging
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID")  # личный чат для админ-уведомлений
BIRDEYE_API_KEY     = os.getenv("BIRDEYE_API_KEY")
HELIUS_API_KEY      = os.getenv("HELIUS_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
WLFI_AUTHORITY      = os.getenv("WLFI_AUTHORITY")

# URL-ы API
BIRDEYE_TOKEN_LIST_URL     = "https://public-api.birdeye.so/public/tokenlist?sort_by=volume_24h_usd"
BIRDEYE_TOKEN_LIQUIDITY_URL= "https://public-api.birdeye.so/public/token/{}/liquidity"
HELIUS_METADATA_URL        = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
RAYDIUM_PROGRAM_ID         = "RVKd61ztZW9sSF2oSUWq4DqvF8BVzTcCB7zgwPjzWqk"
HELIUS_RAYDIUM_TXS         = f"https://api.helius.xyz/v0/addresses/{RAYDIUM_PROGRAM_ID}/transactions?api-key={HELIUS_API_KEY}"
METEORA_POOLS_URL          = "https://api.meteora.ag/pools"

HEADERS_BIRDEYE = {"X-API-KEY": BIRDEYE_API_KEY}
HEADERS_TWITTER = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

SUBSCRIBERS_FILE = "subscribers.json"

# Утилиты по подписчикам
def load_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_subscribers(subs):
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subs, f)

def subscribe(chat_id):
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)
        logging.info(f"Новый подписчик: {chat_id}")

# Рассылка сообщений
def send_telegram_message(text: str):
    subs = load_subscribers()
    # всегда шлём и админ-чат
    targets = subs + ([int(TELEGRAM_CHAT_ID)] if TELEGRAM_CHAT_ID else [])
    for cid in set(targets):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text, "parse_mode": "HTML"}
            )
            if resp.status_code != 200:
                logging.error(f"Ошибка при отправке в {cid}: {resp.text}")
        except Exception as e:
            logging.error(f"Telegram send failed to {cid}: {e}")

# Мониторинг OTC/Birdeye
# ... (оставляем функции fetch_token_list, fetch_volume, check_token_metadata)

def fetch_token_list():
    try:
        r = requests.get(BIRDEYE_TOKEN_LIST_URL, headers=HEADERS_BIRDEYE)
        data = r.json().get("data", [])
        return [t for t in data if 'wlfi' in t.get("address", "").lower() or 'wlfi' in t.get("name", "").lower() or 'wlfi' in t.get("symbol", "").lower()]
    except Exception as e:
        logging.error("Birdeye fetch error: %s", e)
        return []


def fetch_volume(token_address):
    try:
        r = requests.get(BIRDEYE_TOKEN_LIQUIDITY_URL.format(token_address), headers=HEADERS_BIRDEYE)
        return r.json().get("data", {}).get("volume_24h_usd", 0.0)
    except Exception as e:
        logging.error("Volume fetch error: %s", e)
        return 0.0


def check_token_metadata(token_address):
    body = {"jsonrpc": "2.0", "id": 1, "method": "getAccountInfo", "params": [token_address, {"encoding": "jsonParsed"}]}
    try:
        r = requests.post(HELIUS_METADATA_URL, json=body)
        authority = r.json().get("result", {}).get("value", {}).get("data", {}).get("parsed", {}).get("info", {}).get("owner", "")
        return authority == WLFI_AUTHORITY if WLFI_AUTHORITY else False
    except Exception as e:
        logging.error("Metadata fetch error: %s", e)
        return False

# Мониторинг Raydium
async def monitor_raydium_activity():
    seen_tx = set()
    logging.info("📡 Monitoring Raydium...")
    while True:
        try:
            r = requests.get(HELIUS_RAYDIUM_TXS)
            data = r.json()
            txs = data.get("transactions") if isinstance(data, dict) else data
            if not isinstance(txs, list): txs = []
            for tx in txs:
                sig = tx.get("signature")
                if sig and sig not in seen_tx:
                    seen_tx.add(sig)
                    logs = tx.get("meta", {}).get("logMessages", [])
                    if any("WLFI" in l for l in logs):
                        send_telegram_message(f"💧 WLFI Raydium TX: https://solscan.io/tx/{sig}")
            await asyncio.sleep(15)
        except Exception as e:
            logging.error("Raydium monitor error: %s", e)
            await asyncio.sleep(30)

# Мониторинг Meteora
async def monitor_meteora():
    seen = set()
    logging.info("🔭 Monitoring Meteora Pools...")
    while True:
        try:
            r = requests.get(METEORA_POOLS_URL)
            pools = r.json() or []
            for pool in pools:
                a = pool.get("tokenA", {}).get("symbol", "").lower()
                b = pool.get("tokenB", {}).get("symbol", "").lower()
                if "wlfi" in (a, b):
                    pid = pool.get("id")
                    if pid and pid not in seen:
                        seen.add(pid)
                        send_telegram_message(
                            f"🧪 WLFI Pool: {a.upper()}/{b.upper()} | fee={pool.get('feeRate')} | vol={pool.get('volume')} | bin={pool.get('binValue')}"
                        )
            await asyncio.sleep(20)
        except Exception as e:
            logging.error("Meteora monitor error: %s", e)
            await asyncio.sleep(40)

# Мониторинг Twitter
async def monitor_twitter():
    last_id = None
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {"query": "from:WLFI_official OR #WLFI", "tweet.fields": "created_at", "max_results": 5}
    logging.info("🐦 Monitoring Twitter...")
    while True:
        try:
            hdr = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            if last_id: params["since_id"] = last_id
            r = requests.get(url, headers=hdr, params=params)
            for tweet in r.json().get("data", []):
                tid = tweet["id"]; txt = tweet["text"]; ts = tweet["created_at"]
                send_telegram_message(f"🐦 WLFI Twitter:\n{txt}\n⏰ {ts}")
                last_id = tid
        except Exception as e:
            logging.error("Twitter monitor error: %s", e)
        await asyncio.sleep(60)

# Подписка на /start
async def poll_updates():
    last_upd = None
    logging.info("🔔 Polling Telegram updates for /start...")
    while True:
        try:
            params = {"timeout":10}
            if last_upd: params["offset"] = last_upd+1
            resp = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params=params).json()
            for upd in resp.get("result", []):
                last_upd = upd.get("update_id")
                msg = upd.get("message", {})
                if msg.get("text") == "/start":
                    subscribe(msg["chat"]["id"] )
        except Exception as e:
            logging.error("Updates poll error: %s", e)
        await asyncio.sleep(5)

# Основной сканер Birdeye
async def main_scanner():
    seen = set()
    while True:
        tokens = fetch_token_list()
        logging.info(f"🔍 Birdeye fetched: {len(tokens)} entries")
        for t in tokens:
            addr = t.get("address")
            if addr and addr not in seen:
                seen.add(addr)
                vol = fetch_volume(addr)
                ok  = check_token_metadata(addr)
                msg = f"🚀 WLFI Token: {t.get('name')} ({t.get('symbol')}) | Addr: {addr} | Vol(24h)={vol:,.0f}"
                if ok: msg += " | ✅ Verified"
                send_telegram_message(msg)
        await asyncio.sleep(30)

# Точка входа
async def main():
    send_telegram_message(
        f"🔄 <b>WLFI Watcher запущен</b> | {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    await asyncio.gather(
        poll_updates(),
        main_scanner(),
        monitor_raydium_activity(),
        monitor_meteora(),
        monitor_twitter(),
    )

if __name__ == "__main__":
    asyncio.run(main())
