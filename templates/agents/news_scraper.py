#!/usr/bin/env python3
"""
뉴스 스크래핑 에이전트

네이버 검색 API, 웹 스크래핑을 통해 뉴스를 수집하는 재사용 가능한 에이전트
- 단일 책임: 뉴스 수집만 담당 (요약, 발송은 다른 에이전트)
"""

import os
import requests
import re
import html
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

# newspaper3k는 본문 추출용 선택적 의존성
try:
    from newspaper import Article, Config
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("⚠️ newspaper3k가 설치되지 않아 본문 추출 기능이 제한됩니다")


class NewsScraper:
    """뉴스 스크래핑 에이전트"""

    def __init__(
        self,
        naver_client_id: Optional[str] = None,
        naver_client_secret: Optional[str] = None
    ):
        """
        초기화

        Args:
            naver_client_id: 네이버 API Client ID (None이면 환경변수에서 읽기)
            naver_client_secret: 네이버 API Client Secret (None이면 환경변수에서 읽기)
        """
        # 환경 변수 로드
        load_dotenv()

        self.naver_client_id = naver_client_id or os.getenv('NAVER_CLIENT_ID', '')
        self.naver_client_secret = naver_client_secret or os.getenv('NAVER_CLIENT_SECRET', '')

        # 기본 스팸 필터링 키워드
        self.default_spam_keywords = [
            "속보", "재업로드", "2보", "3보", "1분전", "2분전", "사진입니다",
            "소식입니다", "알려드립니다", "일정", "공지",
            "원본보기", "더보기", "관련뉴스"
        ]

        # 기본 출처 신뢰도 점수 (1~3점)
        # 한글 이름 + 도메인 모두 매핑
        self.default_trusted_sources = {
            # 1티어: 주요 경제지 (3점)
            "한국경제": 3, "hankyung": 3,
            "매일경제": 3, "mk": 3,
            "헤럴드경제": 3, "heraldcorp": 3,
            "조선비즈": 3, "chosunbiz": 3,
            "이데일리": 3, "edaily": 3,
            "머니투데이": 3, "mt": 3,
            "비즈니스워치": 3, "bizwatch": 3,
            # 2티어: 주요 일간지 (2점)
            "연합뉴스": 2, "yonhapnews": 2,
            "뉴시스": 2, "newsis": 2,
            "아주경제": 2, "ajunews": 2,
            "서울경제": 2, "sedaily": 2,
            "내일경제": 2, "naeil": 2,
            "파이낸셜뉴스": 2, "fnnews": 2,
            "더벨": 2, "thebell": 2,
        }

    def scrape_naver_news(
        self,
        query: str,
        display: int = 10,
        sort: str = "date"
    ) -> List[Dict[str, Any]]:
        """
        네이버 검색 API에서 뉴스 수집

        Args:
            query: 검색어
            display: 결과 개수 (최대 100)
            sort: 정렬 방식 ("date": 최신순, "sim": 관련도순)

        Returns:
            뉴스 아이템 리스트
            ```python
            [
                {
                    "title": "뉴스 제목",
                    "description": "요약 설명",
                    "link": "기사 URL",
                    "pubDate": "발행일",
                    "source_score": 3  # 출처 신뢰도 점수
                },
                ...
            ]
            ```
        """
        if not self.naver_client_id or not self.naver_client_secret:
            print("❌ 네이버 API 키가 설정되지 않았습니다")
            return []

        try:
            url = "https://openapi.naver.com/v1/search/news.json"

            headers = {
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret
            }

            params = {
                "query": query,
                "display": display,
                "sort": sort
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])

            news_items = []
            for item in items:
                # 제목 정제
                title = self._clean_html_text(item.get('title', ''))

                # 설명 정제
                description = self._clean_html_text(item.get('description', ''))

                # 링크
                link = item.get('link', '')

                # 발행일
                pub_date = item.get('pubDate', '')

                # 출처 점수
                source_score = self._get_source_score(link)

                if len(title) >= 10:  # 제목이 너무 짧으면 제외
                    news_items.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "pubDate": pub_date,
                        "source_score": source_score
                    })

            return news_items

        except Exception as e:
            print(f"❌ 네이버 API 오류 ({query}): {e}")
            return []

    def scrape_multiple_queries(
        self,
        queries: List[str],
        display_per_query: int = 5,
        remove_duplicates: bool = True,
        max_total: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        여러 검색어로 뉴스 수집

        Args:
            queries: 검색어 리스트
            display_per_query: 검색어당 결과 개수
            remove_duplicates: 중복 제거 여부
            max_total: 최대 결과 개수 (None이면 무제한)

        Returns:
            뉴스 아이템 리스트
        """
        all_news = []
        seen_urls = set() if remove_duplicates else None

        for query in queries:
            news_items = self.scrape_naver_news(query, display=display_per_query)

            for item in news_items:
                if remove_duplicates:
                    link = item.get('link', '')
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)

                all_news.append(item)

            # 최대 개수 제한
            if max_total and len(all_news) >= max_total:
                all_news = all_news[:max_total]
                break

        return all_news

    def fetch_full_article(
        self,
        url: str,
        max_sentences: int = 3
    ) -> Optional[str]:
        """
        기사 본문 전체 추출 (newspaper3k 사용)

        Args:
            url: 기사 URL
            max_sentences: 최대 문장 수

        Returns:
            본문 요약 텍스트 (실패시 None)
        """
        if not NEWSPAPER_AVAILABLE:
            return None

        try:
            # newspaper3k 설정
            config = Config()
            config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            config.request_timeout = 10

            # 기사 다운로드 및 파싱
            article = Article(url, config=config)
            article.download()
            article.parse()

            # 본문 텍스트 추출
            full_text = article.text

            if not full_text or len(full_text) < 100:
                return None

            # 문장 단위 분리
            sentences = re.split(r'(?<=[.!?])', full_text)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]

            if not sentences:
                return None

            # 상위 N개 문장 선택
            selected = sentences[:max_sentences]
            summary = ' '.join(selected)

            # 끝처리
            if summary and not summary[-1] in ['.', '!', '?', '요']:
                summary += '.'

            # 최대 500자
            if len(summary) > 500:
                summary = summary[:497] + '...'

            return summary

        except Exception as e:
            print(f"⚠️ 본문 추출 실패: {e}")
            return None

    def filter_spam(
        self,
        news_items: List[Dict[str, Any]],
        spam_keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        스팸 필터링

        Args:
            news_items: 뉴스 아이템 리스트
            spam_keywords: 스팸 키워드 리스트 (None이면 기본값 사용)

        Returns:
            필터링된 뉴스 아이템 리스트
        """
        if spam_keywords is None:
            spam_keywords = self.default_spam_keywords

        filtered = []
        for item in news_items:
            title = item.get('title', '')

            # 스팸 체크
            is_spam = any(keyword in title for keyword in spam_keywords)

            if not is_spam:
                filtered.append(item)

        return filtered

    def sort_by_relevance(
        self,
        news_items: List[Dict[str, Any]],
        sort_by: str = "source_score"
    ) -> List[Dict[str, Any]]:
        """
        관련도별 정렬

        Args:
            news_items: 뉴스 아이템 리스트
            sort_by: 정렬 기준 ("source_score", "date")

        Returns:
            정렬된 뉴스 아이템 리스트
        """
        if sort_by == "source_score":
            # 출처 점수 내림차순 → URL 오름차순 (안정성)
            return sorted(
                news_items,
                key=lambda x: (-x.get('source_score', 1), x.get('link', ''))
            )
        elif sort_by == "date":
            # 발행일 내림차순
            return sorted(
                news_items,
                key=lambda x: x.get('pubDate', ''),
                reverse=True
            )
        else:
            return news_items

    def _clean_html_text(self, text: str) -> str:
        """
        HTML 텍스트 정제

        Args:
            text: HTML 텍스트

        Returns:
            정제된 텍스트
        """
        # HTML 디코딩
        text = html.unescape(text)

        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)

        # 특수 문자 치환
        text = text.replace('&quot;', '"').replace('&amp;', '&')

        # 대괄호 안 내용 제거 (예: [연합뉴스])
        text = re.sub(r'\[.*?\]', '', text)

        # 공백 정리
        text = text.strip()

        return text

    def _get_source_score(self, url: str) -> int:
        """
        출처 신뢰도 점수 반환

        Args:
            url: 기사 URL

        Returns:
            신뢰도 점수 (1~3)
        """
        for source, score in self.default_trusted_sources.items():
            if source in url:
                return score

        # 알 수 없는 출처는 1점
        return 1

    def scrape_with_filters(
        self,
        query: str,
        display: int = 10,
        filter_spam: bool = True,
        fetch_full_content: bool = False,
        sort_by: str = "source_score"
    ) -> List[Dict[str, Any]]:
        """
        필터 적용하여 뉴스 수집 (편의 메서드)

        Args:
            query: 검색어
            display: 결과 개수
            filter_spam: 스팸 필터링 여부
            fetch_full_content: 본문 추출 여부
            sort_by: 정렬 기준

        Returns:
            필터링된 뉴스 아이템 리스트
        """
        # 1. 기본 수집
        news_items = self.scrape_naver_news(query, display=display)

        # 2. 스팸 필터링
        if filter_spam:
            news_items = self.filter_spam(news_items)

        # 3. 본문 추출 (선택)
        if fetch_full_content and NEWSPAPER_AVAILABLE:
            for item in news_items:
                link = item.get('link', '')
                if link:
                    full_text = self.fetch_full_article(link)
                    if full_text:
                        item['full_content'] = full_text

        # 4. 정렬
        news_items = self.sort_by_relevance(news_items, sort_by=sort_by)

        return news_items


# 편의 함수
def scrape_news(
    query: str,
    display: int = 10,
    filter_spam: bool = True
) -> List[Dict[str, Any]]:
    """뉴스 스크래핑 (편의 함수)"""
    return NewsScraper().scrape_with_filters(
        query=query,
        display=display,
        filter_spam=filter_spam
    )


def scrape_multiple_news(
    queries: List[str],
    display_per_query: int = 5,
    max_total: Optional[int] = None
) -> List[Dict[str, Any]]:
    """여러 검색어로 뉴스 스크래핑 (편의 함수)"""
    return NewsScraper().scrape_multiple_queries(
        queries=queries,
        display_per_query=display_per_query,
        max_total=max_total
    )
