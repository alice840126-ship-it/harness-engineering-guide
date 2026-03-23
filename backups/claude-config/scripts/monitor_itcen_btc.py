#!/usr/bin/env python3
"""아이티센글로벌 + BTC 모니터링 - 매시간 실행, 변동 ±3% 시 텔레그램 알림"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import json
import requests
from datetime import datetime
from pathlib import Path
from telegram_sender import TelegramSender

CACHE_FILE = Path("/Users/oungsooryu/.claude/logs/monitor_cache.json")
ALERT_THRESHOLD = 3.0  # 3% 변동 시 알림

def get_itcen_price() -> dict:
    """아이티센글로벌 주가 (네이버 금융 API)"""
    try:
        url = "https://finance.naver.com/item/sise.naver"
        params = {"code": "035600"}  # 아이티센글로벌 종목코드
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, params=params, headers=headers, timeout=10)
        # 간단한 가격 파싱
        import re
        matches = re.findall(r'"now":\s*"?([\d,]+)"?', res.text)
        if matches:
            price = int(matches[0].replace(",", ""))
            return {"price": price, "symbol": "ITCEN"}
    except Exception as e:
        print(f"ITCEN 조회 오류: {e}")
    return {}

def get_btc_price() -> dict:
    """BTC 가격 (CoinGecko API)"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "krw,usd"}
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json().get("bitcoin", {})
        return {"krw": data.get("krw", 0), "usd": data.get("usd", 0)}
    except Exception as e:
        print(f"BTC 조회 오류: {e}")
        return {}

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            pass
    return {}

def save_cache(data: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False))

def calc_change(current: float, previous: float) -> float:
    if not previous:
        return 0
    return ((current - previous) / previous) * 100

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)
    cache = load_cache()
    alerts = []

    # 아이티센글로벌
    itcen = get_itcen_price()
    if itcen.get("price"):
        price = itcen["price"]
        prev = cache.get("itcen_price", 0)
        change = calc_change(price, prev)
        cache["itcen_price"] = price
        print(f"ITCEN: {price:,}원 ({change:+.1f}%)")
        if abs(change) >= ALERT_THRESHOLD and prev:
            emoji = "🚀" if change > 0 else "📉"
            alerts.append(f"{emoji} *아이티센글로벌* {price:,}원 ({change:+.1f}%)")

    # BTC
    btc = get_btc_price()
    if btc.get("krw"):
        krw = btc["krw"]
        usd = btc["usd"]
        prev = cache.get("btc_krw", 0)
        change = calc_change(krw, prev)
        cache["btc_krw"] = krw
        print(f"BTC: {krw:,}원 / ${usd:,} ({change:+.1f}%)")
        if abs(change) >= ALERT_THRESHOLD and prev:
            emoji = "🚀" if change > 0 else "📉"
            alerts.append(f"{emoji} *BTC* {krw:,}원 / ${usd:,} ({change:+.1f}%)")

    save_cache(cache)

    if alerts:
        message = f"⚡ *시장 알림* ({now.strftime('%H:%M')})\n\n" + "\n".join(alerts) + "\n\n⚛️ 자비스"
        sender.send_markdown(message)
        print(f"알림 전송: {len(alerts)}건")
    else:
        print("변동 없음 (임계값 미달)")

if __name__ == "__main__":
    main()
