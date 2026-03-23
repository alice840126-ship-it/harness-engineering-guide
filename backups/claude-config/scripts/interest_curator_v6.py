#!/usr/bin/env python3
"""관심사 큐레이션 - 하루 6회 (09:00~19:00) Brave API로 관심 뉴스 수집 후 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import requests
from datetime import datetime
from telegram_sender import TelegramSender

INTERESTS = [
    "지식산업센터 부동산",
    "부동산 경매",
    "AI 에이전트",
    "오픈클로",
]

def search_brave(query: str, count: int = 3) -> list:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {"q": query, "count": count}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("web", {}).get("results", [])[:2]
    except Exception as e:
        print(f"Brave 검색 오류 ({query}): {e}")
        return []

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    lines = [f"🔍 *{now.strftime('%H:%M')} 관심사 서핑*\n"]

    for interest in INTERESTS:
        results = search_brave(interest)
        if not results:
            continue
        lines.append(f"\n*{interest}*")
        for r in results:
            title = r.get("title", "")[:60]
            url = r.get("url", "")
            lines.append(f"• [{title}]({url})")

    lines.append("\n⚛️ 자비스")
    message = "\n".join(lines)

    if len(message) > 4000:
        message = message[:4000] + "\n..."

    success = sender.send_markdown(message)
    print(f"관심사 큐레이션 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
