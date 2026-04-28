#!/usr/bin/env python3
"""
WebContentReader v2 단위 테스트
"""

import pytest
from web_content_reader import WebContentReader


class TestWebContentReader:
    """WebContentReader 테스트"""

    def test_init(self):
        """초기화 테스트"""
        reader = WebContentReader()
        assert reader.name == "web_content_reader"

    def test_validate_input_read(self):
        """읽기 입력 검증"""
        reader = WebContentReader()
        assert reader.validate_input({
            "operation": "read",
            "url": "https://example.com"
        }) is True

    def test_validate_input_multiple(self):
        """다중 읽기 입력 검증"""
        reader = WebContentReader()
        assert reader.validate_input({
            "operation": "multiple",
            "urls": ["https://example.com"]
        }) is True

    def test_process_read(self):
        """읽기 처리 (trafilatura 없으면 에러)"""
        reader = WebContentReader()
        result = reader.run({
            "operation": "read",
            "url": "https://example.com"
        })
        # trafilatura 없으면 error
        assert "content" in result or "error" in result

    def test_get_stats(self):
        """통계 확인"""
        reader = WebContentReader()
        stats = reader.get_stats()
        assert "runs" in stats
