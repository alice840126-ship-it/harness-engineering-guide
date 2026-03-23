#!/usr/bin/env python3
"""저녁 브리핑 - 매일 17:50 섹션별 뉴스 5개씩 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import requests
from datetime import datetime
from telegram_sender import TelegramSender

SECTIONS = [
    ("🏢 기업/재무", "기업 실적 주주 재무"),
    ("🏠 주거/생활", "아파트 전세 부동산 주거"),
    ("📈 주식시장", "코스피 코스닥 주가 증권"),
    ("⚙️ 산업/기술", "산업 기술 AI 반도체"),
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

    lines = [f"🌆 *{now.strftime('%m월 %d일')} 저녁 브리핑*\n"]

    for section_label, query in SECTIONS:
        items = fetch_naver_news(query, 5)
        if not items:
            continue
        lines.append(f"\n{section_label}")
        for i, item in enumerate(items, 1):
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
            desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
            lines.append(f"{i}. {title}")
            if desc:
                lines.append(f"   _{desc[:80]}_")

    lines.append(f"\n💡 자비스의 한 줄 통찰")
    lines.append(f"오늘 시장의 흐름을 파악하고, 내일을 준비하세요.\n")
    lines.append("⚛️ 자비스")

    message = "\n".join(lines)
    if len(message) > 4000:
        message = message[:4000] + "\n..."

    success = sender.send_markdown(message)
    print(f"저녁 브리핑 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
