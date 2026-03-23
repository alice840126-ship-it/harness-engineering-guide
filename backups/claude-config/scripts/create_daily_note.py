#!/usr/bin/env python3
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH
"""데일리 노트 생성 - 매일 07:00 옵시디언 월별 폴더에 생성"""
import os
from datetime import datetime
from pathlib import Path

def create_daily_note():
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    weekday = weekdays[now.weekday()]

    month_folder = f"{month:02d}월"
    folder_path = Path(VAULT_PATH) / "00. In box" / str(year) / month_folder
    folder_path.mkdir(parents=True, exist_ok=True)

    filename = f"{year}-{month:02d}-{day:02d}.md"
    note_path = folder_path / filename

    if note_path.exists():
        print(f"이미 존재: {note_path}")
        return

    content = f"""---
date: {year}-{month:02d}-{day:02d}
day: {weekday}요일
tags: [daily-note, {year}년]
---

# {year}-{month:02d}-{day:02d} {weekday}요일

## 📅 오늘의 일정
-

## ✅ 오늘 할 일
- [ ]
- [ ]
- [ ]

## 💼 업무 메모

## 💡 인사이트 / 배운 것

## 🔗 관련 노트

---
*자동 생성: {now.strftime("%Y-%m-%d %H:%M")}*
"""

    note_path.write_text(content, encoding="utf-8")
    print(f"✅ 데일리 노트 생성: {note_path}")

if __name__ == "__main__":
    create_daily_note()
