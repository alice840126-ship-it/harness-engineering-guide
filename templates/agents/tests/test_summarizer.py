#!/usr/bin/env python3
"""
Summarizer v2 단위 테스트
"""

import pytest
from summarizer import Summarizer


class TestSummarizer:
    """Summarizer 테스트"""

    def test_init(self):
        """초기화 테스트"""
        summarizer = Summarizer()
        assert summarizer.name == "summarizer"
        assert summarizer.max_sentences == 3

    def test_init_with_config(self):
        """설정과 함께 초기화"""
        config = {"max_sentences": 5, "max_length": 300}
        summarizer = Summarizer(config)
        assert summarizer.max_sentences == 5
        assert summarizer.max_length == 300

    def test_validate_input_text(self):
        """텍스트 요약 입력 검증"""
        summarizer = Summarizer()
        assert summarizer.validate_input({
            "operation": "text",
            "text": "test content"
        }) is True

    def test_validate_input_news(self):
        """뉴스 요약 입력 검증"""
        summarizer = Summarizer()
        assert summarizer.validate_input({
            "operation": "news",
            "news_list": []
        }) is True

    def test_validate_input_invalid(self):
        """잘못된 입력 검증"""
        summarizer = Summarizer()
        assert summarizer.validate_input({"operation": "text"}) is False

    def test_process_text_operation(self):
        """텍스트 요약 처리"""
        summarizer = Summarizer()
        result = summarizer.run({
            "operation": "text",
            "text": "This is a test. This is another test. This is the third test."
        })
        assert "summary" in result
        assert result["type"] == "text"

    def test_process_news_operation(self):
        """뉴스 요약 처리"""
        summarizer = Summarizer()
        news_list = [
            {"title": "뉴스 1", "link": "https://example.com/1"},
            {"title": "뉴스 2", "link": "https://example.com/2"}
        ]
        result = summarizer.run({
            "operation": "news",
            "news_list": news_list,
            "max_count": 5
        })
        assert "summary" in result
        assert result["type"] == "news"

    def test_process_empty_news(self):
        """빈 뉴스 처리"""
        summarizer = Summarizer()
        result = summarizer.run({
            "operation": "news",
            "news_list": []
        })
        assert result["summary"] == "뉴스 없음"

    def test_process_work_log_operation(self):
        """작업 로그 요약 처리"""
        summarizer = Summarizer()
        work_items = [
            {"time": "10:00", "description": "작업 1", "status": "완료"},
            {"time": "11:00", "description": "작업 2", "status": "진행중"}
        ]
        result = summarizer.run({
            "operation": "work_log",
            "work_items": work_items
        })
        assert "summary" in result
        assert result["type"] == "work_log"

    def test_process_bullet_points(self):
        """불렛 포인트 요약"""
        summarizer = Summarizer()
        result = summarizer.run({
            "operation": "bullet_points",
            "text": "Point one. Point two. Point three."
        })
        assert "summary" in result
        assert "•" in result["summary"]


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_summarize_text_signature(self):
        """summarize_text 함수 시그니처"""
        from summarizer import summarize_text
        assert callable(summarize_text)

    def test_summarize_news_signature(self):
        """summarize_news 함수 시그니처"""
        from summarizer import summarize_news
        assert callable(summarize_news)

    def test_summarize_work_log_signature(self):
        """summarize_work_log 함수 시그니처"""
        from summarizer import summarize_work_log
        assert callable(summarize_work_log)
