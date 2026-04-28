#!/usr/bin/env python3
"""Apple Health 일별 지표 SPoE — 시트 마크다운 → 파싱 → JSONL 캐시 → 조회.

배경(2026-04-25):
- Apple Watch FIT 파일에는 VO2max/HRV/안정시 심박이 없다.
- 형님 Apple Health 데이터는 자동 sync 앱이 Google Drive `Health Metrics_v5` 시트에 D+1로 푸시.
- 시트 → 마크다운 텍스트(첫 시트는 일별 활동 + VO₂ max + HRV 등)로 export됨.

이 모듈이 SPoE:
- `update_from_text(raw_md)` — 시트 마크다운을 받아 JSONL 캐시 갱신 (멱등, 중복 날짜는 최신값으로 덮어씀)
- `load_metrics()` — 캐시 → {date: dict} 반환
- `latest_metric(field, max_age_days=14)` — 특정 지표의 가장 최근 유효값 + 측정일
- `recent_avg(field, days=7)` — 최근 N일 평균 (None은 제외)
- `trend_30d(field)` — 30일 전 평균 vs 최근 7일 평균 차이

캐시: ~/.claude/data/health_metrics_log.jsonl
포맷: {"date": "YYYY-MM-DD", "vo2max": 37.5, "hrv": 28, "resting_hr": 73,
       "steps": 17163, "active_kcal": 785, "resting_kcal": 1805,
       "exercise_min": 60, "stand_hours": 12, "logged_at": "..."}

Drive MCP 호출은 이 모듈 밖(슬래시 커맨드/cron) 책임 — 텍스트만 주입받는 순수 파서/저장소.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

CACHE_FILE = Path.home() / ".claude/data/health_metrics_log.jsonl"

# 시트 헤더(마크다운) → 내부 필드명 매핑.
HEADER_MAP: dict[str, str] = {
    "Date": "date",
    "Active Energy": "active_kcal",
    "Resting Energy": "resting_kcal",
    "Resting": "resting_hr",
    "Resting Heart Rate": "resting_hr",
    "HRV": "hrv",
    "Steps": "steps",
    "VO₂ max": "vo2max",
    "VO2 max": "vo2max",
    "VO2max": "vo2max",
    "Exercise Minutes": "exercise_min",
    "Stand Hours": "stand_hours",
}

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_cell(raw: str) -> float | None:
    if raw is None:
        return None
    s = raw.strip()
    if not s or s == "—":
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    s = raw.strip().replace("\\", "")
    m = re.match(r"(\d{4})[\.\-/]\s*(\d{1,2})[\.\-/]\s*(\d{1,2})", s)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_markdown_table(raw_md: str) -> list[dict[str, Any]]:
    """시트 export 마크다운에서 첫 번째 일별 헬스 지표 표를 추출."""
    lines = raw_md.split("\n")
    headers: list[str] | None = None
    rows: list[dict[str, Any]] = []
    in_table = False

    for line in lines:
        if not line.strip().startswith("|"):
            if in_table:
                break
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]

        if not in_table:
            if "Date" in cells and ("VO₂ max" in cells or "VO2 max" in cells or "VO2max" in cells):
                headers = cells
                in_table = True
            continue

        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue

        if headers and len(cells) == len(headers):
            d_raw = cells[headers.index("Date")] if "Date" in headers else None
            d = _parse_date(d_raw) if d_raw else None
            if not d:
                if "Date" in cells:
                    break
                continue
            row: dict[str, Any] = {"date": d}
            for h, v in zip(headers, cells):
                key = HEADER_MAP.get(h)
                if not key or key == "date":
                    continue
                row[key] = _parse_cell(v)
            rows.append(row)

    return rows


def update_from_text(raw_md: str) -> dict[str, int]:
    """시트 마크다운 → JSONL 캐시 갱신 (멱등). {parsed, added, updated} 반환."""
    new_rows = parse_markdown_table(raw_md)
    if not new_rows:
        return {"parsed": 0, "added": 0, "updated": 0}

    existing = load_metrics()
    added = updated = 0
    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")

    for row in new_rows:
        d = row["date"]
        row["logged_at"] = now_iso
        if d in existing:
            old = existing[d]
            changed = any(
                row.get(k) != old.get(k)
                for k in row
                if k != "logged_at"
            )
            if changed:
                existing[d] = {**old, **row}
                updated += 1
        else:
            existing[d] = row
            added += 1

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    sorted_dates = sorted(existing.keys())
    with CACHE_FILE.open("w", encoding="utf-8") as f:
        for d in sorted_dates:
            f.write(json.dumps(existing[d], ensure_ascii=False) + "\n")

    return {"parsed": len(new_rows), "added": added, "updated": updated}


def load_metrics() -> dict[str, dict[str, Any]]:
    if not CACHE_FILE.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for line in CACHE_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if "date" in obj:
                out[obj["date"]] = obj
        except json.JSONDecodeError:
            continue
    return out


def latest_metric(
    field: str, max_age_days: int = 14, today: date | None = None
) -> tuple[float, str] | None:
    """필드의 가장 최근 유효 값 + 측정일. max_age_days 넘으면 None."""
    if today is None:
        today = date.today()
    metrics = load_metrics()
    cutoff = today - timedelta(days=max_age_days)
    for d in sorted(metrics.keys(), reverse=True):
        try:
            d_obj = date.fromisoformat(d)
        except ValueError:
            continue
        if d_obj < cutoff:
            return None
        if d_obj > today:
            continue
        v = metrics[d].get(field)
        if v is not None:
            return float(v), d
    return None


def recent_avg(field: str, days: int = 7, today: date | None = None) -> float | None:
    if today is None:
        today = date.today()
    metrics = load_metrics()
    cutoff = today - timedelta(days=days)
    vals: list[float] = []
    for d, row in metrics.items():
        try:
            d_obj = date.fromisoformat(d)
        except ValueError:
            continue
        if cutoff <= d_obj <= today:
            v = row.get(field)
            if v is not None:
                vals.append(float(v))
    if not vals:
        return None
    return sum(vals) / len(vals)


def trend_30d(field: str, today: date | None = None) -> float | None:
    """30일 전 일주일(±) 평균 vs 최근 7일 평균 차이."""
    if today is None:
        today = date.today()
    metrics = load_metrics()
    old_end = today - timedelta(days=23)
    old_start = today - timedelta(days=37)
    new_start = today - timedelta(days=7)

    old_vals: list[float] = []
    new_vals: list[float] = []
    for d, row in metrics.items():
        try:
            d_obj = date.fromisoformat(d)
        except ValueError:
            continue
        v = row.get(field)
        if v is None:
            continue
        if old_start <= d_obj <= old_end:
            old_vals.append(float(v))
        elif new_start <= d_obj <= today:
            new_vals.append(float(v))
    if not old_vals or not new_vals:
        return None
    return (sum(new_vals) / len(new_vals)) - (sum(old_vals) / len(old_vals))


# ─────────────────────────────────────────────────────────────────────────────
# 회복 분석 (rest day / active day 비교)
# 2026-04-25 추가 — 휴식일 대시보드 코칭 멘트용
# 의존: ~/.claude/data/running_log.jsonl 에서 운동/휴식 분류
# ─────────────────────────────────────────────────────────────────────────────

_RUNNING_LOG_PATH = Path.home() / ".claude/data/running_log.jsonl"


def _running_dates() -> set[str]:
    """running_log.jsonl에서 운동한 날짜 집합 반환."""
    if not _RUNNING_LOG_PATH.exists():
        return set()
    dates: set[str] = set()
    for line in _RUNNING_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line).get("date")
            if d:
                dates.add(d)
        except Exception:
            continue
    return dates


def is_rest_day(target: date | None = None) -> bool:
    """그 날(기본=오늘) 운동 안 했으면 True."""
    if target is None:
        target = date.today()
    return target.isoformat() not in _running_dates()


def compare_rest_vs_active(
    field: str,
    window_days: int = 30,
    today: date | None = None,
) -> dict[str, Any] | None:
    """최근 N일 동안 휴식일 평균 vs 운동일 평균 비교.

    반환: {
        'rest_avg': float, 'active_avg': float,
        'rest_n': int, 'active_n': int,
        'diff': float (rest - active),
        'better_when_resting': bool (HRV처럼 높을수록 좋음 + diff>0 / 안정심박처럼 낮을수록 좋음 + diff<0),
    } 또는 None (데이터 부족)
    """
    if today is None:
        today = date.today()
    metrics = load_metrics()
    run_dates = _running_dates()
    cutoff = today - timedelta(days=window_days)

    rest_vals: list[float] = []
    active_vals: list[float] = []
    for d, row in metrics.items():
        try:
            d_obj = date.fromisoformat(d)
        except ValueError:
            continue
        if not (cutoff <= d_obj <= today):
            continue
        v = row.get(field)
        if v is None:
            continue
        if d in run_dates:
            active_vals.append(float(v))
        else:
            rest_vals.append(float(v))

    if not rest_vals or not active_vals:
        return None

    rest_avg = sum(rest_vals) / len(rest_vals)
    active_avg = sum(active_vals) / len(active_vals)
    diff = rest_avg - active_avg

    # "휴식일이 더 좋은가" 판단: 메트릭별 방향성
    higher_better = {"hrv", "vo2max"}  # 높을수록 좋음
    lower_better = {"resting_hr"}      # 낮을수록 좋음
    if field in higher_better:
        better_when_resting = diff > 0
    elif field in lower_better:
        better_when_resting = diff < 0
    else:
        better_when_resting = False  # 방향성 모호한 메트릭

    return {
        "rest_avg": round(rest_avg, 1),
        "active_avg": round(active_avg, 1),
        "rest_n": len(rest_vals),
        "active_n": len(active_vals),
        "diff": round(diff, 1),
        "better_when_resting": better_when_resting,
    }


def today_vs_baseline(
    field: str,
    today: date | None = None,
    baseline_days: int = 30,
) -> dict[str, Any] | None:
    """오늘 값을 N일 베이스라인 평균과 비교.

    반환: {
        'today': float, 'baseline_avg': float, 'diff': float, 'pct': float,
        'is_better': bool (메트릭 방향성 적용),
    } 또는 None
    """
    if today is None:
        today = date.today()
    metrics = load_metrics()
    row = metrics.get(today.isoformat())
    today_val = row.get(field) if row else None
    if today_val is None:
        # 오늘 값 없으면 가장 최근 7일 안의 값으로 폴백
        result = latest_metric(field, max_age_days=7, today=today)
        if result is None:
            return None
        today_val = result[0]
    today_val = float(today_val)
    baseline = recent_avg(field, days=baseline_days, today=today - timedelta(days=1))
    if baseline is None or baseline == 0:
        return None
    diff = today_val - baseline
    pct = (diff / baseline) * 100

    higher_better = {"hrv", "vo2max", "exercise_min", "stand_hours", "steps"}
    lower_better = {"resting_hr"}
    if field in higher_better:
        is_better = diff > 0
    elif field in lower_better:
        is_better = diff < 0
    else:
        is_better = False

    return {
        "today": round(today_val, 1),
        "baseline_avg": round(baseline, 1),
        "diff": round(diff, 1),
        "pct": round(pct, 1),
        "is_better": is_better,
    }


def consecutive_rest_days(today: date | None = None) -> int:
    """오늘부터 거꾸로 세어 연속 휴식일 수. 오늘 운동했으면 0."""
    if today is None:
        today = date.today()
    run_dates = _running_dates()
    n = 0
    for i in range(60):  # 최대 60일까지만 검사
        d = (today - timedelta(days=i)).isoformat()
        if d in run_dates:
            break
        n += 1
    return n


def vo2max_trend_summary(today: date | None = None) -> dict[str, Any] | None:
    """VO2max 트렌드 — 누적 체력 변화 추적 전용.

    VO2max는 Apple Watch가 야외 러닝 시에만 갱신하므로 휴식일 vs 운동일 비교가 부적절.
    대신 측정된 모든 값의 시계열 평균을 비교해서 "체력이 늘었나/줄었나"를 본다.

    반환: {
        'latest': float | None,           # 가장 최근 측정값
        'latest_date': str | None,
        'avg_7d': float | None,           # 최근 7일 평균
        'avg_30d': float | None,          # 최근 30일 평균
        'avg_90d': float | None,          # 최근 90일 평균
        'trend_30d': float | None,        # 30일 전 일주일 평균 vs 최근 7일 평균
        'trend_90d_vs_30d': float | None, # 30일 평균 - 90일 평균 (양수면 최근 상승)
        'sample_n_30d': int,
        'sample_n_90d': int,
    }
    """
    if today is None:
        today = date.today()
    metrics = load_metrics()

    # 최근 측정값 (max 30일 안)
    latest_val = None
    latest_date = None
    for d in sorted(metrics.keys(), reverse=True):
        try:
            d_obj = date.fromisoformat(d)
        except ValueError:
            continue
        if d_obj > today:
            continue
        if (today - d_obj).days > 30:
            break
        v = metrics[d].get("vo2max")
        if v is not None:
            latest_val = float(v)
            latest_date = d
            break

    avg_7d = recent_avg("vo2max", days=7, today=today)
    avg_30d = recent_avg("vo2max", days=30, today=today)
    avg_90d = recent_avg("vo2max", days=90, today=today)
    trend_30 = trend_30d("vo2max", today=today)

    trend_90_vs_30 = None
    if avg_30d is not None and avg_90d is not None:
        trend_90_vs_30 = round(avg_30d - avg_90d, 2)

    # 표본 개수 (NULL 제외)
    n_30 = 0
    n_90 = 0
    for d, row in metrics.items():
        try:
            d_obj = date.fromisoformat(d)
        except ValueError:
            continue
        if row.get("vo2max") is None:
            continue
        days_ago = (today - d_obj).days
        if 0 <= days_ago <= 30:
            n_30 += 1
        if 0 <= days_ago <= 90:
            n_90 += 1

    return {
        "latest": round(latest_val, 1) if latest_val is not None else None,
        "latest_date": latest_date,
        "avg_7d": round(avg_7d, 1) if avg_7d is not None else None,
        "avg_30d": round(avg_30d, 1) if avg_30d is not None else None,
        "avg_90d": round(avg_90d, 1) if avg_90d is not None else None,
        "trend_30d": round(trend_30, 2) if trend_30 is not None else None,
        "trend_90d_vs_30d": trend_90_vs_30,
        "sample_n_30d": n_30,
        "sample_n_90d": n_90,
    }


def recovery_snapshot(today: date | None = None) -> dict[str, Any]:
    """오늘 휴식 코칭에 필요한 데이터 한 방에 묶기.

    반환: {
        'date': '2026-04-26',
        'is_rest_day': bool,
        'consecutive_rest_days': int,
        'metrics': {
            'hrv': {today_vs_baseline 결과 or None},
            'resting_hr': {...},
            'steps': {...},
        },
        'rest_vs_active_30d': {
            'hrv': {compare_rest_vs_active 결과},
            'resting_hr': {...},
        },
    }
    """
    if today is None:
        today = date.today()
    return {
        "date": today.isoformat(),
        "is_rest_day": is_rest_day(today),
        "consecutive_rest_days": consecutive_rest_days(today),
        # VO2max는 today_vs_baseline 부적절(매일 측정 X) → vo2max_trend로 별도 처리
        "metrics": {
            f: today_vs_baseline(f, today=today)
            for f in ("hrv", "resting_hr", "steps", "exercise_min", "stand_hours")
        },
        # VO2max는 Apple Watch가 야외 러닝 시에만 측정/갱신 → 휴식일 표본 부족
        # → 휴식 vs 운동 비교 부적절. 별도 trend_summary로 누적 체력 변화 추적
        "rest_vs_active_30d": {
            f: compare_rest_vs_active(f, window_days=30, today=today)
            for f in ("hrv", "resting_hr", "steps", "exercise_min", "stand_hours")
        },
        "vo2max_trend": vo2max_trend_summary(today=today),
    }


def _selftest() -> None:
    sample = """
|  Date  |  Active Energy  |  Resting Energy  |  Resting  |  HRV  |  Steps  |  VO₂ max  |  Exercise Minutes  |  Stand Hours  |
| :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| 2026\\. 4. 23 | 785 kcal | 1805 kcal | 73 bpm | 28 | 17163 | 37.4 | 60 | 12 |
| 2026\\. 4. 22 | 759 kcal | 1707 kcal |  | 40 | 21549 | 37.5 | 77 | 3 |
| 2026\\. 4. 21 | 377 kcal | 1761 kcal | 71 bpm | 36 | 7491 |  | 13 | 11 |

|  Date  |  Time  |  Systolic  |  Diastolic  |  Data Source  |
| :-: | :-: | :-: | :-: | :-: |
"""
    rows = parse_markdown_table(sample)
    assert len(rows) == 3, f"expected 3 rows, got {len(rows)}: {rows}"
    assert rows[0]["date"] == "2026-04-23", rows[0]
    assert rows[0]["vo2max"] == 37.4
    assert rows[0]["resting_hr"] == 73
    assert rows[1]["resting_hr"] is None
    assert rows[2]["vo2max"] is None
    print("✅ parse_markdown_table OK (3 rows)")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    elif len(sys.argv) > 1 and sys.argv[1] == "show":
        m = load_metrics()
        if not m:
            print("(캐시 비어있음)")
        else:
            for d in sorted(m.keys())[-10:]:
                print(d, m[d])
    elif len(sys.argv) > 2 and sys.argv[1] == "ingest":
        text = Path(sys.argv[2]).read_text(encoding="utf-8")
        result = update_from_text(text)
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("usage: health_metrics_pull.py [selftest|show|ingest <md_file>]")
