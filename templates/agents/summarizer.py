#!/usr/bin/env python3
"""
요약 에이전트

텍스트, 뉴스, 작업 로그 등을 요약하는 재사용 가능한 에이전트
"""

import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import re


class Summarizer:
    """요약 에이전트"""

    def summarize_text(
        self,
        text: str,
        max_sentences: int = 3,
        max_length: int = 500
    ) -> str:
        """
        텍스트 요약

        Args:
            text: 요약할 텍스트
            max_sentences: 최대 문장 수
            max_length: 최대 길이

        Returns:
            요약된 텍스트
        """
        if not text:
            return "내용 없음"

        # 문장 분리
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # 상위 N개 문장 선택
        selected = sentences[:max_sentences]

        # 길이 제한
        result = ' '.join(selected)
        if len(result) > max_length:
            result = result[:max_length].rsplit(' ', 1)[0] + '...'

        return result

    def summarize_news(
        self,
        news_list: List[Dict[str, Any]],
        max_count: int = 5,
        include_links: bool = False
    ) -> str:
        """
        뉴스 리스트 요약

        Args:
            news_list: 뉴스 딕셔너리 리스트
            max_count: 최대 뉴스 개수
            include_links: 링크 포함 여부

        Returns:
            요약된 뉴스 텍스트
        """
        if not news_list:
            return "뉴스 없음"

        result = []

        for i, news in enumerate(news_list[:max_count], 1):
            title = news.get("title", news.get("제목", ""))
            link = news.get("link", news.get("url", news.get("링크", "")))
            description = news.get("description", news.get("요약", ""))

            # 번호와 제목
            line = f"{i}. {title}"
            result.append(line)

            # 설명 (있으면)
            if description and len(description) < 100:
                result.append(f"   {description}")

            # 링크 (있으면)
            if link and include_links:
                result.append(f"   {link}")

        return '\n'.join(result)

    def summarize_work_log(
        self,
        work_items: List[Dict[str, Any]],
        group_by_category: bool = True,
        max_count: int = 10
    ) -> str:
        """
        작업 로그 요약

        Args:
            work_items: 작업 아이템 리스트
            group_by_category: 카테고리별 그룹핑 여부
            max_count: 최대 작업 개수

        Returns:
            요약된 작업 로그
        """
        if not work_items:
            return "오늘 작업 내역 없음"

        # 시간순 정렬
        sorted_items = sorted(work_items, key=lambda x: x.get('time', ''))

        # 개수 제한
        sorted_items = sorted_items[:max_count]

        if group_by_category:
            return self._group_by_category(sorted_items)
        else:
            return self._simple_list(sorted_items)

    def _group_by_category(self, items: List[Dict]) -> str:
        """카테고리별 그룹핑"""
        categories = {}

        for item in items:
            desc = item.get('description', '')
            category = self._categorize_work(desc)

            if category not in categories:
                categories[category] = []
            categories[category].append(item)

        # 결과 생성
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

    def summarize_daily_report(
        self,
        sections: Dict[str, str],
        date: Optional[str] = None
    ) -> str:
        """
        데일리 리포트 요약

        Args:
            sections: 섹션별 데이터 {"섹션명": 내용}
            date: 날짜 (없으면 오늘)

        Returns:
            포맷된 데일리 리포트
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        result = f"📋 데일리 리포트 ({date})\n"
        result += "=" * 50 + "\n\n"

        for section_name, content in sections.items():
            result += f"## {section_name}\n\n"
            result += f"{content}\n\n"
            result += "-" * 50 + "\n\n"

        return result

    def summarize_with_bullet_points(
        self,
        text: str,
        max_points: int = 5
    ) -> str:
        """
        불렛 포인트 요약

        Args:
            text: 요약할 텍스트
            max_points: 최대 포인트 수

        Returns:
            불렛 포인트로 요약된 텍스트
        """
        if not text:
            return "내용 없음"

        # 문장 분리
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # 상위 N개 선택
        points = sentences[:max_points]

        # 불렛 포인트 포맷
        result = []
        for point in points:
            result.append(f"• {point.strip()}")

        return '\n'.join(result)

    def extract_key_points(
        self,
        text: str,
        keywords: List[str],
        context_sentences: int = 2
    ) -> List[str]:
        """
        키워드 기반 핵심 포인트 추출

        Args:
            text: 분석할 텍스트
            keywords: 찾을 키워드 리스트
            context_sentences: 키워드 주변 문장 수

        Returns:
            핵심 포인트 리스트
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        key_points = []

        for keyword in keywords:
            for i, sentence in enumerate(sentences):
                if keyword.lower() in sentence.lower():
                    # 컨텍스트 포함
                    start = max(0, i - context_sentences)
                    end = min(len(sentences), i + context_sentences + 1)
                    context = ' '.join(sentences[start:end])

                    if context not in key_points:
                        key_points.append(context)

        return key_points[:5]

    def count_tokens(self, text: str) -> int:
        """
        대략적인 토큰 수 계산

        Args:
            text: 텍스트

        Returns:
        예상 토큰 수
        """
        # 한국어와 영어 혼합 텍스트의 대략적 계산
        # 공백 제거
        text_no_spaces = re.sub(r'\s+', '', text)

        # 한글 + 영어 문자 수
        korean_chars = len(re.findall(r'[가-힣]', text_no_spaces))
        english_chars = len(re.findall(r'[a-zA-Z]', text_no_spaces))

        # 대략적 토큰 수 (한글 1글자 = 0.7 토큰, 영어 4글자 = 1 토큰)
        tokens = (korean_chars * 0.7) + (english_chars / 4)

        return int(tokens)


# 편의 함수
def summarize_text(text: str, max_sentences: int = 3) -> str:
    """텍스트 요약 (편의 함수)"""
    return Summarizer().summarize_text(text, max_sentences)


def summarize_news(news_list: List[Dict], max_count: int = 5) -> str:
    """뉴스 요약 (편의 함수)"""
    return Summarizer().summarize_news(news_list, max_count)


def summarize_work_log(work_items: List[Dict], group_by: bool = True) -> str:
    """작업 로그 요약 (편의 함수)"""
    return Summarizer().summarize_work_log(work_items, group_by_category=group_by)
