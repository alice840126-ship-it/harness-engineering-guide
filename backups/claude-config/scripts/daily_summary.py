#!/usr/bin/env python3
"""일일 요약 - 매일 23:00 오늘 shared_context.md 작업 요약 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

from datetime import datetime
from pathlib import Path
from telegram_sender import TelegramSender

SHARED_CONTEXT = Path("/Users/oungsooryu/.claude-unified/shared_context.md")

def get_today_logs() -> list:
    if not SHARED_CONTEXT.exists():
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    today_logs = []
    for line in SHARED_CONTEXT.read_text(encoding="utf-8").splitlines():
        if today in line and line.strip().startswith("-"):
            log = line.strip().lstrip("- ").strip()
            if log:
                today_logs.append(log)
    return today_logs

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    logs = get_today_logs()
    lines = [f"🌙 *{now.strftime('%m월 %d일')} 오늘 요약*\n"]

    if logs:
        lines.append(f"총 {len(logs)}건 작업\n")
        for i, log in enumerate(logs[-10:], 1):  # 최근 10개
            truncated = log[:120] + "..." if len(log) > 120 else log
            lines.append(f"{i}. {truncated}")
    else:
        lines.append("오늘 기록된 작업 없음")

    lines.append("\n⚛️ 자비스 — 오늘도 수고했습니다!")

    message = "\n".join(lines)
    success = sender.send_markdown(message)
    print(f"일일 요약 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
