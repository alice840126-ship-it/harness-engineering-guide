#!/usr/bin/env python3
"""
TelegramSender v2 단위 테스트
"""

import pytest
from telegram_sender_v2 import TelegramSender


class TestTelegramSender:
    """TelegramSender 테스트"""

    def test_init(self):
        """초기화 테스트"""
        sender = TelegramSender()
        assert sender.name == "telegram_sender"
        assert sender.bot_token != "" or sender.chat_id != ""

    def test_init_with_config(self):
        """설정과 함께 초기화"""
        config = {
            "bot_token": "test_token",
            "chat_id": "test_chat"
        }
        sender = TelegramSender(config)
        assert sender.bot_token == "test_token"
        assert sender.chat_id == "test_chat"

    def test_validate_input_valid(self):
        """유효한 입력 검증"""
        sender = TelegramSender()
        assert sender.validate_input({"message": "test"}) is True

    def test_validate_input_invalid(self):
        """잘못된 입력 검증"""
        sender = TelegramSender()
        assert sender.validate_input({}) is False

    def test_process_message_type(self):
        """메시지 타입 처리"""
        sender = TelegramSender()
        # 실제 전송은 안 하고 입력 검증만 테스트
        assert sender.validate_input({
            "message": "test",
            "type": "message"
        }) is True

    def test_process_photo_type(self):
        """사진 타입 처리"""
        sender = TelegramSender()
        assert sender.validate_input({
            "message": "test",
            "type": "photo",
            "photo_path": "/tmp/test.jpg"
        }) is True

    def test_process_document_type(self):
        """문서 타입 처리"""
        sender = TelegramSender()
        assert sender.validate_input({
            "message": "test",
            "type": "document",
            "file_path": "/tmp/test.pdf"
        }) is True

    def test_get_stats(self):
        """통계 확인"""
        sender = TelegramSender()
        stats = sender.get_stats()
        assert "runs" in stats
        assert "errors" in stats
        assert stats["runs"] == 0


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_send_message_signature(self):
        """send_message 함수 시그니처"""
        from telegram_sender_v2 import send_message
        # 함수가 존재하는지 확인
        assert callable(send_message)

    def test_send_html_signature(self):
        """send_html 함수 시그니처"""
        from telegram_sender_v2 import send_html
        assert callable(send_html)

    def test_send_daily_report_signature(self):
        """send_daily_report 함수 시그니처"""
        from telegram_sender_v2 import send_daily_report
        assert callable(send_daily_report)

    def test_send_alert_signature(self):
        """send_alert 함수 시그니처"""
        from telegram_sender_v2 import send_alert
        assert callable(send_alert)
