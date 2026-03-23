#!/usr/bin/env python3
"""아침 일정 - 매일 07:00 구글 캘린더 오늘 일정 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import subprocess
from datetime import datetime
from telegram_sender import TelegramSender

def get_today_schedule() -> str:
    try:
        result = subprocess.run(
            ["gog", "today"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() if result.stdout.strip() else "오늘 일정 없음"
    except Exception as e:
        return f"일정 조회 실패: {e}"

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    schedule = get_today_schedule()
    message = f"📅 *{now.strftime('%m월 %d일')} 오늘 일정*\n\n{schedule}\n\n⚛️ 자비스"

    success = sender.send_markdown(message)
    print(f"아침 일정 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
