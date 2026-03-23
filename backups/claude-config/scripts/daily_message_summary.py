#!/usr/bin/env python3
"""문자 요약 - 매일 17:00 오늘 받은 문자 요약 후 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import subprocess
from datetime import datetime
from telegram_sender import TelegramSender

OSASCRIPT = """
tell application "Messages"
    set today to current date
    set todayStart to today - (time of today)
    set msgList to ""
    set chatCount to 0
    repeat with aChat in chats
        try
            repeat with aMsg in messages of aChat
                if date sent of aMsg > todayStart then
                    set senderName to ""
                    try
                        set senderName to name of sender of aMsg
                    end try
                    if senderName is "" then
                        set senderName to handle of sender of aMsg
                    end if
                    set msgContent to content of aMsg
                    if length of msgContent > 100 then
                        set msgContent to (text 1 thru 100 of msgContent) & "..."
                    end if
                    set msgList to msgList & senderName & ": " & msgContent & "\\n"
                    set chatCount to chatCount + 1
                end if
            end repeat
        end try
    end repeat
    if chatCount = 0 then
        return "오늘 받은 문자 없음"
    end if
    return msgList
end tell
"""

def get_messages() -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", OSASCRIPT],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return f"문자 읽기 실패: {result.stderr.strip()[:100]}"
    except Exception as e:
        return f"오류: {e}"

def send_in_chunks(sender: TelegramSender, header: str, body: str):
    MAX = 3900
    full = header + body
    if len(full) <= MAX:
        sender.send_message(full)
        return
    # 분할 전송
    sender.send_message(header)
    lines = body.split("\n")
    chunk = ""
    part = 1
    for line in lines:
        if len(chunk) + len(line) + 1 > MAX:
            sender.send_message(f"[{part}]\n{chunk.strip()}")
            part += 1
            chunk = ""
        chunk += line + "\n"
    if chunk.strip():
        sender.send_message(f"[{part}]\n{chunk.strip()}")

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    messages = get_messages()
    header = f"📱 {now.strftime('%m월 %d일')} 오늘 문자 요약\n\n"
    footer = "\n\n⚛️ 자비스"

    send_in_chunks(sender, header, messages + footer)
    print(f"✅ 문자 요약 전송 완료")

if __name__ == "__main__":
    main()
