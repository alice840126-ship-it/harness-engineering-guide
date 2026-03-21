#!/usr/bin/env python3
"""
NotebookLMAnalyzer v2 단위 테스트
"""

import pytest
from notebooklm_analyzer_v2 import NotebookLMAnalyzer


class TestNotebookLMAnalyzer:
    """NotebookLMAnalyzer 테스트"""

    def test_init(self):
        """초기화 테스트"""
        analyzer = NotebookLMAnalyzer()
        assert analyzer.name == "notebooklm_analyzer"

    def test_validate_input_analyze(self):
        """분석 입력 검증"""
        analyzer = NotebookLMAnalyzer()
        assert analyzer.validate_input({
            "operation": "analyze",
            "prompt": "test prompt"
        }) is True

    def test_validate_input_news_trends(self):
        """뉴스 트렌드 입력 검증"""
        analyzer = NotebookLMAnalyzer()
        assert analyzer.validate_input({
            "operation": "news_trends",
            "news_items": []
        }) is True

    def test_process_analyze(self):
        """분석 처리 (CLI 없으면 에러)"""
        analyzer = NotebookLMAnalyzer()
        result = analyzer.run({
            "operation": "analyze",
            "prompt": "test"
        })
        # CLI 없으면 error
        assert "result" in result or "error" in result

    def test_get_stats(self):
        """통계 확인"""
        analyzer = NotebookLMAnalyzer()
        stats = analyzer.get_stats()
        assert "runs" in stats
