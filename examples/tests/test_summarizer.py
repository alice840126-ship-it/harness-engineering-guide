#!/usr/bin/env python3
"""
요약 에이전트 단위 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from summarizer import Summarizer


def test_summarize_text():
    """텍스트 요약 테스트"""
    summarizer = Summarizer()

    # 긴 텍스트
    long_text = """
    첫 번째 문장입니다. 두 번째 문장도 있습니다.
    세 번째 문장도 있습니다. 네 번째 문장은 여기까지입니다.
    다섯 번째 문장도 있습니다.
    """

    # 요약
    summary = summarizer.summarize_text(long_text, max_sentences=3)

    # 확인
    assert len(summary) > 0
    assert len(summary) < len(long_text)

    # 문장 수 확인 (대략)
    sentences = summary.split('.')
    assert len(sentences) <= 4  # 3문장 + 빈 문자열

    print("✅ test_summarize_text: 테스트 통과")


def test_summarize_news():
    """뉴스 요약 테스트"""
    summarizer = Summarizer()

    news_list = [
        {"title": "삼성전자 상승", "link": "https://example.com/1"},
        {"title": "현대차 하락", "link": "https://example.com/2"},
        {"title": "SK하이닉스 호조", "link": "https://example.com/3"},
    ]

    # 요약
    summary = summarizer.summarize_news(news_list, max_count=2)

    # 확인
    assert "삼성전자 상승" in summary
    assert "현대차 하락" in summary
    assert "SK하이닉스 호조" not in summary  # max_count=2

    print("✅ test_summarize_news: 테스트 통과")


def test_summarize_work_log():
    """작업 로그 요약 테스트"""
    summarizer = Summarizer()

    work_items = [
        {
            'time': '09:00',
            'description': '아침 뉴스 스크래핑',
            'status': '완료'
        },
        {
            'time': '10:00',
            'description': 'CLAUDE.md 수정',
            'status': '완료'
        },
        {
            'time': '11:00',
            'description': '투자 분석',
            'status': '완료'
        },
    ]

    # 요약 (카테고리별)
    summary = summarizer.summarize_work_log(work_items, group_by_category=True)

    # 확인
    assert "📌" in summary  # 카테고리별 그룹핑 확인
    assert "아침 뉴스 스크래핑" in summary
    assert "CLAUDE.md 수정" in summary
    assert "투자 분석" in summary

    print("✅ test_summarize_work_log: 테스트 통과")


def test_categorize_work():
    """작업 카테고리 분류 테스트"""
    summarizer = Summarizer()

    # 뉴스 시스템
    cat1 = summarizer._categorize_work("아침 뉴스 스크래핑")
    assert cat1 == "뉴스 시스템"

    # 시스템 정리
    cat2 = summarizer._categorize_work("CLAUDE.md 수정")
    assert cat2 == "시스템 정리"

    # 분석
    cat3 = summarizer._categorize_work("주식 분석")
    assert cat3 == "분석"

    # 기타
    cat4 = summarizer._categorize_work("기타 작업")
    assert cat4 == "기타"

    print("✅ test_categorize_work: 테스트 통과")


def test_count_tokens():
    """토큰 수 계산 테스트"""
    summarizer = Summarizer()

    # 한글 텍스트
    korean_text = "안녕하세요 반갑습니다"
    tokens = summarizer.count_tokens(korean_text)

    assert tokens > 0
    assert tokens < len(korean_text)  # 토큰 수가 문자 수보다 적어야 함

    print("✅ test_count_tokens: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 요약 에이전트 테스트 시작")
    print("=" * 50)

    test_summarize_text()
    test_summarize_news()
    test_summarize_work_log()
    test_categorize_work()
    test_count_tokens()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
