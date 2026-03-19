#!/usr/bin/env python3
"""
구글 캘린더 도우미 에이전트
- gog CLI를 사용하여 Google Calendar 일정 조회
- 오늘/내일/이번 주 일정 포맷팅
"""

import subprocess
import json
import datetime
from dateutil import parser
from typing import List, Dict, Optional


class CalendarHelper:
    """구글 캘린더 도우미 에이전트"""

    def __init__(self, gog_path: str = "/opt/homebrew/bin/gog"):
        """
        초기화

        Args:
            gog_path: gog CLI 경로
        """
        self.gog_path = gog_path

    def get_events(self, days_offset: int = 0) -> List[Dict]:
        """
        Google Calendar 일정 가져오기

        Args:
            days_offset: 0=오늘, 1=내일, -1=어제

        Returns:
            일정 리스트
        """
        try:
            if days_offset == 0:
                cmd = [self.gog_path, "calendar", "events", "--today", "--all", "--json"]
            elif days_offset == 1:
                cmd = [self.gog_path, "calendar", "events", "--tomorrow", "--all", "--json"]
            else:
                # 상대 날짜 계산
                target_date = datetime.date.today() + datetime.timedelta(days=days_offset)
                cmd = [self.gog_path, "calendar", "events", "--from", str(target_date), "--to", str(target_date), "--all", "--json"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)
            return data.get("events", [])

        except Exception as e:
            return []

    def get_todays_schedule(self) -> str:
        """오늘 일정 가져오기"""
        events = self.get_events(days_offset=0)
        return self.format_events_for_briefing(events, "오늘 ")

    def get_tomorrows_schedule(self) -> str:
        """내일 일정 가져오기"""
        events = self.get_events(days_offset=1)
        return self.format_events_for_briefing(events, "내일 ")

    def get_this_week_schedule(self) -> str:
        """이번 주 일정 가져오기"""
        try:
            cmd = [self.gog_path, "calendar", "events", "--week", "--all", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                return "📅 이번 주 일정: 조회 실패\n"

            data = json.loads(result.stdout)
            events = data.get("events", [])

            # 오늘 날짜와 지난 일정 필터링
            today = datetime.date.today()
            today_start = datetime.datetime.combine(today, datetime.time.min).timestamp() * 1000

            filtered_events = []
            for event in events:
                start_info = event.get("start", {})

                # 종일 일정
                if "date" in start_info:
                    event_date = parser.parse(start_info["date"])
                    event_datetime = datetime.datetime.combine(event_date, datetime.time.min)
                # 시간 있는 일정
                elif "dateTime" in start_info:
                    start_ms = start_info.get("dateTime", "")
                    if start_ms:
                        start_dt = parser.isoparse(start_ms)
                        event_datetime = start_dt
                else:
                    continue

                # 지난 일정 제거
                if event_datetime.timestamp() * 1000 < today_start:
                    continue

                # 오늘 일정 제거
                if event_datetime.date() == today:
                    continue

                filtered_events.append(event)

            return self.format_events_for_briefing(filtered_events, "이번 주 ", show_date=True, korean_weekday=True)
        except Exception as e:
            return f"📅 이번 주 일정: 조회 실패 ({e})\n"

    def format_events_for_briefing(
        self,
        events: List[Dict],
        title_prefix: str = "",
        show_date: bool = False,
        korean_weekday: bool = False
    ) -> str:
        """
        일정을 브리핑용으로 포맷팅

        Args:
            events: 일정 리스트
            title_prefix: 제목 접두사 (예: "오늘", "내일")
            show_date: 요일과 날짜 표시 여부
            korean_weekday: 한글 요일 사용 (수, 목, 금 등)

        Returns:
            포맷팅된 일정 문자열
        """
        if not events:
            return f"📅 {title_prefix}일정: 없음\n"

        formatted = f"📅 {title_prefix}일정 ({len(events)}건)\n\n"

        # 요일 변환 테이블
        weekday_map = {
            "Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목",
            "Fri": "금", "Sat": "토", "Sun": "일"
        }

        for event in events:
            summary = event.get("summary", "제목 없음")

            # 시간 정보 추출
            start_info = event.get("start", {})
            end_info = event.get("end", {})

            # 날짜/요일 추출
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

            # 종일 일정인지 확인
            if "date" in start_info:
                formatted += f"📍 {summary} (종일)\n"
            else:
                # 시간 있는 일정
                start_time = start_info.get("dateTime", "")
                end_time = end_info.get("dateTime", "")

                try:
                    # ISO 8601 파싱
                    start_dt = parser.isoparse(start_time)
                    end_dt = parser.isoparse(end_time)

                    # 시간만 추출
                    start_str = start_dt.strftime("%H:%M")
                    end_str = end_dt.strftime("%H:%M")

                    formatted += f"⏰ {date_prefix}{start_str}-{end_str} {summary}\n"
                except:
                    formatted += f"⏰ {date_prefix}{summary}\n"

            # 장소 정보
            location = event.get("location", "")
            if location:
                formatted += f"   📍 {location}\n"

            # 설명
            description = event.get("description", "")
            if description and len(description) < 100:
                formatted += f"   📝 {description}\n"

            formatted += "\n"

        return formatted
