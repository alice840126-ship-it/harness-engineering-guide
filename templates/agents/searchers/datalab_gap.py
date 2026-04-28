#!/usr/bin/env python3
"""datalab_gap — 네이버 DataLab 검색량 slope + 경쟁도 gap.

블로그 키워드 교차검증용. SNS(YouTube/Instagram)에서 선행 터진 키워드를
DataLab으로 확인해서:
    1. slope  : 최근 주별 검색량 추세 (상승/안정/하락)
    2. volume : 현재 검색량 (상대값, 0~100)
    3. gap    : 검색량 대비 네이버 블로그 경쟁도 — "내가 비집고 들어갈 틈"

원본 로직은 ~/.claude/scripts/trend_hunter.py `fetch_datalab_trends`에서 복제.
trend_hunter.py는 건드리지 않고 이 모듈이 독립적으로 돈다.

NAVER_CLIENT_ID/SECRET 없으면 graceful skip.

CLI:
    python3 datalab_gap.py selftest
    python3 datalab_gap.py search "토마토주스,올리브오일"
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv as _load
    _load(Path.home() / ".claude" / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from injection_shield import scan as _scan
except Exception:
    _scan = None


def _creds() -> tuple[str, str]:
    return (
        os.getenv("NAVER_CLIENT_ID", "").strip(),
        os.getenv("NAVER_CLIENT_SECRET", "").strip(),
    )


def _compute_slope(ratios: list[float]) -> float:
    """최근 4주 평균 대비 직전 4주 평균 증감률(%).

    데이터 부족 시 단순 (last-prev)/prev*100.
    """
    if not ratios:
        return 0.0
    if len(ratios) >= 8:
        recent = sum(ratios[-4:]) / 4.0
        prior = sum(ratios[-8:-4]) / 4.0
    elif len(ratios) >= 2:
        recent = ratios[-1]
        prior = ratios[-2]
    else:
        return 0.0
    if prior <= 0:
        return 100.0 if recent > 0 else 0.0
    return round((recent - prior) / prior * 100.0, 2)


def _label_trend(slope: float) -> str:
    if slope > 20:
        return "🔺급상승"
    if slope > 5:
        return "▲상승"
    if slope > -5:
        return "→안정"
    if slope > -20:
        return "▽하락"
    return "🔻급하락"


def _competition_gap(blog_count: int, ratio: float) -> float:
    """블로그 경쟁도 gap 점수 (높을수록 비집고 들어갈 틈 큼).

    ratio(검색량 0~100) 대비 blog_count가 상대적으로 적으면 gap↑.
    간단한 스코어: ratio * 10 / log10(blog_count+10)
    """
    import math
    return round(ratio * 10.0 / math.log10(max(blog_count, 1) + 10), 2)


def _naver_blog_count(keyword: str, cid: str, cs: str) -> int:
    """네이버 검색 API로 블로그 경쟁도(전체 문서수) 조회."""
    try:
        import requests
        r = requests.get(
            "https://openapi.naver.com/v1/search/blog.json",
            params={"query": keyword, "display": 1},
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": cs},
            timeout=8,
        )
        if r.status_code != 200:
            return 0
        return int(r.json().get("total", 0) or 0)
    except Exception:
        return 0


def _datalab_batch(keywords: list[str], cid: str, cs: str) -> dict[str, list[float]]:
    """DataLab 배치 조회 — 키워드당 주별 ratio 리스트."""
    try:
        import requests
        now = datetime.now()
        start = (now - timedelta(days=70)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        out: dict[str, list[float]] = {}
        # DataLab API: 배치당 최대 5개
        for i in range(0, len(keywords), 5):
            chunk = keywords[i:i + 5]
            groups = [{"groupName": k, "keywords": [k]} for k in chunk]
            r = requests.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={
                    "X-Naver-Client-Id": cid,
                    "X-Naver-Client-Secret": cs,
                    "Content-Type": "application/json",
                },
                json={
                    "startDate": start,
                    "endDate": end,
                    "timeUnit": "week",
                    "keywordGroups": groups,
                },
                timeout=10,
            )
            if r.status_code != 200:
                continue
            for g in r.json().get("results", []):
                name = g.get("title", "")
                ratios = [float(w.get("ratio", 0) or 0) for w in g.get("data", [])]
                out[name] = ratios
        return out
    except Exception as e:
        print(f"[datalab_gap] 배치 실패: {e}")
        return {}


def _datalab_yearly_batch(keywords: list[str], cid: str, cs: str) -> dict[str, list[float]]:
    """12개월 월간 ratio (지속 추세 감지용)."""
    try:
        import requests
        now = datetime.now()
        start = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        out: dict[str, list[float]] = {}
        for i in range(0, len(keywords), 5):
            chunk = keywords[i:i + 5]
            groups = [{"groupName": k, "keywords": [k]} for k in chunk]
            r = requests.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": cs,
                         "Content-Type": "application/json"},
                json={"startDate": start, "endDate": end, "timeUnit": "month",
                      "keywordGroups": groups},
                timeout=12,
            )
            if r.status_code != 200:
                continue
            for g in r.json().get("results", []):
                name = g.get("title", "")
                ratios = [float(w.get("ratio", 0) or 0) for w in g.get("data", [])]
                out[name] = ratios
        return out
    except Exception as e:
        print(f"[datalab_gap] yearly 배치 실패: {e}")
        return {}


def _compute_long_slope(ratios: list[float]) -> float:
    """12개월 후반 6개월 평균 vs 전반 6개월 평균 증감률."""
    if len(ratios) < 6:
        return 0.0
    half = len(ratios) // 2
    prior = sum(ratios[:half]) / max(half, 1)
    recent = sum(ratios[half:]) / max(len(ratios) - half, 1)
    if prior <= 0:
        return 100.0 if recent > 0 else 0.0
    return round((recent - prior) / prior * 100.0, 2)


def yearly_slopes(keywords: list[str]) -> dict[str, float]:
    """키워드별 12개월 지속 추세 slope(%)."""
    cid, cs = _creds()
    if not (cid and cs) or not keywords:
        return {}
    kws = [str(k).strip() for k in keywords if str(k).strip()]
    ratios_map = _datalab_yearly_batch(kws, cid, cs)
    return {k: _compute_long_slope(ratios_map.get(k, [])) for k in kws}


def search(query, limit: int = 20) -> list[dict[str, Any]]:
    """키워드(단일 or 리스트) → DataLab slope + 경쟁도 gap.

    Returns: [{"title","source","url","score","metadata"}, ...]
    score는 slope × gap 가중 합성.
    """
    if isinstance(query, str):
        keywords = [k.strip() for k in query.split(",") if k.strip()]
    else:
        keywords = [str(k).strip() for k in query if str(k).strip()]
    if not keywords:
        return []

    cid, cs = _creds()
    if not (cid and cs):
        return []

    ratios_map = _datalab_batch(keywords[:limit], cid, cs)
    if not ratios_map:
        return []

    out: list[dict[str, Any]] = []
    for kw in keywords[:limit]:
        ratios = ratios_map.get(kw, [])
        if not ratios:
            continue
        slope = _compute_slope(ratios)
        current = ratios[-1] if ratios else 0.0
        blog_count = _naver_blog_count(kw, cid, cs)
        gap = _competition_gap(blog_count, current)

        # 합성 점수: slope(±)는 40%, gap 60%
        score = round(slope * 0.4 + gap * 0.6, 2)
        trend = _label_trend(slope)
        out.append({
            "title": f"{kw} {trend} (검색량 {current:.0f}, slope {slope:+.1f}%, 블로그 {blog_count:,}건)",
            "source": "datalab",
            "url": f"https://search.naver.com/search.naver?where=nexearch&query={kw}",
            "score": score,
            "metadata": {
                "keyword": kw,
                "slope_pct": slope,
                "current_ratio": current,
                "blog_count": blog_count,
                "gap": gap,
                "trend_label": trend,
                "weeks": len(ratios),
            },
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


# ------------- selftest -------------
def _selftest() -> int:
    passed = 0
    total = 6

    # case 1: slope — 꾸준히 상승하는 시리즈
    up = [10, 12, 13, 14, 20, 22, 24, 26]
    s = _compute_slope(up)
    assert s > 0, f"상승 시리즈가 양수여야: {s}"
    print(f"  ✓ case 1 상승 slope ({s}%)")
    passed += 1

    # case 2: slope — 하락 시리즈
    down = [50, 48, 45, 42, 30, 28, 25, 20]
    s = _compute_slope(down)
    assert s < 0, f"하락 시리즈가 음수여야: {s}"
    print(f"  ✓ case 2 하락 slope ({s}%)")
    passed += 1

    # case 3: 라벨링
    assert _label_trend(30) == "🔺급상승"
    assert _label_trend(10) == "▲상승"
    assert _label_trend(0) == "→안정"
    assert _label_trend(-10) == "▽하락"
    assert _label_trend(-30) == "🔻급하락"
    print("  ✓ case 3 trend 라벨링 5단계")
    passed += 1

    # case 4: gap — 경쟁 적을수록 gap 높음
    g_crowded = _competition_gap(1_000_000, 50)
    g_niche = _competition_gap(1_000, 50)
    assert g_niche > g_crowded
    print(f"  ✓ case 4 경쟁 gap ({g_crowded} < {g_niche})")
    passed += 1

    # case 5: creds 없으면 graceful skip
    orig_id = os.environ.pop("NAVER_CLIENT_ID", None)
    orig_sec = os.environ.pop("NAVER_CLIENT_SECRET", None)
    try:
        rows = search("테스트", limit=3)
        assert rows == [], f"cred 없으면 빈 리스트: {rows}"
        print("  ✓ case 5 no-cred graceful skip")
        passed += 1
    finally:
        if orig_id:
            os.environ["NAVER_CLIENT_ID"] = orig_id
        if orig_sec:
            os.environ["NAVER_CLIENT_SECRET"] = orig_sec

    # case 6: 빈 쿼리 → 빈 리스트
    assert search("", limit=5) == []
    assert search([], limit=5) == []
    print("  ✓ case 6 빈 쿼리 안전")
    passed += 1

    # case 7: long_slope 계산 — 12개월 전반/후반 비교
    total = 7
    yearly_up = [10, 11, 12, 13, 14, 15, 20, 22, 25, 28, 30, 32]
    ls = _compute_long_slope(yearly_up)
    assert ls > 0, f"장기 상승이 양수여야: {ls}"
    yearly_down = [50, 48, 45, 42, 40, 38, 25, 22, 20, 18, 15, 12]
    ls2 = _compute_long_slope(yearly_down)
    assert ls2 < 0, f"장기 하락이 음수여야: {ls2}"
    # cred 없을 때 yearly_slopes → {}
    orig_id = os.environ.pop("NAVER_CLIENT_ID", None)
    orig_sec = os.environ.pop("NAVER_CLIENT_SECRET", None)
    try:
        assert yearly_slopes(["test"]) == {}, "no-cred 시 {}"
    finally:
        if orig_id:
            os.environ["NAVER_CLIENT_ID"] = orig_id
        if orig_sec:
            os.environ["NAVER_CLIENT_SECRET"] = orig_sec
    print(f"  ✓ case 7 12개월 long_slope (up={ls}, down={ls2})")
    passed += 1

    print(f"✅ selftest passed: {passed}/{total}"
          + ("  (NAVER creds 없어 실제 호출 skip)" if not all(_creds()) else ""))
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
            print("usage: datalab_gap.py search '키워드1,키워드2'")
            return 1
        rows = search(sys.argv[2])
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
