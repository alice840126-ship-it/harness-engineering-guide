#!/usr/bin/env python3
"""내일 일정 - 매일 18:00 구글 캘린더 내일 일정 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import subprocess
from datetime import datetime, timedelta
from telegram_sender import TelegramSender

def get_tomorrow_schedule() -> str:
    try:
        result = subprocess.run(
            ["gog", "tomorrow"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip() if result.stdout.strip() else "내일 일정 없음"
    except Exception as e:
        return f"일정 조회 실패: {e}"

def main():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    schedule = get_tomorrow_schedule()
    message = f"📅 *내일 {tomorrow.strftime('%m월 %d일')} 일정*\n\n{schedule}\n\n⚛️ 자비스"

    success = sender.send_markdown(message)
    print(f"내일 일정 전송: {'성공' if success else '실패'}")

if __name__ == "__main__":
    main()
