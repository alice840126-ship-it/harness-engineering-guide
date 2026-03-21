#!/usr/bin/env python3
"""
DuplicateFilter v2 단위 테스트
"""

import pytest
import tempfile
from pathlib import Path
from duplicate_filter_v2 import DuplicateFilter


class TestDuplicateFilter:
    """DuplicateFilter 테스트"""

    def test_init(self):
        """초기화 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.json"
            filter_obj = DuplicateFilter({"db_path": db_path})
            assert filter_obj.name == "duplicate_filter"

    def test_validate_input_check(self):
        """체크 입력 검증"""
        filter_obj = DuplicateFilter()
        assert filter_obj.validate_input({
            "operation": "check",
            "item": "test"
        }) is True

    def test_validate_input_filter(self):
        """필터 입력 검증"""
        filter_obj = DuplicateFilter()
        assert filter_obj.validate_input({
            "operation": "filter",
            "items": ["a", "b", "c"]
        }) is True

    def test_process_check(self):
        """체크 처리"""
        filter_obj = DuplicateFilter()
        result = filter_obj.run({
            "operation": "check",
            "item": "test_item"
        })
        assert "is_duplicate" in result

    def test_process_add(self):
        """추가 처리"""
        filter_obj = DuplicateFilter()
        result = filter_obj.run({
            "operation": "add",
            "item": "test_item"
        })
        assert "success" in result

    def test_process_stats(self):
        """통계 처리"""
        filter_obj = DuplicateFilter()
        result = filter_obj.run({"operation": "stats"})
        assert "total_items" in result
