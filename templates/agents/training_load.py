#!/usr/bin/env python3
"""훈련 부하 엔진 — CTL/ATL/TSB/ACWR + Fitness CSV seed import.

공식:
    CTL (Chronic Training Load, 체력) = EWMA(TRIMP, 28일)  ← HealthFit 호환 (2026-04-24 변경, 원래 42일)
    ATL (Acute Training Load, 피로)   = EWMA(TRIMP, 7일)
    TSB (Training Stress Balance)     = CTL - ATL  (양수=컨디션 피크, 음수=피로)
    ACWR (Acute:Chronic Workload Ratio) = (7일 합 TRIMP) / (28일 평균 × 4)
          0.8~1.3 = 안전, 1.5+ = 부상 위험

EWMA: CTL_today = CTL_yesterday + (TRIMP_today - CTL_yesterday) × (1 - e^(-1/28))
     ATL_today = ATL_yesterday + (TRIMP_today - ATL_yesterday) × (1 - e^(-1/7))

저장:
    ~/.claude/data/training_load.jsonl — 매일 한 줄
        {"date": "YYYY-MM-DD", "trimp": float, "ctl": float, "atl": float, "tsb": float, "acwr": float}

CLI:
    python3 training_load.py seed [csv_path]   # Fitness-xxxx.csv에서 초기화
    python3 training_load.py update            # running_log.jsonl에서 최근 날짜 갱신
    python3 training_load.py show [N]          # 최근 N일 출력 (기본 14)
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

LOAD_FILE = Path.home() / ".claude/data/training_load.jsonl"
RUNNING_LOG = Path.home() / ".claude/data/running_log.jsonl"
DEFAULT_FITNESS_CSV = Path("/Users/oungsooryu/Library/Mobile Documents/com~apple~CloudDocs/Downloads")

# EWMA 감쇠 계수
ALPHA_CTL = 1 - math.exp(-1 / 28)  # ~0.0351 — HealthFit 호환 (2026-04-24, 원래 1/42)
ALPHA_ATL = 1 - math.exp(-1 / 7)   # ~0.1331


def load_load_history() -> list[dict]:
    if not LOAD_FILE.exists():
        return []
    rows = []
    for line in LOAD_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    rows.sort(key=lambda r: r["date"])
    return rows


def save_load_history(rows: list[dict]) -> None:
    LOAD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOAD_FILE, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def daily_trimp_from_running_log() -> dict[str, float]:
    """running_log.jsonl → date별 TRIMP 합산 (러닝만)."""
    if not RUNNING_LOG.exists():
        return {}
    daily: dict[str, float] = {}
    for line in RUNNING_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            s = json.loads(line)
        except Exception:
            continue
        if s.get("workout_type") != "러닝":
            continue
        d = s.get("date")
        t = s.get("trimp")
        if d and t is not None:
            daily[d] = daily.get(d, 0) + float(t)
    return daily


def _ewma_step(prev: float, today_trimp: float, alpha: float) -> float:
    return prev + (today_trimp - prev) * alpha


def recalc_series(daily_trimp: dict[str, float], seed_ctl: float = 0, seed_atl: float = 0,
                   start: str | None = None, end: str | None = None,
                   seed_window: list[float] | None = None) -> list[dict]:
    """연속 날짜로 CTL/ATL/TSB/ACWR 재계산.

    Args:
        daily_trimp: {date_str: trimp} — 없는 날은 0으로 채움
        seed_ctl, seed_atl: 시작일 이전 상태값
        start, end: YYYY-MM-DD (None이면 daily_trimp의 min/max)
    """
    if not daily_trimp and start is None:
        return []
    dates_sorted = sorted(daily_trimp.keys())
    start = start or dates_sorted[0]
    end = end or dates_sorted[-1]

    d_start = datetime.strptime(start, "%Y-%m-%d").date()
    d_end = datetime.strptime(end, "%Y-%m-%d").date()

    series: list[dict] = []
    ctl = seed_ctl
    atl = seed_atl
    trimp_window: list[float] = list(seed_window) if seed_window else []  # 최근 28일 TRIMP

    d = d_start
    while d <= d_end:
        ds = d.strftime("%Y-%m-%d")
        t = daily_trimp.get(ds, 0.0)
        ctl = _ewma_step(ctl, t, ALPHA_CTL)
        atl = _ewma_step(atl, t, ALPHA_ATL)
        trimp_window.append(t)
        if len(trimp_window) > 28:
            trimp_window.pop(0)

        acute_7 = sum(trimp_window[-7:])
        chronic_28_avg = (sum(trimp_window) / len(trimp_window)) * 7 if trimp_window else 0
        acwr = round(acute_7 / chronic_28_avg, 2) if chronic_28_avg > 0 else 0.0

        series.append({
            "date": ds,
            "trimp": round(t, 1),
            "ctl": round(ctl, 2),
            "atl": round(atl, 2),
            "tsb": round(ctl - atl, 2),
            "acwr": acwr,
        })
        d += timedelta(days=1)
    return series


def _parse_csv_date(s: str) -> str | None:
    """'Apr 18, 2026' 또는 'YYYY-MM-DD' → 'YYYY-MM-DD'."""
    s = s.strip().strip('"')
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def seed_from_fitness_csv(csv_path: str | Path) -> list[dict]:
    """Fitness-xxxx.csv → training_load.jsonl 초기 seed.

    CSV 컬럼: date, Fitness (CTL), Fatigue (ATL), Form (TSB), TRIMP (Exp), ACWR
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(p)
    rows: list[dict] = []
    with open(p, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            d_raw = r.get("date")
            if not d_raw:
                continue
            d = _parse_csv_date(d_raw)
            if not d:
                continue
            try:
                trimp = float(r.get("TRIMP (Exp)") or 0)
                ctl = float(r.get("Fitness (CTL)") or 0)
                atl = float(r.get("Fatigue (ATL)") or 0)
                tsb = float(r.get("Form (TSB)") or 0)
                acwr = float(r.get("ACWR") or 0) if r.get("ACWR") else 0.0
            except ValueError:
                continue
            rows.append({
                "date": d,
                "trimp": round(trimp, 1),
                "ctl": round(ctl, 2),
                "atl": round(atl, 2),
                "tsb": round(tsb, 2),
                "acwr": round(acwr, 2),
                "source": "fitness_csv_seed",
            })
    rows.sort(key=lambda x: x["date"])
    return rows


def find_latest_fitness_csv() -> Path | None:
    """~/Downloads 와 iCloud Downloads 에서 최신 Fitness-*.csv 찾기."""
    candidates = []
    for base in [Path.home() / "Downloads", DEFAULT_FITNESS_CSV]:
        if base.exists():
            for p in base.glob("Fitness-*.csv"):
                # 중복 복사본 (예: "Fitness-... 2.csv") 제외
                if " " in p.stem.split("-")[-1]:
                    continue
                candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def cmd_seed(argv: list[str]) -> None:
    csv_path = argv[0] if argv else None
    if csv_path is None:
        p = find_latest_fitness_csv()
        if p is None:
            print("❌ Fitness-*.csv 를 찾을 수 없음 (~/Downloads 또는 iCloud Downloads 확인)")
            sys.exit(1)
        csv_path = str(p)
    print(f"seed from: {csv_path}")
    rows = seed_from_fitness_csv(csv_path)
    save_load_history(rows)
    print(f"✅ {len(rows)}일치 seed 저장: {LOAD_FILE}")
    if rows:
        print(f"   범위: {rows[0]['date']} ~ {rows[-1]['date']}")
        print(f"   최신: CTL={rows[-1]['ctl']} ATL={rows[-1]['atl']} TSB={rows[-1]['tsb']} ACWR={rows[-1]['acwr']}")


def cmd_update(argv: list[str]) -> None:
    """running_log에서 신규 날짜 TRIMP를 끌어와 기존 history 뒤에 이어 계산."""
    history = load_load_history()
    if not history:
        print("⚠️ history 비어있음 → seed 먼저 실행하세요: python3 training_load.py seed")
        sys.exit(1)
    # 멱등성: 기존 running_log source 레코드는 제거 후 재계산
    history = [h for h in history if h.get("source") != "running_log"]
    if not history:
        print("⚠️ seed 기록이 없음")
        sys.exit(1)
    last = history[-1]
    daily = daily_trimp_from_running_log()
    # history 마지막 날짜 이후의 TRIMP만 사용
    start_date = datetime.strptime(last["date"], "%Y-%m-%d").date() + timedelta(days=1)
    today = date.today()
    if start_date > today:
        print(f"✅ 이미 최신 ({last['date']} 까지)")
        return
    # 해당 구간 모든 날짜 채우기 (무운동일 0)
    window = {}
    d = start_date
    while d <= today:
        ds = d.strftime("%Y-%m-%d")
        window[ds] = daily.get(ds, 0.0)
        d += timedelta(days=1)
    # 28일 TRIMP 히스토리로 ACWR 초기 창 복원
    past28 = {}
    d28 = start_date - timedelta(days=28)
    for h in history:
        if datetime.strptime(h["date"], "%Y-%m-%d").date() >= d28:
            past28[h["date"]] = h["trimp"]
    # recalc
    full = {**past28, **window}
    # 과거 28일 TRIMP window 복원 (history 마지막 28개 연속으로 가정)
    past_window = [h.get("trimp", 0.0) for h in history[-28:]]
    while len(past_window) < 28:
        past_window.insert(0, 0.0)
    series = recalc_series(
        full,
        seed_ctl=last["ctl"],
        seed_atl=last["atl"],
        start=start_date.strftime("%Y-%m-%d"),
        end=today.strftime("%Y-%m-%d"),
        seed_window=past_window,
    )
    # 이어붙이기
    for r in series:
        r["source"] = "running_log"
    save_load_history(history + series)
    print(f"✅ {len(series)}일 추가: {series[0]['date']} ~ {series[-1]['date']}")
    last_r = series[-1]
    print(f"   최신: CTL={last_r['ctl']} ATL={last_r['atl']} TSB={last_r['tsb']} ACWR={last_r['acwr']}")


def cmd_show(argv: list[str]) -> None:
    n = int(argv[0]) if argv else 14
    history = load_load_history()
    if not history:
        print("(empty)")
        return
    recent = history[-n:]
    print(f"{'date':12} {'TRIMP':>6} {'CTL':>6} {'ATL':>6} {'TSB':>7} {'ACWR':>5}")
    for r in recent:
        print(f"{r['date']:12} {r['trimp']:>6.1f} {r['ctl']:>6.2f} {r['atl']:>6.2f} {r['tsb']:>+7.2f} {r['acwr']:>5.2f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "seed":
        cmd_seed(rest)
    elif cmd == "update":
        cmd_update(rest)
    elif cmd == "show":
        cmd_show(rest)
    else:
        print(f"unknown cmd: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
