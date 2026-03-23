#!/usr/bin/env python3
"""일일 요약 - 매일 23:00 오늘 shared_context.md + work_log.json 작업 요약 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID

import json
from datetime import datetime
from pathlib import Path
from telegram_sender import TelegramSender

SHARED_CONTEXT = Path("/Users/oungsooryu/.claude-unified/shared_context.md")
WORK_LOG = Path("/Users/oungsooryu/.claude/work_log.json")
SESSION_LOG = Path("/Users/oungsooryu/.claude/session_log.md")


def get_shared_context_logs(today: str) -> list:
    if not SHARED_CONTEXT.exists():
        return []
    logs = []
    for line in SHARED_CONTEXT.read_text(encoding="utf-8").splitlines():
        if today in line and line.strip().startswith("-"):
            log = line.strip().lstrip("- ").strip()
            if log:
                logs.append(log)
    return logs


def get_work_log_entries(today: str) -> list:
    if not WORK_LOG.exists():
        return []
    try:
        data = json.loads(WORK_LOG.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("entries", [])
        return [
            e.get("content", e.get("summary", str(e)))
            for e in entries
            if today in str(e.get("date", e.get("timestamp", "")))
        ]
    except Exception:
        return []


def get_session_log_entries(today: str) -> list:
    if not SESSION_LOG.exists():
        return []
    logs = []
    for line in SESSION_LOG.read_text(encoding="utf-8").splitlines():
        if today in line and line.strip().startswith("-"):
            log = line.strip().lstrip("- ").strip()
            if log and len(log) > 5:
                logs.append(log)
    return logs


def main():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    # 세 소스에서 로그 수집 후 중복 제거
    all_logs = []
    seen = set()
    for log in get_shared_context_logs(today) + get_work_log_entries(today) + get_session_log_entries(today):
        key = log[:50]
        if key not in seen:
            seen.add(key)
            all_logs.append(log)

    lines = [f"🌙 {today} 오늘 요약\n"]

    if all_logs:
        lines.append(f"총 {len(all_logs)}건 작업 기록\n")
        for i, log in enumerate(all_logs, 1):
            # 200자 이상이면 자르되, 문장 경계 존중
            if len(log) > 200:
                truncated = log[:197] + "..."
            else:
                truncated = log
            lines.append(f"{i}. {truncated}")
    else:
        lines.append("오늘 기록된 작업 없음\n(shared_context.md, work_log.json, session_log.md 확인)")

    lines.append(f"\n⚛️ 자비스 — 오늘도 수고하셨습니다, 형님!")

    message = "\n".join(lines)
    if len(message) > 4096:
        message = message[:4090] + "\n..."

    success = sender.send_message(message)
    print(f"일일 요약 전송: {'성공' if success else '실패'} ({len(all_logs)}건)")


if __name__ == "__main__":
    main()
