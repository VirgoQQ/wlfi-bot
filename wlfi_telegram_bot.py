import os
import requests
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
BIRDEYE_API_KEY    = os.getenv("BIRDEYE_API_KEY")
HELIUS_API_KEY     = os.getenv("HELIUS_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
WLFI_AUTHORITY     = os.getenv("WLFI_AUTHORITY")

BIRDEYE_TOKEN_LIST_URL    = "https://public-api.birdeye.so/public/tokenlist?sort_by=volume_24h_usd"
BIRDEYE_TOKEN_LIQUIDITY_URL = "https://public-api.birdeye.so/public/token/{}/liquidity"
HELIUS_METADATA_URL       = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
RAYDIUM_PROGRAM_ID        = "RVKd61ztZW9sSF2oSUWq4DqvF8BVzTcCB7zgwPjzWqk"
HELIUS_RAYDIUM_TXS        = f"https://api.helius.xyz/v0/addresses/{RAYDIUM_PROGRAM_ID}/transactions?api-key={HELIUS_API_KEY}"
METEORA_POOLS_URL         = "https://api.meteora.ag/pools"

HEADERS_BIRDEYE = {"X-API-KEY": BIRDEYE_API_KEY}
HEADERS_TWITTER = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


def send_telegram_message(text: str):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
        )
        if r.status_code == 200:
            logging.info("✅ Telegram sent: %s", text)
        else:
            logging.error("❌ Telegram error: %s", r.text)
    except Exception as e:
        logging.error("Telegram send failed: %s", e)


def fetch_token_list():
    try:
        r = requests.get(BIRDEYE_TOKEN_LIST_URL, headers=HEADERS_BIRDEYE)
        data = r.json().get("data", [])
        return [
            t for t in data
            if 'wlfi' in t.get("address", "").lower()
            or 'wlfi' in t.get("name", "").lower()
            or 'wlfi' in t.get("symbol", "").lower()
        ]
    except Exception as e:
        logging.error("Birdeye fetch error: %s", e)
        return []


def fetch_volume(token_address: str) -> float:
    try:
        r = requests.get(BIRDEYE_TOKEN_LIQUIDITY_URL.format(token_address), headers=HEADERS_BIRDEYE)
        return r.json().get("data", {}).get("volume_24h_usd", 0.0)
    except Exception as e:
        logging.error("Volume fetch error: %s", e)
        return 0.0


def check_token_metadata(token_address: str) -> bool:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [token_address, {"encoding": "jsonParsed"}]
    }
    try:
        r = requests.post(HELIUS_METADATA_URL, json=body)
        result = r.json().get("result", {})
        authority = (
            result.get("value", {})
                  .get("data", {})
                  .get("parsed", {})
                  .get("info", {})
                  .get("owner", "")
        )
        return authority == WLFI_AUTHORITY if WLFI_AUTHORITY else False
    except Exception as e:
        logging.error("Metadata fetch error: %s", e)
        return False


async def monitor_raydium_activity():
    seen_tx = set()
    logging.info("📡 Monitoring Raydium...")
    while True:
        try:
            r = requests.get(HELIUS_RAYDIUM_TXS)
            if r.status_code == 200:
                data = r.json()
                # Helius может отдавать либо dict с ключом "transactions", либо сразу список
                txs = data.get("transactions") if isinstance(data, dict) else data
                if not isinstance(txs, list):
                    txs = []
                for tx in txs:
                    sig = tx.get("signature")
                    if sig and sig not in seen_tx:
                        seen_tx.add(sig)
                        logs = tx.get("meta", {}).get("logMessages", [])
                        if any("WLFI" in msg for msg in logs):
                            send_telegram_message(f"💧 WLFI Raydium TX: https://solscan.io/tx/{sig}")
            await asyncio.sleep(15)
        except Exception as e:
            logging.error("Raydium monitor error: %s", e)
            await asyncio.sleep(30)


async def monitor_meteora():
    seen_pairs = set()
    logging.info("🔭 Monitoring Meteora Pools...")
    while True:
        try:
            r = requests.get(METEORA_POOLS_URL)
            if r.status_code == 200:
                pools = r.json() or []
                for pool in pools:
                    token_a = pool.get("tokenA", {}).get("symbol", "").lower()
                    token_b = pool.get("tokenB", {}).get("symbol", "").lower()
                    if "wlfi" in (token_a, token_b):
                        pid = pool.get("id")
                        if pid and pid not in seen_pairs:
                            seen_pairs.add(pid)
                            fee    = pool.get("feeRate", "?")
                            vol    = pool.get("volume", "?")
                            binval = pool.get("binValue", "?")
                            msg = (
                                f"🧪 WLFI Pool on Meteora:\n"
                                f"Pair: {token_a.upper()} / {token_b.upper()}\n"
                                f"Fee: {fee}\nVolume: {vol}\nBin: {binval}"
                            )
                            send_telegram_message(msg)
            await asyncio.sleep(20)
        except Exception as e:
            logging.error("Meteora monitor error: %s", e)
            await asyncio.sleep(40)


async def monitor_twitter():
    last_id = None
    query   = "from:WLFI_official OR #WLFI"
    url     = "https://api.twitter.com/2/tweets/search/recent"
    params  = {"query": query, "tweet.fields": "created_at", "max_results": 5}
    logging.info("🐦 Monitoring Twitter for WLFI...")
    while True:
        try:
            hdr = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            if last_id:
                params["since_id"] = last_id
            r = requests.get(url, headers=hdr, params=params)
            for tweet in r.json().get("data", []):
                tid = tweet["id"]
                txt = tweet["text"]
                ts  = tweet["created_at"]
                send_telegram_message(f"🐦 <b>WLFI Twitter:</b>\n{txt}\n⏰ {ts}")
                last_id = tid
        except Exception as e:
            logging.error("Twitter monitor error: %s", e)
        await asyncio.sleep(60)


async def main():
    seen = set()
    logging.info("🚀 Starting WLFI token scanner...")
    while True:
        tokens = fetch_token_list()
        logging.info("🔍 Birdeye token list fetched: %d entries", len(tokens))
        for t in tokens:
            addr   = t.get("address")
            if addr and addr not in seen:
                seen.add(addr)
                vol    = fetch_volume(addr)
                is_ok  = check_token_metadata(addr)
                msg    = (
                    f"🚀 WLFI Token Found: {t.get('name')} ({t.get('symbol')})\n"
                    f"Addr: {addr}\nVol(24h): ${vol:,.0f}"
                )
                if is_ok:
                    msg += "\n✅ Verified Authority"
                send_telegram_message(msg)
        await asyncio.sleep(30)


async def main_loop():
    version = os.getenv("RENDER_GIT_COMMIT", "unknown")[:7]
    now     = datetime.now().strftime("%d.%m.%Y %H:%M")
    send_telegram_message(f"🔄 <b>WLFI Watcher обновлён</b>\nВерсия: <code>{version}</code>\n⏰ {now}")
    await asyncio.gather(
        main(),
        monitor_raydium_activity(),
        monitor_meteora(),
        monitor_twitter(),
    )


if __name__ == "__main__":
    asyncio.run(main_loop())
