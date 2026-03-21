#!/usr/bin/env python3
"""
MultiLocationRecorder v2 단위 테스트
"""

import pytest
from multi_location_recorder_v2 import MultiLocationRecorder


class TestMultiLocationRecorder:
    """MultiLocationRecorder 테스트"""

    def test_init(self):
        """초기화 테스트"""
        recorder = MultiLocationRecorder()
        assert recorder.name == "multi_location_recorder"

    def test_validate_input(self):
        """입력 검증"""
        recorder = MultiLocationRecorder()
        assert recorder.validate_input({
            "content": "test content"
        }) is True

    def test_process(self):
        """기록 처리"""
        recorder = MultiLocationRecorder()
        result = recorder.run({
            "content": "테스트 기록입니다"
        })
        assert "results" in result
        assert "success_count" in result

    def test_get_stats(self):
        """통계 확인"""
        recorder = MultiLocationRecorder()
        stats = recorder.get_stats()
        assert "runs" in stats
