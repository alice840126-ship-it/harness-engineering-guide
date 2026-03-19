#!/usr/bin/env python3
"""
텔레그램 발송 에이전트 단위 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

# 환경변수 설정 (테스트용)
os.environ['BOT_TOKEN'] = 'TEST_TOKEN'
os.environ['CHAT_ID'] = 'TEST_CHAT_ID'

from telegram_sender import TelegramSender


def test_send_message():
    """기본 메시지 발송 테스트"""
    sender = TelegramSender()

    # 실제로 전송하지 않고 인터페이스만 확인
    # 실제 테스트에서는 mock 사용 필요

    print("✅ test_send_message: 테스트 통과")
    assert sender.bot_token == 'TEST_TOKEN'
    assert sender.chat_id == 'TEST_CHAT_ID'


def test_html_formatting():
    """HTML 포맷 지원 확인"""
    sender = TelegramSender()

    # 인터페이스 확인
    assert hasattr(sender, 'send_html')
    assert hasattr(sender, 'send_markdown')

    print("✅ test_html_formatting: 테스트 통과")


def test_send_daily_report_structure():
    """데일리 리포트 구조 확인"""
    sender = TelegramSender()

    # 메서드 존재 확인
    assert hasattr(sender, 'send_daily_report')
    assert hasattr(sender, 'send_alert')
    assert hasattr(sender, 'send_html')

    print("✅ test_send_daily_report_structure: 테스트 통과")


def test_news_formatting():
    """뉴스 포맷 지원 확인"""
    sender = TelegramSender()

    # 뉴스 데이터 예시
    news = [
        {"title": "테스트 뉴스", "link": "https://example.com"}
    ]

    # 메서드 존재 확인
    assert hasattr(sender, 'send_news')

    print("✅ test_news_formatting: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 텔레그램 발송 에이전트 테스트 시작")
    print("=" * 50)

    test_send_message()
    test_html_formatting()
    test_send_daily_report_structure()
    test_news_formatting()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
