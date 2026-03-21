#!/usr/bin/env python3
"""
뉴스 스크래핑 에이전트 v2 (BaseAgent 기반)

네이버 검색 API, 웹 스크래핑을 통해 뉴스를 수집하는 재사용 가능한 에이전트
- 단일 책임: 뉴스 수집만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import os
import requests
import re
import html
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from base_agent import BaseAgent

# newspaper3k는 본문 추출용 선택적 의존성
try:
    from newspaper import Article, Config
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False


class NewsScraper(BaseAgent):
    """뉴스 스크래핑 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (naver_client_id, naver_client_secret)
        """
        super().__init__("news_scraper", config)

        # 환경 변수 로드
        load_dotenv()

        self.naver_client_id = self.config.get("naver_client_id") or os.getenv('NAVER_CLIENT_ID', '')
        self.naver_client_secret = self.config.get("naver_client_secret") or os.getenv('NAVER_CLIENT_SECRET', '')

        # 기본 스팸 필터링 키워드
        self.default_spam_keywords = [
            "속보", "재업로드", "2보", "3보", "1분전", "2분전", "사진입니다",
            "소식입니다", "알려드립니다", "일정", "공지",
            "원본보기", "더보기", "관련뉴스"
        ]

        # 기본 출처 신뢰도 점수
        self.default_trusted_sources = {
            "한국경제": 3, "hankyung": 3,
            "매일경제": 3, "mk": 3,
            "헤럴드경제": 3, "heraldcorp": 3,
            "조선비즈": 3, "chosunbiz": 3,
            "이데일리": 3, "edaily": 3,
            "머니투데이": 3, "mt": 3,
            "비즈니스워치": 3, "bizwatch": 3,
            "연합뉴스": 2, "yonhapnews": 2,
            "뉴시스": 2, "newsis": 2,
            "아주경제": 2, "ajunews": 2,
            "서울경제": 2, "sedaily": 2,
            "내일경제": 2, "naeil": 2,
            "파이낸셜뉴스": 2, "fnnews": 2,
            "더벨": 2, "thebell": 2,
        }

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "scrape")

        if operation == "scrape":
            return "query" in data
        elif operation == "multiple":
            return "queries" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        뉴스 스크래핑 처리

        Args:
            data: {
                "operation": str,     # "scrape", "multiple"
                "query": str,         # single 검색어
                "queries": list,      # multiple 검색어들
                "display": int,       # 결과 개수
                "filter_spam": bool,  # 스팸 필터링
                "sort": str           # 정렬 방식
            }

        Returns:
            {"articles": list, "count": int, "operation": str}
        """
        operation = data.get("operation", "scrape")

        if operation == "scrape":
            return self._scrape_single(data)
        elif operation == "multiple":
            return self._scrape_multiple(data)
        else:
            return {"articles": [], "error": "잘못된 operation"}

    def _scrape_single(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """단일 검색어 스크래핑"""
        query = data.get("query", "")
        display = data.get("display", 10)
        sort = data.get("sort", "date")
        filter_spam = data.get("filter_spam", True)
        fetch_full = data.get("fetch_full_content", False)

        # 스크래핑
        news_items = self.scrape_naver_news(query, display=display, sort=sort)

        # 스팸 필터링
        if filter_spam:
            news_items = self.filter_spam(news_items)

        # 본문 추출
        if fetch_full and NEWSPAPER_AVAILABLE:
            for item in news_items:
                link = item.get('link', '')
                if link:
                    full_text = self.fetch_full_article(link)
                    if full_text:
                        item['full_content'] = full_text

        return {
            "articles": news_items,
            "count": len(news_items),
            "query": query,
            "operation": "scrape"
        }

    def _scrape_multiple(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """여러 검색어 스크래핑"""
        queries = data.get("queries", [])
        display_per_query = data.get("display_per_query", 5)
        remove_duplicates = data.get("remove_duplicates", True)
        max_total = data.get("max_total")

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

            if max_total and len(all_news) >= max_total:
                all_news = all_news[:max_total]
                break

        return {
            "articles": all_news,
            "count": len(all_news),
            "queries": queries,
            "operation": "multiple"
        }

    def scrape_naver_news(
        self,
        query: str,
        display: int = 10,
        sort: str = "date"
    ) -> List[Dict[str, Any]]:
        """네이버 검색 API에서 뉴스 수집"""
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
                title = self._clean_html_text(item.get('title', ''))
                description = self._clean_html_text(item.get('description', ''))
                link = item.get('link', '')
                pub_date = item.get('pubDate', '')
                source_score = self._get_source_score(link)

                if len(title) >= 10:
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

    def filter_spam(
        self,
        news_items: List[Dict[str, Any]],
        spam_keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """스팸 필터링"""
        if spam_keywords is None:
            spam_keywords = self.default_spam_keywords

        filtered = []
        for item in news_items:
            title = item.get('title', '')
            is_spam = any(keyword in title for keyword in spam_keywords)

            if not is_spam:
                filtered.append(item)

        return filtered

    def fetch_full_article(self, url: str, max_sentences: int = 3) -> Optional[str]:
        """기사 본문 전체 추출"""
        if not NEWSPAPER_AVAILABLE:
            return None

        try:
            config = Config()
            config.browser_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            config.request_timeout = 10

            article = Article(url, config=config)
            article.download()
            article.parse()

            full_text = article.text

            if not full_text or len(full_text) < 100:
                return None

            sentences = re.split(r'(?<=[.!?])', full_text)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]

            if not sentences:
                return None

            selected = sentences[:max_sentences]
            summary = ' '.join(selected)

            if summary and not summary[-1] in ['.', '!', '?', '요']:
                summary += '.'

            if len(summary) > 500:
                summary = summary[:497] + '...'

            return summary

        except Exception as e:
            return None

    def _clean_html_text(self, text: str) -> str:
        """HTML 텍스트 정제"""
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&quot;', '"').replace('&amp;', '&')
        text = re.sub(r'\[.*?\]', '', text)
        text = text.strip()
        return text

    def _get_source_score(self, url: str) -> int:
        """출처 신뢰도 점수 반환"""
        for source, score in self.default_trusted_sources.items():
            if source in url:
                return score
        return 1


# 편의 함수
def scrape_news(query: str, display: int = 10, filter_spam: bool = True) -> List[Dict[str, Any]]:
    """뉴스 스크래핑 (편의 함수)"""
    scraper = NewsScraper()
    result = scraper.run({
        "operation": "scrape",
        "query": query,
        "display": display,
        "filter_spam": filter_spam
    })
    return result.get("articles", [])


def scrape_multiple_news(
    queries: List[str],
    display_per_query: int = 5,
    max_total: Optional[int] = None
) -> List[Dict[str, Any]]:
    """여러 검색어로 뉴스 스크래핑 (편의 함수)"""
    scraper = NewsScraper()
    result = scraper.run({
        "operation": "multiple",
        "queries": queries,
        "display_per_query": display_per_query,
        "max_total": max_total
    })
    return result.get("articles", [])
