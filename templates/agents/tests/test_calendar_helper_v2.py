#!/usr/bin/env python3
"""
CalendarHelper v2 단위 테스트
"""

import pytest
from calendar_helper_v2 import CalendarHelper


class TestCalendarHelper:
    """CalendarHelper 테스트"""

    def test_init(self):
        """초기화 테스트"""
        helper = CalendarHelper()
        assert helper.name == "calendar_helper"

    def test_init_with_config(self):
        """설정과 함께 초기화"""
        config = {"gog_path": "/custom/path/gog"}
        helper = CalendarHelper(config)
        assert helper.gog_path == "/custom/path/gog"

    def test_validate_input_valid(self):
        """유효한 입력 검증"""
        helper = CalendarHelper()
        assert helper.validate_input({"operation": "today"}) is True

    def test_validate_input_invalid(self):
        """잘못된 입력 검증"""
        helper = CalendarHelper()
        assert helper.validate_input({}) is False

    def test_process_today_operation(self):
        """오늘 일정 처리"""
        helper = CalendarHelper()
        result = helper.run({"operation": "today"})
        assert "events" in result
        assert "formatted" in result
        assert result["operation"] == "today"

    def test_process_tomorrow_operation(self):
        """내일 일정 처리"""
        helper = CalendarHelper()
        result = helper.run({"operation": "tomorrow"})
        assert "events" in result
        assert result["operation"] == "tomorrow"

    def test_process_week_operation(self):
        """이번 주 일정 처리"""
        helper = CalendarHelper()
        result = helper.run({"operation": "week"})
        assert "events" in result
        assert "formatted" in result
        assert result["operation"] == "week"

    def test_process_custom_operation(self):
        """사용자 지정 날짜 처리"""
        helper = CalendarHelper()
        result = helper.run({
            "operation": "custom",
            "days_offset": 7
        })
        assert "events" in result
        assert result["operation"] == "custom"

    def test_format_events_for_briefing_empty(self):
        """빈 이벤트 포맷팅"""
        helper = CalendarHelper()
        formatted = helper.format_events_for_briefing([], "오늘 ")
        assert "없음" in formatted

    def test_format_events_for_briefing_with_events(self):
        """이벤트 포맷팅"""
        helper = CalendarHelper()
        events = [
            {
                "summary": "테스트 미팅",
                "start": {"date": "2026-03-21"},
                "end": {"date": "2026-03-21"}
            }
        ]
        formatted = helper.format_events_for_briefing(events, "오늘 ")
        assert "테스트 미팅" in formatted

    def test_get_stats(self):
        """통계 확인"""
        helper = CalendarHelper()
        stats = helper.get_stats()
        assert "runs" in stats
        assert "errors" in stats


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_get_todays_schedule_signature(self):
        """get_todays_schedule 함수 시그니처"""
        from calendar_helper_v2 import get_todays_schedule
        assert callable(get_todays_schedule)

    def test_get_tomorrows_schedule_signature(self):
        """get_tomorrows_schedule 함수 시그니처"""
        from calendar_helper_v2 import get_tomorrows_schedule
        assert callable(get_tomorrows_schedule)

    def test_get_this_week_schedule_signature(self):
        """get_this_week_schedule 함수 시그니처"""
        from calendar_helper_v2 import get_this_week_schedule
        assert callable(get_this_week_schedule)
