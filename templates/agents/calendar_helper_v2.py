#!/usr/bin/env python3
"""
구글 캘린더 도우미 에이전트 v2 (BaseAgent 기반)

gog CLI를 사용하여 Google Calendar 일정 조회
- 단일 책임: 캘린더 일정 조회만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import subprocess
import json
import datetime
from dateutil import parser
from typing import List, Dict, Optional, Any
from base_agent import BaseAgent


class CalendarHelper(BaseAgent):
    """구글 캘린더 도우미 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (gog_path)
        """
        super().__init__("calendar_helper", config)

        self.gog_path = self.config.get("gog_path", "/opt/homebrew/bin/gog")

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        return "operation" in data

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        캘린더 일정 조회 처리

        Args:
            data: {
                "operation": str,    # "today", "tomorrow", "week", "custom"
                "days_offset": int,  # custom용 날짜 오프셋
                "format": bool       # 브리핑용 포맷팅 여부
            }

        Returns:
            {"events": list, "formatted": str, "operation": str}
        """
        operation = data.get("operation", "today")

        if operation == "today":
            return self._get_today_events(data)
        elif operation == "tomorrow":
            return self._get_tomorrow_events(data)
        elif operation == "week":
            return self._get_week_events(data)
        elif operation == "custom":
            return self._get_custom_events(data)
        else:
            return {"events": [], "error": "잘못된 operation"}

    def _get_today_events(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """오늘 일정"""
        events = self.get_events(days_offset=0)
        formatted = self.format_events_for_briefing(events, "오늘 ")

        return {
            "events": events,
            "formatted": formatted,
            "count": len(events),
            "operation": "today"
        }

    def _get_tomorrow_events(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """내일 일정"""
        events = self.get_events(days_offset=1)
        formatted = self.format_events_for_briefing(events, "내일 ")

        return {
            "events": events,
            "formatted": formatted,
            "count": len(events),
            "operation": "tomorrow"
        }

    def _get_week_events(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """이번 주 일정"""
        try:
            cmd = [self.gog_path, "calendar", "events", "--week", "--all", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return {
                    "events": [],
                    "formatted": "📅 이번 주 일정: 조회 실패\n",
                    "operation": "week"
                }

            data_json = json.loads(result.stdout)
            events = data_json.get("events", [])

            # 오늘 날짜와 지난 일정 필터링
            today = datetime.date.today()
            today_start = datetime.datetime.combine(today, datetime.time.min).timestamp() * 1000

            filtered_events = []
            for event in events:
                start_info = event.get("start", {})

                if "date" in start_info:
                    event_date = parser.parse(start_info["date"])
                    event_datetime = datetime.datetime.combine(event_date, datetime.time.min)
                elif "dateTime" in start_info:
                    start_ms = start_info.get("dateTime", "")
                    if start_ms:
                        start_dt = parser.isoparse(start_ms)
                        event_datetime = start_dt
                else:
                    continue

                if event_datetime.timestamp() * 1000 < today_start:
                    continue

                if event_datetime.date() == today:
                    continue

                filtered_events.append(event)

            formatted = self.format_events_for_briefing(
                filtered_events, "이번 주 ", show_date=True, korean_weekday=True
            )

            return {
                "events": filtered_events,
                "formatted": formatted,
                "count": len(filtered_events),
                "operation": "week"
            }

        except Exception as e:
            return {
                "events": [],
                "formatted": f"📅 이번 주 일정: 조회 실패 ({e})\n",
                "operation": "week"
            }

    def _get_custom_events(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """사용자 지정 날짜 일정"""
        days_offset = data.get("days_offset", 0)
        events = self.get_events(days_offset=days_offset)

        date_str = (
            "오늘" if days_offset == 0 else
            "내일" if days_offset == 1 else
            f"{abs(days_offset)}일 {'후' if days_offset > 0 else '전'}"
        )

        formatted = self.format_events_for_briefing(events, f"{date_str} ")

        return {
            "events": events,
            "formatted": formatted,
            "count": len(events),
            "operation": "custom"
        }

    def get_events(self, days_offset: int = 0) -> List[Dict]:
        """Google Calendar 일정 가져오기"""
        try:
            if days_offset == 0:
                cmd = [self.gog_path, "calendar", "events", "--today", "--all", "--json"]
            elif days_offset == 1:
                cmd = [self.gog_path, "calendar", "events", "--tomorrow", "--all", "--json"]
            else:
                target_date = datetime.date.today() + datetime.timedelta(days=days_offset)
                cmd = [self.gog_path, "calendar", "events", "--from", str(target_date), "--to", str(target_date), "--all", "--json"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)
            return data.get("events", [])

        except Exception as e:
            return []

    def format_events_for_briefing(
        self,
        events: List[Dict],
        title_prefix: str = "",
        show_date: bool = False,
        korean_weekday: bool = False
    ) -> str:
        """일정을 브리핑용으로 포맷팅"""
        if not events:
            return f"📅 {title_prefix}일정: 없음\n"

        formatted = f"📅 {title_prefix}일정 ({len(events)}건)\n\n"

        weekday_map = {
            "Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목",
            "Fri": "금", "Sat": "토", "Sun": "일"
        }

        for event in events:
            summary = event.get("summary", "제목 없음")
            start_info = event.get("start", {})
            end_info = event.get("end", {})

            date_prefix = ""
            if show_date:
                try:
                    start_time = start_info.get("dateTime", "")
                    if start_time:
                        start_dt = parser.isoparse(start_time)
                        weekday_en = start_dt.strftime('%a')
                        weekday_ko = weekday_map.get(weekday_en, weekday_en)

                        if korean_weekday:
                            date_prefix = f"({start_dt.strftime('%m/%d')}({weekday_ko})) "
                        else:
                            date_prefix = f"({start_dt.strftime('%m/%d')}({weekday_en}) ) "
                except:
                    pass

            if "date" in start_info:
                formatted += f"📍 {summary} (종일)\n"
            else:
                start_time = start_info.get("dateTime", "")
                end_time = end_info.get("dateTime", "")

                try:
                    start_dt = parser.isoparse(start_time)
                    end_dt = parser.isoparse(end_time)
                    start_str = start_dt.strftime("%H:%M")
                    end_str = end_dt.strftime("%H:%M")
                    formatted += f"⏰ {date_prefix}{start_str}-{end_str} {summary}\n"
                except:
                    formatted += f"⏰ {date_prefix}{summary}\n"

            location = event.get("location", "")
            if location:
                formatted += f"   📍 {location}\n"

            description = event.get("description", "")
            if description and len(description) < 100:
                formatted += f"   📝 {description}\n"

            formatted += "\n"

        return formatted


# 편의 함수
def get_todays_schedule() -> str:
    """오늘 일정 가져오기 (편의 함수)"""
    helper = CalendarHelper()
    result = helper.run({"operation": "today"})
    return result.get("formatted", "")


def get_tomorrows_schedule() -> str:
    """내일 일정 가져오기 (편의 함수)"""
    helper = CalendarHelper()
    result = helper.run({"operation": "tomorrow"})
    return result.get("formatted", "")


def get_this_week_schedule() -> str:
    """이번 주 일정 가져오기 (편의 함수)"""
    helper = CalendarHelper()
    result = helper.run({"operation": "week"})
    return result.get("formatted", "")
