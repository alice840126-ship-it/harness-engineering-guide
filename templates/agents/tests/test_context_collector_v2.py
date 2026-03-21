#!/usr/bin/env python3
"""
ContextCollector v2 단위 테스트
"""

import pytest
from context_collector_v2 import ContextCollector


class TestContextCollector:
    """ContextCollector 테스트"""

    def test_init(self):
        """초기화 테스트"""
        collector = ContextCollector()
        assert collector.name == "context_collector"

    def test_validate_input_collect(self):
        """컬렉트 입력 검증"""
        collector = ContextCollector()
        assert collector.validate_input({"operation": "collect"}) is True

    def test_validate_input_save(self):
        """저장 입력 검증"""
        collector = ContextCollector()
        assert collector.validate_input({
            "operation": "save",
            "findings": {}
        }) is True

    def test_process_collect(self):
        """컬렉트 처리"""
        collector = ContextCollector()
        result = collector.run({"operation": "collect", "limit": 10})
        assert "findings" in result
        assert result["operation"] == "collect"

    def test_get_stats(self):
        """통계 확인"""
        collector = ContextCollector()
        stats = collector.get_stats()
        assert "runs" in stats
