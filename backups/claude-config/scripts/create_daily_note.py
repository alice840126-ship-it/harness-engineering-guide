#!/usr/bin/env python3
"""데일리 노트 생성 - 매일 07:00 옵시디언 월별 폴더에 생성 + 오늘 일정 주입"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
from config import VAULT_PATH

import subprocess
from datetime import datetime
from pathlib import Path


def get_today_schedule() -> str:
    try:
        result = subprocess.run(
            ["gog", "today"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if not output:
            return "- 일정 없음"
        # 각 줄을 "- " 리스트 형식으로 변환
        lines = [f"- {line.strip()}" if not line.strip().startswith("-") else line.strip()
                 for line in output.splitlines() if line.strip()]
        return "\n".join(lines) if lines else "- 일정 없음"
    except Exception as e:
        return f"- 일정 조회 실패: {e}"


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

    schedule = get_today_schedule()

    content = f"""---
date: {year}-{month:02d}-{day:02d}
day: {weekday}요일
tags: [daily-note, {year}년]
---

# {year}-{month:02d}-{day:02d} {weekday}요일

## 📅 오늘의 일정
{schedule}

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
