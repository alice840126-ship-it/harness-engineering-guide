#!/usr/bin/env python3
"""공인중개사 퀴즈 - 하루 7회 (09:00~17:00) NotebookLM으로 기출문제 생성"""
import sys
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, BRAVE_API_KEY, VAULT_PATH, AGENTS_PATH

import asyncio
import re
from datetime import datetime
from telegram_sender import TelegramSender

NOTEBOOK_ID = "6a1a4c9d"  # 공인중개사 1차 자료

PROMPT = """공인중개사 1차 기출문제 1문제를 출제해주세요.

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
    """지문 숫자 제거 (①...1, ②...2 형태)"""
    text = re.sub(r'[①②③④⑤]\s*\.?\s*\d+\.\s*', lambda m: m.group(0)[:1] + ' ', text)
    text = re.sub(r'\s{3,}', '  ', text)
    return text.strip()

async def get_quiz() -> str:
    try:
        from notebooklm import NotebookLMClient
        client = await NotebookLMClient.from_storage()
        # notebook 선택
        notebooks = await client.notebooks.list()
        target = None
        for nb in notebooks:
            nb_id = getattr(nb, 'id', '') or ''
            if NOTEBOOK_ID in nb_id:
                target = nb
                break
        if not target:
            return "❌ 공인중개사 노트북을 찾을 수 없습니다"

        result = await asyncio.wait_for(
            client.chat.ask(target.id, PROMPT),
            timeout=180
        )
        answer = getattr(result, 'text', '') or str(result)
        answer = clean_answer_text(answer)
        if len(answer) > 1500:
            answer = answer[:1500] + "\n..."
        return answer
    except asyncio.TimeoutError:
        return "❌ NotebookLM 응답 시간 초과 (180초)"
    except Exception as e:
        return f"❌ 오류: {e}"

def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    print("🧠 공인중개사 퀴즈 생성 중...")
    quiz = asyncio.run(get_quiz())

    message = f"📚 *공인중개사 퀴즈* ({now.strftime('%H:%M')})\n\n{quiz}\n\n⚛️ 자비스"
    success = sender.send_message(message)
    print(f"퀴즈 전송: {'성공' if success else '실패'} ({len(quiz)}자)")

if __name__ == "__main__":
    main()
