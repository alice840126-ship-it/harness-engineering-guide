#!/usr/bin/env python3
"""
NewsScraper v2 단위 테스트
"""

import pytest
from news_scraper import NewsScraper


class TestNewsScraper:
    """NewsScraper 테스트"""

    def test_init(self):
        """초기화 테스트"""
        scraper = NewsScraper()
        assert scraper.name == "news_scraper"

    def test_init_with_config(self):
        """설정과 함께 초기화"""
        config = {
            "naver_client_id": "test_id",
            "naver_client_secret": "test_secret"
        }
        scraper = NewsScraper(config)
        assert scraper.naver_client_id == "test_id"

    def test_validate_input_scrape(self):
        """스크래핑 입력 검증"""
        scraper = NewsScraper()
        assert scraper.validate_input({
            "operation": "scrape",
            "query": "테스트"
        }) is True

    def test_validate_input_multiple(self):
        """다중 검색어 입력 검증"""
        scraper = NewsScraper()
        assert scraper.validate_input({
            "operation": "multiple",
            "queries": ["테스트1", "테스트2"]
        }) is True

    def test_validate_input_invalid(self):
        """잘못된 입력 검증"""
        scraper = NewsScraper()
        assert scraper.validate_input({"operation": "scrape"}) is False

    def test_process_scrape_operation(self):
        """스크래핑 처리 (API 없이 입력 검증만)"""
        scraper = NewsScraper()
        # API 키 없으면 빈 결과 반환
        result = scraper.run({
            "operation": "scrape",
            "query": "테스트",
            "display": 5
        })
        assert "articles" in result
        assert "operation" in result

    def test_process_multiple_operation(self):
        """다중 검색어 처리"""
        scraper = NewsScraper()
        result = scraper.run({
            "operation": "multiple",
            "queries": ["테스트1", "테스트2"],
            "display_per_query": 3
        })
        assert "articles" in result
        assert result["operation"] == "multiple"

    def test_filter_spam(self):
        """스팸 필터링 테스트"""
        scraper = NewsScraper()
        news_items = [
            {"title": "[속보] 일반 뉴스"},
            {"title": "정상 뉴스"},
            {"title": "[재업로드] 스팸 뉴스"}
        ]
        filtered = scraper.filter_spam(news_items)
        assert len(filtered) < len(news_items)
        assert all("[속보]" not in item.get("title", "") for item in filtered)

    def test_clean_html_text(self):
        """HTML 텍스트 정제"""
        scraper = NewsScraper()
        html_text = "&lt;test&gt;content&lt;/test&gt;"
        cleaned = scraper._clean_html_text(html_text)
        assert "<" not in cleaned
        assert "&lt;" not in cleaned

    def test_get_source_score(self):
        """출처 점수 계산"""
        scraper = NewsScraper()
        # 신뢰도 높은 출처
        assert scraper._get_source_score("https://www.hankyung.com/news") == 3
        # 알 수 없는 출처
        assert scraper._get_source_score("https://unknown.com") == 1


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_scrape_news_signature(self):
        """scrape_news 함수 시그니처"""
        from news_scraper import scrape_news
        assert callable(scrape_news)

    def test_scrape_multiple_news_signature(self):
        """scrape_multiple_news 함수 시그니처"""
        from news_scraper import scrape_multiple_news
        assert callable(scrape_multiple_news)
