#!/usr/bin/env python3
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH
"""데일리 뉴스 → 옵시디언 저장 - 매일 07:00"""
import requests
from datetime import datetime
from pathlib import Path

QUERIES = [
    ("부동산", "지식산업센터 부동산"),
    ("경제", "경제 금리"),
    ("AI기술", "AI 인공지능"),
    ("주식", "코스피 주식 시장"),
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
    year = now.year
    month = now.month
    day = now.day

    month_folder = f"{month:02d}월"
    folder_path = Path(VAULT_PATH) / "30. 자원 상자" / "뉴스" / str(year) / month_folder
    folder_path.mkdir(parents=True, exist_ok=True)

    filename = f"{year}-{month:02d}-{day:02d} 뉴스.md"
    note_path = folder_path / filename

    lines = [
        f"---",
        f"date: {year}-{month:02d}-{day:02d}",
        f"tags: [뉴스, daily-news]",
        f"---",
        f"",
        f"# {year}-{month:02d}-{day:02d} 뉴스 브리핑",
        f"",
    ]

    for label, query in QUERIES:
        items = fetch_naver_news(query, 5)
        if not items:
            continue
        lines.append(f"## 📌 {label}")
        for i, item in enumerate(items, 1):
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
            desc = item.get("description", "").replace("<b>", "").replace("</b>", "")
            link = item.get("link", "")
            lines.append(f"{i}. [{title}]({link})")
            if desc:
                lines.append(f"   > {desc[:120]}")
        lines.append("")

    lines.append(f"---")
    lines.append(f"*자동 생성: {now.strftime('%Y-%m-%d %H:%M')}*")

    note_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 데일리 뉴스 저장: {note_path}")

if __name__ == "__main__":
    main()
