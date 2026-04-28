#!/usr/bin/env python3
"""my_blog_stats — 내 네이버 블로그 조회수 통계 SPoE.

Playwright + 저장된 네이버 세션(~/.claude/data/naver_session.json)으로
blog.stat.naver.com/blog/rank/cv/content 페이지에서 일간/주간/월간
TOP 게시글(제목 + 조회수)을 긁어옴.

2026-04-21: trend_hunter.py의 fetch_blog_stats() 로직을 재사용 가능 모듈로 추출.
blog_keyword_hunter/weekly/trend_hunter 모두 여기서 import.

세션 파일 없으면 graceful skip (빈 결과).

사용:
    from my_blog_stats import fetch_top_posts, fetch_all_periods

    monthly = fetch_top_posts("월간", limit=10)
    all_p = fetch_all_periods(10)

CLI:
    python3 my_blog_stats.py selftest
    python3 my_blog_stats.py fetch [월간|주간|일간]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

STATE_FILE = str(Path.home() / ".claude/data/naver_session.json")
TARGET_URL = "https://blog.stat.naver.com/blog/rank/cv/content"
PERIODS = ("일간", "주간", "월간")


def _has_session() -> bool:
    p = Path(STATE_FILE)
    if not p.exists():
        return False
    try:
        with open(p) as f:
            d = json.load(f)
        return len(d.get("cookies", [])) > 0
    except Exception:
        return False


def _parse_daily_date(text: str) -> str | None:
    """페이지 상단 '2026.04.20. 달력보기' 에서 기준일 추출."""
    import re
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\.\s*\n?\s*달력보기", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"이전 기간 조회\s*\n?\s*(\d{4})\.(\d{2})\.(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _parse_rank_text(text: str, limit: int) -> list[dict[str, Any]]:
    """inner_text에서 '순위\\t제목\\t조회수' 블록 파싱."""
    start = text.find("순위\t제목")
    if start < 0:
        return []
    chunk = text[start:]
    entries: list[dict[str, Any]] = []
    for line in chunk.split("\n")[1:]:
        parts = line.strip().split("\t")
        if len(parts) >= 3 and parts[0].strip().isdigit():
            entries.append({
                "rank": int(parts[0].strip()),
                "title": parts[1].strip(),
                "views": parts[2].strip(),
            })
        if len(entries) >= limit:
            break
    return entries


def fetch_all_periods(limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    """일간/주간/월간 모두 수집. 세션 없거나 실패 시 {}."""
    if not _has_session():
        return {}

    import asyncio

    async def _collect() -> dict[str, list[dict[str, Any]]]:
        from playwright.async_api import async_playwright
        results: dict[str, list[dict[str, Any]]] = {}
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, channel="chrome")
                context = await browser.new_context(storage_state=STATE_FILE)
                page = await context.new_page()

                for period in PERIODS:
                    await page.goto(TARGET_URL, timeout=15000)
                    await page.wait_for_timeout(2000)
                    if period != "일간":
                        try:
                            btn = page.get_by_text(period, exact=True)
                            await btn.click()
                            await page.wait_for_timeout(2000)
                        except Exception:
                            continue
                    text = await page.inner_text("body")
                    entries = _parse_rank_text(text, limit)
                    if entries:
                        results[period] = entries
                    if period == "일간":
                        daily_date = _parse_daily_date(text)
                        if daily_date:
                            results["_meta"] = {"daily_date": daily_date}

                await browser.close()
        except Exception as e:
            print(f"[my_blog_stats] 수집 실패: {e}")
        return results

    try:
        return asyncio.run(_collect())
    except Exception as e:
        print(f"[my_blog_stats] 실행 실패: {e}")
        return {}


def fetch_top_posts(period: str = "월간", limit: int = 10) -> list[dict[str, Any]]:
    """단일 기간 수집."""
    if period not in PERIODS:
        raise ValueError(f"period는 {PERIODS} 중 하나여야 함: {period}")
    data = fetch_all_periods(limit)
    return data.get(period, [])


def analyze_shifts(stats: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """일간/주간/월간 교집합·차집합 분류.

    - evergreen: 3개 기간 모두 TOP에 있는 글 (꾸준 유입 → 후속/심화글 후보)
    - rising: 주간 TOP인데 월간 TOP에 없음 (최근 급상승 → 지금 쓰면 탄력)
    - falling: 월간 TOP인데 주간 TOP에 없음 (하락 → 업데이트글로 살리기)
    - daily_only: 일간만 (일회성 유입, 참고만)

    제목 키 정규화: 앞뒤 공백/이모지 제거 수준만.
    """
    def _key(t: str) -> str:
        return (t or "").strip()

    def _lst(p):
        v = stats.get(p, [])
        return v if isinstance(v, list) else []
    daily = {_key(e["title"]): e for e in _lst("일간")}
    weekly = {_key(e["title"]): e for e in _lst("주간")}
    monthly = {_key(e["title"]): e for e in _lst("월간")}

    evergreen = []
    for t, w in weekly.items():
        if t in monthly and t in daily:
            evergreen.append({
                "title": t,
                "daily_views": daily[t]["views"],
                "weekly_views": w["views"],
                "monthly_views": monthly[t]["views"],
            })

    rising = []
    for t, w in weekly.items():
        if t not in monthly:
            rising.append({
                "title": t,
                "weekly_views": w["views"],
                "weekly_rank": w["rank"],
                "in_daily": t in daily,
            })

    falling = []
    for t, m in monthly.items():
        if t not in weekly:
            falling.append({
                "title": t,
                "monthly_views": m["views"],
                "monthly_rank": m["rank"],
            })

    daily_only = []
    for t, d in daily.items():
        if t not in weekly and t not in monthly:
            daily_only.append({
                "title": t,
                "daily_views": d["views"],
                "daily_rank": d["rank"],
            })

    return {
        "evergreen": evergreen,
        "rising": rising,
        "falling": falling,
        "daily_only": daily_only,
    }


def extract_keywords(entries: list[dict[str, Any]]) -> list[str]:
    """조회수 TOP 제목에서 핵심 키워드(명사/단어) 단순 추출.

    공백/특수문자 기준 분리, 3글자 이상 한글/영문 단어만.
    """
    import re
    stop = {"그것", "이것", "저것", "여기", "거기", "저기", "오늘", "어제", "내일",
            "이거", "저거", "그거", "하는", "있는", "없는", "되는", "합니다", "이야"}
    kws: dict[str, int] = {}
    for e in entries:
        title = str(e.get("title", ""))
        for w in re.findall(r"[가-힣A-Za-z]{2,}", title):
            if w in stop:
                continue
            kws[w] = kws.get(w, 0) + 1
    return [w for w, _ in sorted(kws.items(), key=lambda kv: -kv[1])[:20]]


# ═══════════════════════════════════════════════
#  selftest
# ═══════════════════════════════════════════════
def _selftest() -> int:
    passed = 0
    total = 6

    has = _has_session()
    print(f"  ✓ case 1 세션 감지 → {'있음' if has else '없음'}")
    passed += 1

    fake = "헤더\n다른내용\n순위\t제목\t조회수\n1\t테스트 글 1\t1,234\n2\t테스트 글 2\t500\n3\t테스트 글 3\t123\n"
    entries = _parse_rank_text(fake, 10)
    assert len(entries) == 3, f"3개 파싱 필요: {entries}"
    assert entries[0]["rank"] == 1 and entries[0]["title"] == "테스트 글 1"
    assert entries[0]["views"] == "1,234"
    print(f"  ✓ case 2 rank 텍스트 파싱 ({len(entries)}건)")
    passed += 1

    entries2 = _parse_rank_text(fake, 2)
    assert len(entries2) == 2
    print("  ✓ case 3 limit 절삭")
    passed += 1

    try:
        fetch_top_posts("이상한", 5)
        assert False, "ValueError 필요"
    except ValueError:
        pass
    print("  ✓ case 4 잘못된 period → ValueError")
    passed += 1

    ents = [
        {"title": "부동산 투자 지식산업센터 덕은동 임장 후기"},
        {"title": "지식산업센터 투자 분양 매물 분석"},
        {"title": "러닝 마라톤 훈련 16주 플랜"},
    ]
    kws = extract_keywords(ents)
    assert "지식산업센터" in kws, f"빈도 TOP 누락: {kws}"
    assert "투자" in kws
    print(f"  ✓ case 5 키워드 추출 Top5 → {kws[:5]}")
    passed += 1

    stats_fake = {
        "일간": [
            {"rank": 1, "title": "A글", "views": "100"},
            {"rank": 2, "title": "B글", "views": "50"},
            {"rank": 3, "title": "D글", "views": "30"},
        ],
        "주간": [
            {"rank": 1, "title": "A글", "views": "700"},
            {"rank": 2, "title": "B글", "views": "400"},
            {"rank": 3, "title": "E글", "views": "200"},
        ],
        "월간": [
            {"rank": 1, "title": "A글", "views": "2000"},
            {"rank": 2, "title": "C글", "views": "1500"},
        ],
    }
    shifts = analyze_shifts(stats_fake)
    assert any(x["title"] == "A글" for x in shifts["evergreen"]), "A글 evergreen"
    assert any(x["title"] == "E글" for x in shifts["rising"]), "E글 rising"
    assert any(x["title"] == "C글" for x in shifts["falling"]), "C글 falling"
    assert any(x["title"] == "D글" for x in shifts["daily_only"]), "D글 daily_only"
    print(f"  ✓ case 6 shift 분석 (evergreen:{len(shifts['evergreen'])}/rising:{len(shifts['rising'])}/falling:{len(shifts['falling'])}/daily:{len(shifts['daily_only'])})")
    passed += 1

    print(f"✅ selftest passed: {passed}/{total}"
          + ("" if _has_session() else "  (세션 파일 없어 실제 수집 skip)"))
    return 0 if passed == total else 1


def _cli():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "selftest":
        return _selftest()
    if cmd == "fetch":
        period = sys.argv[2] if len(sys.argv) >= 3 else "월간"
        res = fetch_top_posts(period, 10)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
