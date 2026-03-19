#!/usr/bin/env python3
"""
뉴스 분석 에이전트 단위 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from news_analyzer import NewsAnalyzer


def test_analyzer_initialization():
    """분석기 초기화 테스트"""
    analyzer = NewsAnalyzer()

    # 키워드 사전 확인
    assert hasattr(analyzer, 'investment_keywords')
    assert hasattr(analyzer, 'outlook_keywords')

    # 키워드 카테고리 확인
    assert 'AI' in analyzer.investment_keywords
    assert '부동산' in analyzer.investment_keywords
    assert '금융' in analyzer.investment_keywords

    print("✅ test_analyzer_initialization: 테스트 통과")


def test_extract_keywords():
    """키워드 추출 테스트"""
    analyzer = NewsAnalyzer()

    # 테스트 텍스트
    text = "삼성전자와 SK하이닉스가 HBM 반도체 시장을 선도하고 있습니다. AI 수요가 급증하고 있습니다."

    keywords = analyzer.extract_keywords(text)

    # 키워드 확인
    assert len(keywords) > 0

    # 카테고리와 키워드 형태 확인
    categories = [kw[0] for kw in keywords]
    assert 'AI' in categories

    print("✅ test_extract_keywords: 테스트 통과")


def test_group_by_theme():
    """테마 그룹핑 테스트"""
    analyzer = NewsAnalyzer()

    # 테스트 기사
    articles = [
        {'title': '삼성전자 HBM 투자', 'content': '삼성전자가 HBM 생산을 확대합니다.'},
        {'title': 'SK하이닉스 반도체', 'content': 'SK하이닉스도 HBM에 투자합니다.'},
        {'title': 'AI 반도체 수요', 'content': 'AI로 인한 반도체 수요가 급증합니다.'},
        {'title': '부동산 시장 뉴스', 'content': '아파트 가격이 상승합니다.'},
    ]

    themes = analyzer.group_by_theme(articles, min_articles=2)

    # AI/반도체 테마 확인
    assert len(themes) > 0

    # 최소 2개 이상의 기사가 있는 테마만 선택
    for theme_key, theme_data in themes.items():
        assert theme_data['count'] >= 2

    print("✅ test_group_by_theme: 테스트 통과")


def test_derive_insights():
    """인사이트 도출 테스트"""
    analyzer = NewsAnalyzer()

    # 테스트 테마
    themes = {
        'AI:반도체': {
            'category': 'AI',
            'keyword': '반도체',
            'count': 5,
            'articles': [
                {'title': '삼성전자 HBM'},
                {'title': 'SK하이닉스 칩'}
            ]
        },
        '금융:금리': {
            'category': '금융',
            'keyword': '금리',
            'count': 3,
            'articles': [
                {'title': '금리 인상'}
            ]
        }
    }

    insights = analyzer.derive_insights(themes, "2026-03-19")

    # 인사이트 확인
    assert len(insights) > 0

    # 인사이트 타입 확인
    insight_types = [i['type'] for i in insights]
    assert '주요 테마' in insight_types

    print("✅ test_derive_insights: 테스트 통과")


def test_analyze_outlook():
    """전망 분석 테스트"""
    analyzer = NewsAnalyzer()

    # 전망이 포함된 텍스트
    text_with_outlook = "시장 분석가들은 내년 상반기까지 주가가 상승할 것으로 전망합니다. 목표가는 80,000원입니다."
    outlook = analyzer.analyze_outlook(text_with_outlook)

    assert outlook is not None
    assert '전망' in outlook or '목표가' in outlook

    # 전망이 없는 텍스트
    text_without_outlook = "오늘 날씨가 좋습니다."
    outlook_none = analyzer.analyze_outlook(text_without_outlook)

    assert outlook_none is None

    print("✅ test_analyze_outlook: 테스트 통과")


def test_calculate_sentiment():
    """감성 분석 테스트"""
    analyzer = NewsAnalyzer()

    # 긍정 텍스트
    positive_text = "주가가 상승했습니다. 성장세가 지속됩니다. 최고가를 갱신했습니다."
    sentiment = analyzer.calculate_sentiment(positive_text)

    assert sentiment['label'] in ['긍정', '중립']
    assert sentiment['positive'] > 0

    # 부정 텍스트
    negative_text = "주가가 하락했습니다. 위기가 지속됩니다. 우려가 커지고 있습니다."
    sentiment = analyzer.calculate_sentiment(negative_text)

    assert sentiment['label'] in ['부정', '중립']
    assert sentiment['negative'] > 0

    # 중립 텍스트
    neutral_text = "오늘 뉴스입니다."
    sentiment = analyzer.calculate_sentiment(neutral_text)

    assert sentiment['score'] == 0
    assert sentiment['label'] == '중립'

    print("✅ test_calculate_sentiment: 테스트 통과")


def test_generate_summary():
    """요약 생성 테스트"""
    analyzer = NewsAnalyzer()

    articles = [
        {'title': '삼성전자가 HBM 생산을 확대합니다.'},
        {'title': 'SK하이닉스도 반도체 투자를 늘립니다.'},
        {'title': 'AI 수요로 반도체 업황이 호조입니다.'},
    ]

    summary = analyzer.generate_summary(articles, max_sentences=3)

    assert len(summary) > 0
    assert isinstance(summary, str)

    print("✅ test_generate_summary: 테스트 통과")


def test_analyze_trend():
    """트렌드 분석 테스트"""
    analyzer = NewsAnalyzer()

    articles = [
        {'title': '삼성전자 HBM 투자', 'content': '삼성전자 내용'},
        {'title': 'SK하이닉스 반도체', 'content': 'SK하이닉스 내용'},
        {'title': 'AI 반도체 수요', 'content': 'AI 수요 내용'},
    ]

    trend = analyzer.analyze_trend(articles)

    assert 'trend' in trend
    assert 'strength' in trend
    assert trend['trend'] != '없음'
    assert trend['strength'] > 0

    print("✅ test_analyze_trend: 테스트 통과")


def test_interface_methods():
    """인터페이스 메서드 확인 테스트"""
    analyzer = NewsAnalyzer()

    # 주요 메서드 확인
    assert hasattr(analyzer, 'extract_keywords')
    assert hasattr(analyzer, 'group_by_theme')
    assert hasattr(analyzer, 'derive_insights')
    assert hasattr(analyzer, 'analyze_outlook')
    assert hasattr(analyzer, 'calculate_sentiment')
    assert hasattr(analyzer, 'generate_summary')
    assert hasattr(analyzer, 'analyze_trend')

    print("✅ test_interface_methods: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 뉴스 분석 에이전트 테스트 시작")
    print("=" * 50)

    test_analyzer_initialization()
    test_extract_keywords()
    test_group_by_theme()
    test_derive_insights()
    test_analyze_outlook()
    test_calculate_sentiment()
    test_generate_summary()
    test_analyze_trend()
    test_interface_methods()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
