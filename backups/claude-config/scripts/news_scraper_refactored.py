#!/usr/bin/env python3
"""뉴스 스크래퍼 - 주간(일요일 09:00) / 월간(1일 09:00) 옵시디언 저장 + 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import requests
from datetime import datetime, timedelta
from pathlib import Path
from telegram_sender import TelegramSender

QUERIES = [
    ("부동산/지식산업센터", "지식산업센터 부동산 매매"),
    ("경제/금융", "경제 금리 주식 코스피"),
    ("AI/기술", "AI 인공지능 기술 스타트업"),
    ("지정학/국제", "지정학 무역 미국 중국"),
]

def fetch_naver_news(query: str, display: int = 10) -> list:
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

def determine_period() -> tuple:
    """실행 날짜 기준으로 주간/월간 판단"""
    now = datetime.now()
    day_of_week = now.weekday()  # 0=월, 6=일
    day_of_month = now.day

    if day_of_month == 1:
        return "monthly", now
    elif day_of_week == 6:  # 일요일
        return "weekly", now
    else:
        return "weekly", now  # 기본값

def save_to_obsidian(period: str, content: str, now: datetime):
    vault = Path(VAULT_PATH)

    if period == "monthly":
        folder = vault / "30. 자원 상자" / "뉴스" / str(now.year) / "월간"
        filename = f"{now.year}-{now.month:02d}월 뉴스 분석.md"
    else:
        # 이번 주 날짜 범위
        week_start = now - timedelta(days=now.weekday())
        week_end = week_start + timedelta(days=6)
        folder = vault / "30. 자원 상자" / "뉴스" / str(now.year) / "주간"
        filename = f"{week_start.strftime('%m월%d일')}~{week_end.strftime('%m월%d일')} 주간 뉴스.md"

    folder.mkdir(parents=True, exist_ok=True)
    note_path = folder / filename
    note_path.write_text(content, encoding="utf-8")
    print(f"✅ 저장: {note_path}")
    return str(note_path)

def build_content(period: str, now: datetime, all_news: dict) -> str:
    period_label = "월간" if period == "monthly" else "주간"
    lines = [
        f"---",
        f"date: {now.strftime('%Y-%m-%d')}",
        f"type: {period_label}-뉴스",
        f"tags: [뉴스, {period_label}]",
        f"---",
        f"",
        f"# {now.strftime('%Y년 %m월')} {period_label} 뉴스 분석",
        f"",
    ]
    for label, items in all_news.items():
        lines.append(f"## 📌 {label}")
        for i, item in enumerate(items, 1):
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
            desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
            link = item.get("link", "")
            lines.append(f"{i}. [{title}]({link})")
            if desc:
                lines.append(f"   > {desc[:150]}")
        lines.append("")
    lines.append(f"---")
    lines.append(f"*자동 생성: {now.strftime('%Y-%m-%d %H:%M')}*")
    return "\n".join(lines)

def main():
    now = datetime.now()
    period, ref_date = determine_period()
    period_label = "월간" if period == "monthly" else "주간"
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    print(f"📰 {period_label} 뉴스 스크래핑 시작...")
    all_news = {}
    for label, query in QUERIES:
        items = fetch_naver_news(query, 10)
        if items:
            all_news[label] = items

    content = build_content(period, now, all_news)
    note_path = save_to_obsidian(period, content, now)

    # 텔레그램 요약 전송
    total = sum(len(v) for v in all_news.values())
    tg_lines = [f"📰 *{period_label} 뉴스 분석 완료*\n"]
    tg_lines.append(f"총 {total}건 수집\n")
    for label, items in all_news.items():
        tg_lines.append(f"*{label}* ({len(items)}건)")
        for item in items[:3]:
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")[:60]
            tg_lines.append(f"• {title}")
        tg_lines.append("")
    tg_lines.append(f"📁 옵시디언 저장 완료")
    tg_lines.append("\n⚛️ 자비스")

    message = "\n".join(tg_lines)
    if len(message) > 4000:
        message = message[:4000] + "\n..."
    sender.send_markdown(message)

if __name__ == "__main__":
    main()
