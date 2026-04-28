#!/usr/bin/env python3
"""
MultiPlatformSearcher v2 단위 테스트
"""

import pytest
from multi_platform_searcher import MultiPlatformSearcher


class TestMultiPlatformSearcher:
    """MultiPlatformSearcher 테스트"""

    def test_init(self):
        """초기화 테스트"""
        searcher = MultiPlatformSearcher()
        assert searcher.name == "multi_platform_searcher"

    def test_validate_input(self):
        """입력 검증"""
        searcher = MultiPlatformSearcher()
        assert searcher.validate_input({
            "operation": "naver",
            "keywords": ["test"]
        }) is True

    def test_process_naver(self):
        """네이버 검색 처리 (API 없으면 빈 결과)"""
        searcher = MultiPlatformSearcher()
        result = searcher.run({
            "operation": "naver",
            "keywords": ["test"]
        })
        assert "results" in result

    def test_is_korean(self):
        """한글 확인"""
        searcher = MultiPlatformSearcher()
        assert searcher.is_korean("한글 테스트") is True
        assert searcher.is_korean("English text") is False

    def test_get_stats(self):
        """통계 확인"""
        searcher = MultiPlatformSearcher()
        stats = searcher.get_stats()
        assert "runs" in stats
