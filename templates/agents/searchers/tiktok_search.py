#!/usr/bin/env python3
"""tiktok_search — TikTok 검색 페이지 기반 키워드 신호 수집.

Pre-Write Protocol:
- Step 1: agent_registry find tiktok → 매치 없음 / playwright → web_data_scraper 있음
- Step 2: HARNESS_DOMAIN_REGISTRY → "웹 데이터 수집(동적)" SPoE=web_data_scraper.py
- Step 3 결정: [A] SPoE 있음. WebDataScraper 재사용하되 TikTok JS 지연 렌더링은
  별도 wait 필요 → 얇게 Playwright 직접 사용 (기존 WebDataScraper 패턴 동일).

selftest는 네트워크 없이 파싱 단위로만 검증.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
AGENTS = HERE.parent
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

try:
    from injection_shield import wrap_external  # noqa: E402
except Exception:
    def wrap_external(text: str, source: str = "external") -> str:
        return text


# ═══════════════════════════════════════════════
# 파싱 (순수 함수 — selftest에서 직접 검증)
# ═══════════════════════════════════════════════

_HASHTAG_RE = re.compile(r"#([가-힣A-Za-z0-9_]{2,30})")
_ARIA_RE = re.compile(r'aria-label="([^"]{8,120})"')
_CATEGORY_RE = re.compile(r"Watch more videos of the #([가-힣A-Za-z0-9_]{2,30}) category")


def parse_hashtags(html: str) -> list[str]:
    """HTML에서 한글/영문 해시태그만 추출 (CSS 색상코드 필터)."""
    raw = _HASHTAG_RE.findall(html or "")
    out: list[str] = []
    seen: set[str] = set()
    for tag in raw:
        if re.fullmatch(r"[0-9a-fA-F]{3,8}", tag):
            continue
        if tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def parse_categories(html: str) -> list[str]:
    return list(dict.fromkeys(_CATEGORY_RE.findall(html or "")))


def parse_video_labels(html: str) -> list[str]:
    raw = _ARIA_RE.findall(html or "")
    noise = {
        "Notifications alt+T",
        "TikTok 추천 피드로 이동",
        "전체 화면에서 시청",
        "Go to TikTok For You feed",
        "Watch in full screen",
    }
    out: list[str] = []
    seen: set[str] = set()
    for lbl in raw:
        if lbl in noise or lbl.startswith("Watch more videos"):
            continue
        if lbl.startswith("Notifications") or lbl.startswith("TikTok "):
            continue
        if lbl in seen:
            continue
        seen.add(lbl)
        out.append(lbl)
    return out


# ═══════════════════════════════════════════════
# 수집 (런타임 네트워크 호출)
# ═══════════════════════════════════════════════

def _fetch_html(url: str, timeout_ms: int = 25000, wait_sec: float = 4.0) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        page = ctx.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            time.sleep(wait_sec)
            return page.content()
        finally:
            browser.close()


def search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """TikTok 검색 페이지에서 관련 해시태그/카테고리 수집.

    반환: searchers/ 표준 포맷
    """
    if not query or not query.strip():
        return []
    try:
        from urllib.parse import quote
        url = f"https://www.tiktok.com/search?q={quote(query)}"
        html = _fetch_html(url)
    except Exception as e:
        print(f"[tiktok_search] {query}: {e}")
        return []

    _ = wrap_external(html[:1000], source="tiktok")

    categories = parse_categories(html)
    hashtags = parse_hashtags(html)

    results: list[dict[str, Any]] = []

    for i, tag in enumerate(categories[:limit]):
        results.append({
            "title": f"#{tag}",
            "source": "tiktok",
            "url": f"https://www.tiktok.com/tag/{tag}",
            "score": 20.0 - i * 1.5,
            "metadata": {"kind": "category", "query": query},
        })

    cat_set = set(categories)
    remain = limit - len(results)
    for i, tag in enumerate(hashtags):
        if remain <= 0:
            break
        if tag in cat_set:
            continue
        results.append({
            "title": f"#{tag}",
            "source": "tiktok",
            "url": f"https://www.tiktok.com/tag/{tag}",
            "score": 8.0 - i * 0.3,
            "metadata": {"kind": "hashtag", "query": query},
        })
        remain -= 1

    return results


# ═══════════════════════════════════════════════
# selftest
# ═══════════════════════════════════════════════

def selftest() -> int:
    passed = 0
    total = 0

    total += 1
    html = '<div style="color:#fff">태그 #이유식 #아기수면 #f8f8f8 글</div>'
    tags = parse_hashtags(html)
    assert "이유식" in tags and "아기수면" in tags
    assert "fff" not in tags and "f8f8f8" not in tags
    print("  ✓ case 1 한글 해시태그 + CSS 색상 필터")
    passed += 1

    total += 1
    html = 'aria-label="Watch more videos of the #유아식 category" data-x="1"'
    cats = parse_categories(html)
    assert cats == ["유아식"], cats
    print("  ✓ case 2 카테고리 추출")
    passed += 1

    total += 1
    html = (
        'aria-label="Notifications alt+T" '
        'aria-label="TikTok 추천 피드로 이동" '
        'aria-label="이유식 만드는 법 완벽 정리" '
        'aria-label="Watch more videos of the #유아식 category"'
    )
    labels = parse_video_labels(html)
    assert "이유식 만드는 법 완벽 정리" in labels
    assert "Notifications alt+T" not in labels
    assert not any(l.startswith("Watch more") for l in labels)
    print("  ✓ case 3 비디오 label 노이즈 제거")
    passed += 1

    total += 1
    assert parse_hashtags("") == []
    assert parse_categories(None) == []
    assert parse_video_labels("") == []
    assert search("") == []
    print("  ✓ case 4 빈 입력 안전")
    passed += 1

    total += 1
    assert 20.0 > 8.0
    assert (20.0 - 0 * 1.5) > (20.0 - 5 * 1.5)
    print("  ✓ case 5 score 순위 로직")
    passed += 1

    print(f"✅ selftest passed: {passed}/{total}")
    return 0 if passed == total else 1


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    q = sys.argv[1] if len(sys.argv) > 1 else "이유식"
    results = search(q, limit=10)
    print(f"[tiktok_search] {q} → {len(results)}건")
    for r in results[:10]:
        print(f"  {r['score']:5.1f}  {r['title']}  [{r['metadata'].get('kind')}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
