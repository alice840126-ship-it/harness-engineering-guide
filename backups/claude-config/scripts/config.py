#!/usr/bin/env python3
"""공통 설정 로더 - 모든 스크립트에서 import해서 사용"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ~/.claude/.env 로드
ENV_FILE = Path.home() / ".claude" / ".env"
load_dotenv(ENV_FILE)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
VAULT_PATH = os.getenv(
    "OBSIDIAN_VAULT_PATH",
    "/Users/oungsooryu/Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"
)
AGENTS_PATH = os.getenv(
    "AGENTS_PATH",
    "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents"
)
