#!/usr/bin/env python3
"""공인중개사 퀴즈 - 하루 7회 (09:00~17:00) NotebookLM으로 기출문제 생성"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID

import re
from datetime import datetime
from telegram_sender import TelegramSender
from notebooklm_analyzer_v2 import NotebookLMAnalyzer

NOTEBOOK_ID = "6a1a4c9d-d2df-4610-8c45-105dc6837fbc"  # 공인중개사 1차 자료

PROMPT_GAERON = """김백중 기출문제(부동산학개론) 자료에서 기출문제 1문제를 출제해주세요.

형식:
[문제] 문제 내용

① 보기1
② 보기2
③ 보기3
④ 보기4
⑤ 보기5

[정답] 번호

[해설] 핵심 해설 (2-3줄)"""

PROMPT_MINBEOP = """김덕수 기출문제(민법) 자료에서 기출문제 1문제를 출제해주세요.

형식:
[문제] 문제 내용

① 보기1
② 보기2
③ 보기3
④ 보기4
⑤ 보기5

[정답] 번호

[해설] 핵심 해설 (2-3줄)"""


def clean_answer_text(text: str) -> str:
    text = re.sub(r'[①②③④⑤]\s*\.?\s*\d+\.\s*', lambda m: m.group(0)[:1] + ' ', text)
    text = re.sub(r'\s*\[[\d,\s\-]+\]', '', text)
    text = re.sub(r'\s{3,}', '  ', text)
    return text.strip()


def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)
    nb_analyzer = NotebookLMAnalyzer()

    print("🧠 공인중개사 퀴즈 생성 중...")

    gaeron_result = nb_analyzer.run({
        "operation": "ask",
        "notebook_id": NOTEBOOK_ID,
        "prompt": PROMPT_GAERON,
        "ask_timeout": 180
    })
    gaeron = clean_answer_text(gaeron_result.get("result", "❌ 개론 문제 생성 실패"))

    minbeop_result = nb_analyzer.run({
        "operation": "ask",
        "notebook_id": NOTEBOOK_ID,
        "prompt": PROMPT_MINBEOP,
        "ask_timeout": 180
    })
    minbeop = clean_answer_text(minbeop_result.get("result", "❌ 민법 문제 생성 실패"))

    message = (
        f"📚 *공인중개사 퀴즈* ({now.strftime('%H:%M')})\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏠 *부동산학개론*\n\n"
        f"{gaeron[:700] + chr(10) + '...' if len(gaeron) > 700 else gaeron}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚖️ *민법*\n\n"
        f"{minbeop[:700] + chr(10) + '...' if len(minbeop) > 700 else minbeop}\n\n"
        f"⚛️ 자비스"
    )
    success = sender.send_message(message)
    print(f"퀴즈 전송: {'성공' if success else '실패'} (개론 {len(gaeron)}자, 민법 {len(minbeop)}자)")


if __name__ == "__main__":
    main()
