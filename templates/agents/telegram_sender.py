#!/usr/bin/env python3
"""
텔레그램 발송 에이전트 v2 (BaseAgent 기반)

모든 텔레그램 발송을 담당하는 재사용 가능한 에이전트
- 단일 책임: 텔레그램 발송만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import requests
import os
from typing import Optional, Union, Dict, Any
from pathlib import Path
from base_agent import BaseAgent


class TelegramSender(BaseAgent):
    """텔레그램 메시지 발송 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (bot_token, chat_id)
        """
        super().__init__("telegram_sender", config)

        self.bot_token = self.config.get("bot_token") or os.getenv("BOT_TOKEN", "")
        self.chat_id = self.config.get("chat_id") or os.getenv("CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        required_keys = ["message"]
        return all(key in data for key in required_keys)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        텔레그램 발송 처리

        Args:
            data: {
                "message": str,           # 필수: 메시지 내용
                "parse_mode": str,        # 선택: "HTML" 또는 "Markdown"
                "disable_preview": bool,  # 선택: 링크 미리보기 비활성화
                "type": str               # 선택: "message", "photo", "document"
            }

        Returns:
            {"success": bool, "message_id": str}
        """
        message_type = data.get("type", "message")

        if message_type == "photo":
            return self._send_photo(data)
        elif message_type == "document":
            return self._send_document(data)
        else:
            return self._send_message(data)

    def _send_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """메시지 발송 — 4096자 초과 시 자동 분할"""
        text = data["message"]
        parse_mode = data.get("parse_mode")
        disable_preview = data.get("disable_preview", True)

        # Telegram 최대 4096자 → 초과 시 4000자 단위로 분할
        LIMIT = 4000
        chunks = [text[i:i+LIMIT] for i in range(0, len(text), LIMIT)] if len(text) > LIMIT else [text]

        try:
            url = f"{self.base_url}/sendMessage"
            for i, chunk in enumerate(chunks):
                payload = {
                    "chat_id": self.chat_id,
                    "text": chunk,
                    "disable_web_page_preview": disable_preview
                }
                if parse_mode:
                    payload["parse_mode"] = parse_mode

                response = requests.post(url, data=payload, timeout=10)
                response.raise_for_status()

            return {"success": True, "type": "message", "chunks": len(chunks)}

        except Exception as e:
            raise Exception(f"텔레그램 전송 실패: {e}")

    def _send_photo(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """사진 발송"""
        try:
            url = f"{self.base_url}/sendPhoto"
            photo_path = data.get("photo_path")

            if not photo_path:
                raise ValueError("photo_path가 필요합니다")

            files = {"photo": open(photo_path, "rb")}
            payload = {"chat_id": self.chat_id}

            caption = data.get("caption")
            if caption:
                payload["caption"] = caption

            response = requests.post(url, files=files, data=payload, timeout=30)
            response.raise_for_status()

            return {"success": True, "type": "photo"}

        except Exception as e:
            raise Exception(f"사진 전송 실패: {e}")

    def _send_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """문서 발송"""
        try:
            url = f"{self.base_url}/sendDocument"
            file_path = data.get("file_path")

            if not file_path:
                raise ValueError("file_path가 필요합니다")

            files = {"document": open(file_path, "rb")}
            payload = {"chat_id": self.chat_id}

            caption = data.get("caption")
            if caption:
                payload["caption"] = caption

            response = requests.post(url, files=files, data=payload, timeout=30)
            response.raise_for_status()

            return {"success": True, "type": "document"}

        except Exception as e:
            raise Exception(f"문서 전송 실패: {e}")


# ── 편의 함수 ─────────────────────────────────────────────────────────────────

def _get_sender() -> "TelegramSender":
    """토큰을 자동으로 로드해 TelegramSender 인스턴스 반환.
    ~/.claude/.env → TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 사용.
    스크립트에서 직접 TelegramSender를 인스턴스화하지 말고 이 함수를 거칠 것.
    """
    from pathlib import Path as _Path
    try:
        from dotenv import load_dotenv as _load
        _load(_Path.home() / ".claude" / ".env")
    except ImportError:
        pass
    return TelegramSender(config={
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    })


def send_telegram(text: str, parse_mode: Optional[str] = None) -> bool:
    """텔레그램 메시지 발송 — 스크립트 공통 진입점.
    TelegramSender를 직접 쓰지 말고 이 함수를 사용할 것.
    API가 바뀌어도 이 함수만 수정하면 됨.
    """
    sender = _get_sender()
    result = sender.run({"message": text, "parse_mode": parse_mode, "type": "message"})
    return result.get("success", False)


def send_telegram_html(text: str) -> bool:
    """HTML 형식 텔레그램 발송"""
    return send_telegram(text, parse_mode="HTML")


def send_telegram_chunks(text: str, parse_mode: Optional[str] = None, max_len: int = 3900) -> bool:
    """긴 메시지를 자동 분할해서 발송"""
    if len(text) <= max_len:
        return send_telegram(text, parse_mode=parse_mode)
    sender = _get_sender()
    parts, current = [], ""
    for line in text.split("\n\n"):
        if len(current) + len(line) + 2 > max_len:
            parts.append(current.strip())
            current = line
        else:
            current += ("\n\n" + line) if current else line
    if current.strip():
        parts.append(current.strip())
    success = True
    for i, part in enumerate(parts, 1):
        prefix = f"[{i}/{len(parts)}]\n" if len(parts) > 1 else ""
        result = sender.run({"message": prefix + part, "parse_mode": parse_mode, "type": "message"})
        if not result.get("success", False):
            success = False
    return success


# 하위 호환 유지 (기존 코드 호환)
def send_message(text: str, parse_mode: Optional[str] = None) -> bool:
    """하위 호환용. send_telegram() 사용 권장."""
    return send_telegram(text, parse_mode)


def send_html(html: str) -> bool:
    """하위 호환용. send_telegram_html() 사용 권장."""
    return send_telegram_html(html)


def send_daily_report(title: str, content: str, sections: Optional[dict] = None) -> bool:
    """데일리 리포트 발송 (편의 함수)"""
    html = f"<b>{title}</b>\n\n{content}\n\n"

    if sections:
        for section_name, section_content in sections.items():
            html += f"━━━━━━━━━━━━━━━\n\n<b>{section_name}</b>\n{section_content}\n\n"

    return send_html(html)


def send_alert(title: str, message: str, emoji: str = "🚨") -> bool:
    """알림 발송 (편의 함수)"""
    html = f"{emoji} <b>{title}</b>\n\n{message}"
    return send_html(html)
