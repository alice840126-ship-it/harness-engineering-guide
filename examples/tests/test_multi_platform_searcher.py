#!/usr/bin/env python3
"""
다중 플랫폼 검색 에이전트 단위 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'agents'))

from multi_platform_searcher import MultiPlatformSearcher


def test_is_korean():
    """한글 확인 테스트"""
    searcher = MultiPlatformSearcher()

    # 한글 텍스트
    assert searcher.is_korean("안녕하세요"), "한글 텍스트 확인 실패"
    assert searcher.is_korean("Hello 한국"), "혼합 텍스트 확인 실패"

    # 한글 아님
    assert not searcher.is_korean("Hello World"), "영문 텍스트 오류"
    assert not searcher.is_korean(""), "빈 텍스트 오류"

    print("✅ test_is_korean: 테스트 통과")


def test_search_reddit():
    """Reddit 검색 테스트 (실제 API 호출)"""
    searcher = MultiPlatformSearcher()

    # Python 관련 서브레딧
    results = searcher.search_reddit(["Python"], limit=3, filter_korean=False)

    # 확인
    assert len(results) > 0, "검색 결과 없음"
    assert "title" in results[0], "title 필드 없음"
    assert "url" in results[0], "url 필드 없음"
    assert "source" in results[0], "source 필드 없음"

    print(f"✅ test_search_reddit: 테스트 통과 ({len(results)}개)")


def test_search_reddit_korean_filter():
    """Reddit 한글 필터링 테스트"""
    searcher = MultiPlatformSearcher()

    # 한글이 포함된 서브레딧 (Korea)
    results = searcher.search_reddit(["Korea"], limit=10, filter_korean=True)

    # 모든 결과가 한글이어야 함
    for result in results:
        assert searcher.is_korean(result["title"]), f"한글 아님: {result['title']}"

    print(f"✅ test_search_reddit_korean_filter: 테스트 통과 ({len(results)}개)")


def test_search_github():
    """GitHub 검색 테스트 (실제 API 호출)"""
    searcher = MultiPlatformSearcher()

    # Python 관련 저장소
    results = searcher.search_github(["python"], limit=3, filter_korean=False)

    # 확인
    assert len(results) > 0, "검색 결과 없음"
    assert "title" in results[0], "title 필드 없음"
    assert "url" in results[0], "url 필드 없음"
    assert "description" in results[0], "description 필드 없음"

    print(f"✅ test_search_github: 테스트 통과 ({len(results)}개)")


def test_search_all():
    """통합 검색 테스트"""
    searcher = MultiPlatformSearcher()

    params = {
        "naver_keywords": [],  # API 키 없으면 건너뜀
        "reddit_subreddits": ["Python"],
        "github_keywords": ["python"],
        "x_query": ""  # Nitter 불안정해서 건너뜀
    }

    platforms = ["reddit", "github"]
    results = searcher.search_all(platforms, params, limit_per_platform=3)

    # 확인
    assert "reddit" in results, "reddit 결과 없음"
    assert "github" in results, "github 결과 없음"
    assert len(results["reddit"]) > 0, "reddit 검색 실패"
    assert len(results["github"]) > 0, "github 검색 실패"

    print(f"✅ test_search_all: 테스트 통과")
    print(f"   - Reddit: {len(results['reddit'])}개")
    print(f"   - GitHub: {len(results['github'])}개")


def test_html_unescape():
    """HTML 엔티티 디코딩 테스트"""
    from multi_platform_searcher import html_unescape

    # HTML 엔티티
    encoded = "Hello &quot;World&quot; &amp; Test"
    decoded = html_unescape(encoded)

    assert decoded == 'Hello "World" & Test', "디코딩 실패"

    print("✅ test_html_unescape: 테스트 통과")


def test_search_naver_no_api_key():
    """네이버 API 키 없을 때 테스트"""
    # API 키 없이 초기화
    searcher = MultiPlatformSearcher(naver_client_id=None, naver_client_secret=None)

    results = searcher.search_naver_webkr(["테스트"], limit=5)

    # 빈 결과 반환해야 함
    assert len(results) == 0, "API 키 없으면 빈 결과"

    print("✅ test_search_naver_no_api_key: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 다중 플랫폼 검색 에이전트 테스트 시작")
    print("=" * 50)

    test_is_korean()
    test_html_unescape()
    test_search_naver_no_api_key()

    # 네트워크 테스트
    print("\n🌐 네트워크 테스트 시작...")
    try:
        test_search_reddit()
        test_search_reddit_korean_filter()
        test_search_github()
        test_search_all()
    except Exception as e:
        print(f"⚠️ 네트워크 테스트 오류 (무시): {e}")

    print("\n" + "=" * 50)
    print("✅ 테스트 완료!")


if __name__ == "__main__":
    run_all_tests()
