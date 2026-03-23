#!/usr/bin/env python3
"""작업 요약 - 매일 23:00 work_log.json 오늘 작업 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import json
from datetime import datetime
from pathlib import Path
from telegram_sender import TelegramSender

WORK_LOG = Path("/Users/oungsooryu/.claude/work_log.json")

def get_today_work() -> list:
    if not WORK_LOG.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        data = json.loads(WORK_LOG.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("entries", [])
        today_entries = [
            e for e in entries
            if isinstance(e, dict) and e.get("date", "").startswith(today)
        ]
        return today_entries
    except Exception as e:
        print(f"work_log 읽기 실패: {e}")
        return []

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    entries = get_today_work()
    lines = [f"📋 *{now.strftime('%m월 %d일')} 작업 로그*\n"]

    if entries:
        lines.append(f"총 {len(entries)}건\n")
        for i, entry in enumerate(entries[-10:], 1):
            desc = entry.get("description", entry.get("content", str(entry)))[:120]
            lines.append(f"{i}. {desc}")
    else:
        lines.append("오늘 기록된 작업 없음")

    lines.append("\n⚛️ 자비스")

    message = "\n".join(lines)
    success = sender.send_markdown(message)
    print(f"작업 요약 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
