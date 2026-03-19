#!/usr/bin/env python3
"""
텔레그램 발송 에이전트

모든 텔레그램 발송을 담당하는 재사용 가능한 에이전트
"""

import requests
import os
from typing import Optional, Union
from pathlib import Path


class TelegramSender:
    """텔레그램 메시지 발송 에이전트"""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        초기화

        Args:
            bot_token: 텔레그램 봇 토큰 (None이면 환경변수에서 읽기)
            chat_id: 채팅 ID (None이면 환경변수에서 읽기)
        """
        self.bot_token = bot_token or os.getenv("BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(
        self,
        text: str,
        parse_mode: Optional[str] = None,
        disable_preview: bool = True
    ) -> bool:
        """
        기본 메시지 발송

        Args:
            text: 메시지 내용
            parse_mode: "HTML" 또는 "Markdown"
            disable_preview: 링크 미리보기 비활성화

        Returns:
            성공 여부
        """
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": disable_preview
            }

            if parse_mode:
                data["parse_mode"] = parse_mode

            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()

            return True

        except Exception as e:
            print(f"텔레그램 전송 실패: {e}")
            return False

    def send_html(self, html: str, disable_preview: bool = True) -> bool:
        """
        HTML 포맷 메시지 발송

        Args:
            html: HTML 포맷 텍스트
            disable_preview: 링크 미리보기 비활성화

        Returns:
            성공 여부
        """
        return self.send_message(html, parse_mode="HTML", disable_preview=disable_preview)

    def send_markdown(self, markdown: str, disable_preview: bool = True) -> bool:
        """
        마크다운 포맷 메시지 발송

        Args:
            markdown: 마크다운 포맷 텍스트
            disable_preview: 링크 미리보기 비활성화

        Returns:
            성공 여부
        """
        return self.send_message(markdown, parse_mode="Markdown", disable_preview=disable_preview)

    def send_photo(self, photo_path: Union[str, Path], caption: Optional[str] = None) -> bool:
        """
        사진 발송

        Args:
            photo_path: 사진 파일 경로
            caption: 캡션 (선택)

        Returns:
            성공 여부
        """
        try:
            url = f"{self.base_url}/sendPhoto"
            files = {"photo": open(photo_path, "rb")}
            data = {"chat_id": self.chat_id}

            if caption:
                data["caption"] = caption

            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()

            return True

        except Exception as e:
            print(f"사진 전송 실패: {e}")
            return False

    def send_document(self, file_path: Union[str, Path], caption: Optional[str] = None) -> bool:
        """
        문서 발송

        Args:
            file_path: 파일 경로
            caption: 캡션 (선택)

        Returns:
            성공 여부
        """
        try:
            url = f"{self.base_url}/sendDocument"
            files = {"document": open(file_path, "rb")}
            data = {"chat_id": self.chat_id}

            if caption:
                data["caption"] = caption

            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()

            return True

        except Exception as e:
            print(f"문서 전송 실패: {e}")
            return False

    def send_daily_report(
        self,
        title: str,
        content: str,
        sections: Optional[dict] = None
    ) -> bool:
        """
        데일리 리포트 발송 (HTML 포맷)

        Args:
            title: 리포트 제목
            content: 주요 내용
            sections: 섹션별 데이터 {"섹션명": 내용}

        Returns:
            성공 여부
        """
        html = f"<b>{title}</b>\n\n"
        html += f"{content}\n\n"

        if sections:
            for section_name, section_content in sections.items():
                html += f"━━━━━━━━━━━━━━━\n\n"
                html += f"<b>{section_name}</b>\n"
                html += f"{section_content}\n\n"

        return self.send_html(html)

    def send_alert(
        self,
        title: str,
        message: str,
        emoji: str = "🚨"
    ) -> bool:
        """
        알림 발송

        Args:
            title: 알림 제목
            message: 알림 내용
            emoji: 이모지

        Returns:
            성공 여부
        """
        text = f"{emoji} <b>{title}</b>\n\n{message}"
        return self.send_html(text)

    def send_news(
        self,
        category: str,
        news_list: list,
        max_count: int = 5
    ) -> bool:
        """
        뉴스 발송

        Args:
            category: 뉴스 카테고리 (예: "경제", "부동산")
            news_list: 뉴스 기사 리스트 [{"title": ..., "link": ...}]
            max_count: 최대 전송 개수

        Returns:
            성공 여부
        """
        html = f"📰 <b>{category} 뉴스</b>\n\n"

        for i, news in enumerate(news_list[:max_count], 1):
            title = news.get("title", news.get("제목", ""))
            link = news.get("link", news.get("url", "")) or news.get("링크", "")

            html += f"{i}. {title}\n"

            if link:
                html += f"   {link}\n"

            html += "\n"

        return self.send_html(html)


# 싱글톤 인스턴스 (기본값 사용)
_default_sender = None


def get_sender() -> TelegramSender:
    """기본 텔레그램 발송자 인스턴스 반환"""
    global _default_sender
    if _default_sender is None:
        _default_sender = TelegramSender()
    return _default_sender


# 편의 함수
def send_message(text: str, parse_mode: Optional[str] = None) -> bool:
    """메시지 발송 (편의 함수)"""
    return get_sender().send_message(text, parse_mode)


def send_html(html: str) -> bool:
    """HTML 발송 (편의 함수)"""
    return get_sender().send_html(html)


def send_daily_report(title: str, content: str, sections: Optional[dict] = None) -> bool:
    """데일리 리포트 발송 (편의 함수)"""
    return get_sender().send_daily_report(title, content, sections)


def send_alert(title: str, message: str, emoji: str = "🚨") -> bool:
    """알림 발송 (편의 함수)"""
    return get_sender().send_alert(title, message, emoji)
