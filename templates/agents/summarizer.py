#!/usr/bin/env python3
"""
요약 에이전트 v2 (BaseAgent 기반)

텍스트, 뉴스, 작업 로그 등을 요약하는 재사용 가능한 에이전트
- 단일 책임: 텍스트 요약만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from base_agent import BaseAgent


class Summarizer(BaseAgent):
    """요약 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (max_sentences, max_length 등)
        """
        super().__init__("summarizer", config)

        # 기본 설정
        self.max_sentences = self.config.get("max_sentences", 3)
        self.max_length = self.config.get("max_length", 500)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "text")

        if operation == "text":
            return "text" in data
        elif operation == "news":
            return "news_list" in data
        elif operation == "work_log":
            return "work_items" in data
        elif operation == "daily_report":
            return "sections" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        요약 처리

        Args:
            data: {
                "operation": str,  # "text", "news", "work_log", "daily_report"
                ...operation-specific params
            }

        Returns:
            {"summary": str, "type": str}
        """
        operation = data.get("operation", "text")

        if operation == "text":
            return self._summarize_text(data)
        elif operation == "news":
            return self._summarize_news(data)
        elif operation == "work_log":
            return self._summarize_work_log(data)
        elif operation == "daily_report":
            return self._summarize_daily_report(data)
        elif operation == "bullet_points":
            return self._summarize_bullet_points(data)
        else:
            return {"summary": "잘못된 operation", "type": "error"}

    def _summarize_text(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """텍스트 요약"""
        text = data.get("text", "")
        max_sentences = data.get("max_sentences", self.max_sentences)
        max_length = data.get("max_length", self.max_length)

        if not text:
            return {"summary": "내용 없음", "type": "text"}

        # 문장 분리
        sentences = re.split(r'(?<=[.!?])\s+', text)
        selected = sentences[:max_sentences]

        # 길이 제한
        result = ' '.join(selected)
        if len(result) > max_length:
            result = result[:max_length].rsplit(' ', 1)[0] + '...'

        return {"summary": result, "type": "text"}

    def _summarize_news(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """뉴스 리스트 요약"""
        news_list = data.get("news_list", [])
        max_count = data.get("max_count", 5)
        include_links = data.get("include_links", False)

        if not news_list:
            return {"summary": "뉴스 없음", "type": "news"}

        result = []

        for i, news in enumerate(news_list[:max_count], 1):
            title = news.get("title", news.get("제목", ""))
            link = news.get("link", news.get("url", news.get("링크", "")))
            description = news.get("description", news.get("요약", ""))

            line = f"{i}. {title}"
            result.append(line)

            if description and len(description) < 100:
                result.append(f"   {description}")

            if link and include_links:
                result.append(f"   {link}")

        return {"summary": '\n'.join(result), "type": "news"}

    def _summarize_work_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """작업 로그 요약"""
        work_items = data.get("work_items", [])
        group_by_category = data.get("group_by_category", True)
        max_count = data.get("max_count", 10)

        if not work_items:
            return {"summary": "오늘 작업 내역 없음", "type": "work_log"}

        # 시간순 정렬
        sorted_items = sorted(work_items, key=lambda x: x.get('time', ''))[:max_count]

        if group_by_category:
            return {"summary": self._group_by_category(sorted_items), "type": "work_log"}
        else:
            return {"summary": self._simple_list(sorted_items), "type": "work_log"}

    def _group_by_category(self, items: List[Dict]) -> str:
        """카테고리별 그룹핑"""
        categories = {}

        for item in items:
            desc = item.get('description', '')
            category = self._categorize_work(desc)

            if category not in categories:
                categories[category] = []
            categories[category].append(item)

        result = []
        for category, cat_items in categories.items():
            result.append(f"\n📌 {category}")
            for item in cat_items:
                time_str = item.get('time', '')
                desc = item.get('description', '')
                status = item.get('status', '')
                status_emoji = "✅" if status == "완료" else "🔄"
                result.append(f"   {status_emoji} {time_str} - {desc}")

        return '\n'.join(result)

    def _simple_list(self, items: List[Dict]) -> str:
        """단순 리스트"""
        result = []
        for item in items:
            time_str = item.get('time', '')
            desc = item.get('description', '')
            status = item.get('status', '')
            status_emoji = "✅" if status == "완료" else "🔄"
            result.append(f"{status_emoji} {time_str} - {desc}")

        return '\n'.join(result)

    def _categorize_work(self, description: str) -> str:
        """작업 카테고리 분류"""
        keywords = {
            "뉴스 시스템": ["뉴스", "스크래핑", "브리핑"],
            "시스템 정리": ["CLAUDE", "수정", "리모델링"],
            "분석": ["분석", "보고서", "리포트"],
            "자동화": ["자동화", "스크립트", "LaunchAgent"],
            "투자": ["주식", "코인", "비트코인", "이더리움"],
        }

        for category, cats in keywords.items():
            for keyword in cats:
                if keyword in description:
                    return category

        return "기타"

    def _summarize_daily_report(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """데일리 리포트 요약"""
        sections = data.get("sections", {})
        date = data.get("date")

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        result = f"📋 데일리 리포트 ({date})\n"
        result += "=" * 50 + "\n\n"

        for section_name, content in sections.items():
            result += f"## {section_name}\n\n{content}\n\n"
            result += "-" * 50 + "\n\n"

        return {"summary": result, "type": "daily_report"}

    def _summarize_bullet_points(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """불렛 포인트 요약"""
        text = data.get("text", "")
        max_points = data.get("max_points", 5)

        if not text:
            return {"summary": "내용 없음", "type": "bullet_points"}

        sentences = re.split(r'(?<=[.!?])\s+', text)
        points = sentences[:max_points]

        result = []
        for point in points:
            result.append(f"• {point.strip()}")

        return {"summary": '\n'.join(result), "type": "bullet_points"}


# 편의 함수
def summarize_text(text: str, max_sentences: int = 3) -> str:
    """텍스트 요약 (편의 함수)"""
    summarizer = Summarizer()
    result = summarizer.run({
        "operation": "text",
        "text": text,
        "max_sentences": max_sentences
    })
    return result.get("summary", "")


def summarize_news(news_list: List[Dict], max_count: int = 5) -> str:
    """뉴스 요약 (편의 함수)"""
    summarizer = Summarizer()
    result = summarizer.run({
        "operation": "news",
        "news_list": news_list,
        "max_count": max_count
    })
    return result.get("summary", "")


def summarize_work_log(work_items: List[Dict], group_by: bool = True) -> str:
    """작업 로그 요약 (편의 함수)"""
    summarizer = Summarizer()
    result = summarizer.run({
        "operation": "work_log",
        "work_items": work_items,
        "group_by_category": group_by
    })
    return result.get("summary", "")
