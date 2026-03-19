#!/usr/bin/env python3
"""
뉴스 스크래핑 에이전트 단위 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

# 환경변수 설정 (테스트용)
os.environ['NAVER_CLIENT_ID'] = 'TEST_CLIENT_ID'
os.environ['NAVER_CLIENT_SECRET'] = 'TEST_CLIENT_SECRET'

from news_scraper import NewsScraper


def test_scraper_initialization():
    """스크래퍼 초기화 테스트"""
    scraper = NewsScraper()

    # 환경변수 확인
    assert scraper.naver_client_id == 'TEST_CLIENT_ID'
    assert scraper.naver_client_secret == 'TEST_CLIENT_SECRET'

    # 기본 설정 확인
    assert len(scraper.default_spam_keywords) > 0
    assert len(scraper.default_trusted_sources) > 0

    print("✅ test_scraper_initialization: 테스트 통과")


def test_clean_html_text():
    """HTML 텍스트 정제 테스트"""
    scraper = NewsScraper()

    # HTML 태그 제거
    html_text = "<b>굵게</b> &amp; <i>기울임</i>"
    cleaned = scraper._clean_html_text(html_text)

    assert "&amp;" not in cleaned
    assert "<b>" not in cleaned
    assert "굵게" in cleaned
    assert "기울임" in cleaned

    print("✅ test_clean_html_text: 테스트 통과")


def test_source_score():
    """출처 점수 계산 테스트"""
    scraper = NewsScraper()

    # 주요 경제지 (3점)
    score1 = scraper._get_source_score("https://www.hankyung.com/article/2023...")
    assert score1 == 3

    # 주요 일간지 (2점)
    score2 = scraper._get_source_score("https://www.yonhapnews.com/...")
    assert score2 == 2

    # 알 수 없는 출처 (1점)
    score3 = scraper._get_source_score("https://unknown-news.com/...")
    assert score3 == 1

    print("✅ test_source_score: 테스트 통과")


def test_spam_filtering():
    """스팸 필터링 테스트"""
    scraper = NewsScraper()

    news_items = [
        {"title": "속보: 삼성전자 상승", "link": "https://example.com/1"},
        {"title": "재업로드: 주식 뉴스", "link": "https://example.com/2"},
        {"title": "정상 뉴스 기사", "link": "https://example.com/3"},
        {"title": "알려드립니다: 공지사항", "link": "https://example.com/4"},
    ]

    filtered = scraper.filter_spam(news_items)

    # 스팸 필터링 확인
    assert len(filtered) == 1
    assert filtered[0]["title"] == "정상 뉴스 기사"

    print("✅ test_spam_filtering: 테스트 통과")


def test_custom_spam_keywords():
    """커스텀 스팸 키워드 테스트"""
    scraper = NewsScraper()

    news_items = [
        {"title": "필터링 테스트", "link": "https://example.com/1"},
        {"title": "제목어제거", "link": "https://example.com/2"},
    ]

    # 커스텀 키워드로 필터링
    custom_keywords = ["테스트"]
    filtered = scraper.filter_spam(news_items, spam_keywords=custom_keywords)

    assert len(filtered) == 1
    assert filtered[0]["title"] == "제목어제거"

    print("✅ test_custom_spam_keywords: 테스트 통과")


def test_sort_by_source_score():
    """출처 점수별 정렬 테스트"""
    scraper = NewsScraper()

    news_items = [
        {"title": "1점 뉴스", "link": "https://unknown.com/1", "source_score": 1},
        {"title": "3점 뉴스", "link": "https://hankyung.com/2", "source_score": 3},
        {"title": "2점 뉴스", "link": "https://yonhapnews.com/3", "source_score": 2},
    ]

    sorted_items = scraper.sort_by_relevance(news_items, sort_by="source_score")

    # 점수순 정렬 확인
    assert sorted_items[0]["source_score"] == 3
    assert sorted_items[1]["source_score"] == 2
    assert sorted_items[2]["source_score"] == 1

    print("✅ test_sort_by_source_score: 테스트 통과")


def test_interface_methods():
    """인터페이스 메서드 확인 테스트"""
    scraper = NewsScraper()

    # 주요 메서드 확인
    assert hasattr(scraper, 'scrape_naver_news')
    assert hasattr(scraper, 'scrape_multiple_queries')
    assert hasattr(scraper, 'fetch_full_article')
    assert hasattr(scraper, 'filter_spam')
    assert hasattr(scraper, 'sort_by_relevance')
    assert hasattr(scraper, 'scrape_with_filters')

    print("✅ test_interface_methods: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 뉴스 스크래핑 에이전트 테스트 시작")
    print("=" * 50)

    test_scraper_initialization()
    test_clean_html_text()
    test_source_score()
    test_spam_filtering()
    test_custom_spam_keywords()
    test_sort_by_source_score()
    test_interface_methods()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
