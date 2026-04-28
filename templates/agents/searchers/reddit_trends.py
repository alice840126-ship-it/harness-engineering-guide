#!/usr/bin/env python3
"""reddit_trends — Reddit 공개 JSON API (블로그 키워드 헌터용 복제본).

reddit_searcher.py는 형님 관심 서브레딧(selfhosted/Stoicism 등) 위주라
블로그 주제(건강/뷰티/푸드 등)와 서브레딧 풀이 다르다.

이 모듈은 blog_keyword_hunter 전용 — Core 11 도메인별 서브레딧 매핑을
내장하고 표준 인터페이스(title/source/url/score/metadata)로 반환한다.

trend_hunter.py의 Reddit 로직과도 독립 (원본은 건드리지 않음).

CLI:
    python3 reddit_trends.py selftest
    python3 reddit_trends.py search "diet" --domain 다이어트
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from injection_shield import scan as _scan
except Exception:
    _scan = None


# Core 11 도메인별 서브레딧 매핑 (블로그 타겟에 맞춘 영문권 트렌드)
DOMAIN_SUBREDDITS: dict[str, list[str]] = {
    "건강": ["Health", "Supplements", "Nutrition", "loseit"],
    "뷰티": ["SkincareAddiction", "MakeupAddiction", "AsianBeauty", "30PlusSkinCare"],
    "푸드": ["MealPrepSunday", "EatCheapAndHealthy", "recipes", "Cooking"],
    "생활": ["lifehacks", "organization", "CleaningTips", "BuyItForLife"],
    "육아": ["beyondthebump", "Parenting", "toddlers", "NewParents"],
    "아이교육": ["homeschool", "education", "ScienceBasedParenting", "ECEProfessionals"],
    "다이어트": ["loseit", "intermittentfasting", "1200isplenty", "CICO"],
    "여행": ["travel", "solotravel", "JapanTravel", "digitalnomad"],
    "반려동물": ["dogs", "cats", "AskVet", "Pets"],
    "재테크": ["personalfinance", "financialindependence", "investing", "frugal"],
    "인테리어": ["HomeDecorating", "malelivingspace", "femalelivingspace", "DesignMyRoom"],
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}


def _sanitize(text: str) -> str:
    if _scan is None:
        return (text or "")[:200]
    r = _scan(text or "")
    if r.level == "high":
        return "[⚠️ blocked]"
    return (text or "")[:200]


def _score(upvotes: int, comments: int, age_hours: float) -> float:
    """Reddit hot 유사 점수 — 업보트 + 댓글 가중, 시간 감쇠."""
    import math
    age_days = max(age_hours / 24.0, 0.01)
    recency = 1.0 / (1.0 + age_days / 7.0)  # 1주일 하프라이프
    return round(
        math.log10(max(upvotes, 1) + 1) * 2.0
        + math.log10(max(comments, 1) + 1) * 1.5
        + recency * 2.0,
        3,
    )


def _subreddits_for(domain: str | None) -> list[str]:
    if domain and domain in DOMAIN_SUBREDDITS:
        return DOMAIN_SUBREDDITS[domain]
    # 전체 플랫
    flat: list[str] = []
    for v in DOMAIN_SUBREDDITS.values():
        flat += v
    return flat[:15]


def search(query: str, limit: int = 10, domain: str | None = None) -> list[dict[str, Any]]:
    """Reddit 서브레딧 묶음에서 쿼리 검색. domain이 지정되면 해당 서브레딧만."""
    if not query:
        return []
    try:
        import requests
        from datetime import datetime, timezone

        subs = _subreddits_for(domain)
        joined = "+".join(subs)
        r = requests.get(
            f"https://www.reddit.com/r/{joined}/search.json",
            params={
                "q": query,
                "sort": "relevance",
                "t": "month",
                "limit": min(limit * 2, 25),
                "restrict_sr": "1",
            },
            headers=_HEADERS,
            timeout=12,
        )
        if r.status_code == 429:
            print("[reddit_trends] 429 rate limit — skip")
            return []
        if r.status_code != 200:
            return []
        posts = r.json().get("data", {}).get("children", [])
        now = datetime.now(timezone.utc)
        out: list[dict[str, Any]] = []
        for p in posts:
            d = p.get("data", {}) or {}
            title = _sanitize(d.get("title", ""))
            if not title or title == "[⚠️ blocked]":
                continue
            created = d.get("created_utc", 0) or 0
            try:
                age_hours = (now.timestamp() - float(created)) / 3600.0
            except Exception:
                age_hours = 720.0
            up = int(d.get("ups", 0) or 0)
            cm = int(d.get("num_comments", 0) or 0)
            out.append({
                "title": title,
                "source": "reddit",
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "score": _score(up, cm, age_hours),
                "metadata": {
                    "subreddit": d.get("subreddit", ""),
                    "upvotes": up,
                    "comments": cm,
                    "age_hours": round(age_hours, 1),
                    "upvote_ratio": d.get("upvote_ratio", 0),
                },
            })
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:limit]
    except Exception as e:
        print(f"[reddit_trends] 실패: {e}")
        return []


def top_by_domain(domain: str, limit: int = 5) -> list[dict[str, Any]]:
    """도메인 서브레딧들의 주간 top 글 (쿼리 없이)."""
    subs = _subreddits_for(domain)
    if not subs:
        return []
    try:
        import requests
        from datetime import datetime, timezone
        out: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for s in subs[:4]:  # 도메인당 최대 4개 서브레딧
            try:
                r = requests.get(
                    f"https://www.reddit.com/r/{s}/top.json",
                    params={"t": "week", "limit": limit},
                    headers=_HEADERS,
                    timeout=10,
                )
                time.sleep(0.6)  # rate limit 방어
                if r.status_code != 200:
                    continue
                for p in r.json().get("data", {}).get("children", []):
                    d = p.get("data", {}) or {}
                    title = _sanitize(d.get("title", ""))
                    if not title or title == "[⚠️ blocked]":
                        continue
                    created = d.get("created_utc", 0) or 0
                    try:
                        age_hours = (now.timestamp() - float(created)) / 3600.0
                    except Exception:
                        age_hours = 720.0
                    out.append({
                        "title": title,
                        "source": "reddit",
                        "url": f"https://reddit.com{d.get('permalink', '')}",
                        "score": _score(
                            int(d.get("ups", 0) or 0),
                            int(d.get("num_comments", 0) or 0),
                            age_hours,
                        ),
                        "metadata": {
                            "subreddit": s,
                            "upvotes": int(d.get("ups", 0) or 0),
                            "comments": int(d.get("num_comments", 0) or 0),
                            "age_hours": round(age_hours, 1),
                        },
                    })
            except Exception:
                continue
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:limit * 2]
    except Exception as e:
        print(f"[reddit_trends top_by_domain] 실패: {e}")
        return []


# ------------- selftest -------------
def _selftest() -> int:
    passed = 0
    total = 5

    # case 1: 도메인 → 서브레딧 매핑
    subs = _subreddits_for("다이어트")
    assert "loseit" in subs
    print(f"  ✓ case 1 도메인 매핑 (다이어트 → {subs[:2]}...)")
    passed += 1

    # case 2: 모든 Core 11 도메인이 매핑돼 있음
    core11 = ["건강", "뷰티", "푸드", "생활", "육아", "아이교육",
              "다이어트", "여행", "반려동물", "재테크", "인테리어"]
    for d in core11:
        assert d in DOMAIN_SUBREDDITS, f"{d} 누락"
        assert len(DOMAIN_SUBREDDITS[d]) >= 3, f"{d} 서브레딧 부족"
    print(f"  ✓ case 2 Core 11 전체 매핑 ({len(core11)}개)")
    passed += 1

    # case 3: score — 업보트 많고 신선하면 점수 높음
    s_fresh = _score(1000, 50, 10.0)
    s_old = _score(1000, 50, 500.0)
    assert s_fresh > s_old
    print(f"  ✓ case 3 신선도 가중 ({s_old} < {s_fresh})")
    passed += 1

    # case 4: 빈 쿼리 → 빈 리스트
    assert search("") == []
    print("  ✓ case 4 빈 쿼리 안전")
    passed += 1

    # case 5: 없는 도메인이어도 _subreddits_for이 fallback
    subs = _subreddits_for("존재하지않는도메인")
    assert len(subs) > 0
    print(f"  ✓ case 5 unknown 도메인 fallback ({len(subs)}개)")
    passed += 1

    print(f"✅ selftest passed: {passed}/{total}  (네트워크 호출 없이 로직만 검증)")
    return 0 if passed == total else 1


def _cli():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "selftest":
        return _selftest()
    if cmd == "search":
        if len(sys.argv) < 3:
            print("usage: reddit_trends.py search <query> [domain]")
            return 1
        q = sys.argv[2]
        d = sys.argv[3] if len(sys.argv) > 3 else None
        rows = search(q, domain=d)
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
