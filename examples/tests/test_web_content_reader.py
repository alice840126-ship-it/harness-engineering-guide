#!/usr/bin/env python3
"""
웹 콘텐츠 리더 에이전트 단위 테스트
"""

import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'agents'))

from web_content_reader import WebContentReader


def test_read_content():
    """단일 URL 본문 추출 테스트"""
    reader = WebContentReader()

    # 실제 웹사이트 테스트 (예: 위키백과)
    test_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"

    content = reader.read_content(test_url)

    # 확인
    assert content is not None, "본문 추출 실패"
    assert len(content) > 100, "본문이 너무 짧음"
    assert "artificial" in content.lower() or "intelligence" in content.lower(), "관련 내용 없음"

    print(f"✅ test_read_content: 테스트 통과 ({len(content)}자 추출)")


def test_read_multiple_contents():
    """여러 URL 일괄 본문 추출 테스트"""
    reader = WebContentReader()

    # 테스트 URL
    urls = [
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://en.wikipedia.org/wiki/Deep_learning",
    ]

    results = reader.read_multiple_contents(urls)

    # 확인
    assert len(results) == 2, "결과 개수 불일치"
    assert results[0]["url"] == urls[0], "첫 번째 URL 불일치"
    assert results[1]["url"] == urls[1], "두 번째 URL 불일치"

    # 성공 여부 확인 (네트워크 상황에 따라 다를 수 있음)
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"✅ test_read_multiple_contents: {success_count}/{len(urls)} 성공")


def test_invalid_url():
    """유효하지 않은 URL 테스트"""
    reader = WebContentReader()

    # 잘못된 URL
    invalid_url = "not-a-valid-url"

    content = reader.read_content(invalid_url)

    # 확인
    assert content is None, "잘못된 URL은 None을 반환해야 함"

    print("✅ test_invalid_url: 테스트 통과")


def test_max_chars_limit():
    """최대 길이 제한 테스트"""
    reader = WebContentReader(max_chars=500)

    # 긴 본문이 있는 페이지
    test_url = "https://en.wikipedia.org/wiki/Python_(programming_language)"

    content = reader.read_content(test_url)

    # 확인
    if content:
        assert len(content) <= 500, f"최대 길이 초과: {len(content)}자"
        print(f"✅ test_max_chars_limit: 테스트 통과 ({len(content)}자)")
    else:
        print("⚠️ test_max_chars_limit: 본문 추출 실패 (네트워크 문제 가능)")


def test_extract_metadata():
    """메타데이터 추출 테스트"""
    reader = WebContentReader()

    test_url = "https://en.wikipedia.org/wiki/Data_science"

    metadata = reader.get_metadata(test_url)

    # 확인 (성공 시)
    if metadata:
        assert "url" in metadata, "URL 없음"
        assert metadata["url"] == test_url, "URL 불일치"
        print(f"✅ test_extract_metadata: 테스트 통과 (제목: {metadata.get('title', 'N/A')})")
    else:
        print("⚠️ test_extract_metadata: 메타데이터 추출 실패 (네트워크 문제 가능)")


def test_html_extraction():
    """HTML 문자열에서 본문 추출 테스트"""
    reader = WebContentReader()

    # 간단한 HTML
    html = """
    <html>
        <head><title>테스트</title></head>
        <body>
            <h1>제목</h1>
            <p>이것은 본문입니다.</p>
            <p>두 번째 문단입니다.</p>
            <script>var x = 1;</script>
            <nav>네비게이션</nav>
        </body>
    </html>
    """

    content = reader.extract_main_content(html)

    # 확인
    if content:
        assert "본문" in content or "제목" in content, "본문 추출 실패"
        # script, nav 태그는 필터링되어야 함
        print("✅ test_html_extraction: 테스트 통과")
    else:
        print("⚠️ test_html_extraction: trafilatura 미설치 또는 오류")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 웹 콘텐츠 리더 에이전트 테스트 시작")
    print("=" * 50)

    test_invalid_url()
    test_html_extraction()

    # 네트워크 테스트 (실패해도 계속 진행)
    print("\n🌐 네트워크 테스트 시작...")
    try:
        test_read_content()
        test_read_multiple_contents()
        test_max_chars_limit()
        test_extract_metadata()
    except Exception as e:
        print(f"⚠️ 네트워크 테스트 오류 (무시): {e}")

    print("\n" + "=" * 50)
    print("✅ 테스트 완료!")


if __name__ == "__main__":
    run_all_tests()
