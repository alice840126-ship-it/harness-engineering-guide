#!/usr/bin/env python3
"""아침 뉴스 - 매일 07:00 네이버 API로 뉴스 수집 후 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import requests
from datetime import datetime
from telegram_sender import TelegramSender

CATEGORIES = [
    ("부동산", "지식산업센터 부동산"),
    ("경제", "경제 금리 주식"),
    ("AI기술", "AI 인공지능 기술"),
]

def fetch_naver_news(query: str, display: int = 5) -> list:
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "date"}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        print(f"뉴스 오류 ({query}): {e}")
        return []

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    lines = [f"☀️ *{now.strftime('%m월 %d일')} 아침 뉴스*\n"]

    for label, query in CATEGORIES:
        items = fetch_naver_news(query, 5)
        if not items:
            continue
        lines.append(f"\n📌 *{label}*")
        for i, item in enumerate(items, 1):
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
            desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
            lines.append(f"{i}. {title}")
            if desc:
                lines.append(f"   _{desc[:80]}_")

    lines.append("\n⚛️ 자비스")
    message = "\n".join(lines)

    # 4096자 제한 처리
    if len(message) > 4000:
        message = message[:4000] + "\n..."

    success = sender.send_markdown(message)
    print(f"아침 뉴스 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
