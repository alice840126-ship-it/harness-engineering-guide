#!/usr/bin/env python3
"""러닝 코치 조언 기록/조회 SPoE.

러닝 대시보드가 매일/매주/매월 조언을 내놓을 때, 그 조언을 jsonl로 보존하고
다음 회차 대시보드가 "지난번 조언 → 오늘 실행 비교"를 만들 수 있게 해준다.

스키마 (1줄 1JSON):
    {
      "id": "uuid4",
      "date": "2026-04-22",
      "period": "daily|weekly|monthly",
      "signal": "ok|warn|tip",
      "triggered_rules": ["acwr_danger", "z45_high"],
      "summary": "이번주는 Z2 회복조깅 30분만",
      "advice_until": "2026-04-28",
      "created_at": "2026-04-22T10:00:00"
    }

compliance 체크는 직전 조언의 triggered_rules와 오늘 세션/로드를 비교.
"""
from __future__ import annotations
import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

LOG_FILE = Path.home() / ".claude/data/advice_log.jsonl"


def _ensure_parent() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def save_advice(
    period: str,
    target_date: date,
    signal: str,
    triggered_rules: list[str],
    summary: str,
    advice_until: date | None = None,
) -> dict:
    """조언 1건을 jsonl에 append. 저장된 레코드 반환."""
    assert period in ("daily", "weekly", "monthly"), period
    assert signal in ("ok", "warn", "tip"), signal
    _ensure_parent()

    if advice_until is None:
        span = {"daily": 1, "weekly": 7, "monthly": 30}[period]
        advice_until = target_date + timedelta(days=span)

    rec = {
        "id": str(uuid.uuid4()),
        "date": target_date.isoformat(),
        "period": period,
        "signal": signal,
        "triggered_rules": list(triggered_rules or []),
        "summary": (summary or "").strip()[:400],
        "advice_until": advice_until.isoformat(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _read_all() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    rows = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def get_last_advice(period: str, before: date | None = None) -> dict | None:
    """해당 period의 가장 최근 조언 1건. before 지정 시 그 날짜 이전 것만."""
    before = before or date.today()
    cands = [
        r for r in _read_all()
        if r["period"] == period and r["date"] < before.isoformat()
    ]
    if not cands:
        return None
    cands.sort(key=lambda r: r["date"])
    return cands[-1]


def get_recent_advice(period: str, days: int = 14) -> list[dict]:
    """최근 N일 조언 목록 (오래된 → 최근)."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = [r for r in _read_all() if r["period"] == period and r["date"] >= cutoff]
    rows.sort(key=lambda r: r["date"])
    return rows


def check_compliance(last_advice: dict, today_trigger: list[str],
                     today_signal: str) -> dict:
    """지난 조언을 오늘 지켰는지 판정.

    규칙 (심플 — 과하게 똑똑하게 굴지 말자):
    - 지난번이 warn이었는데 오늘도 같은 warn 룰이 또 뜸 → 위반
    - 지난번이 warn이었는데 오늘은 ok → 잘 지킴
    - 지난번이 ok/tip이었으면 무조건 neutral (비교 의미 없음)
    """
    if not last_advice:
        return {"status": "none", "note": ""}

    last_sig = last_advice.get("signal")
    last_rules = set(last_advice.get("triggered_rules") or [])
    today_rules = set(today_trigger or [])

    if last_sig != "warn":
        return {"status": "neutral", "note": ""}

    repeated = last_rules & today_rules
    if repeated:
        rules_str = ", ".join(sorted(repeated))
        return {
            "status": "violated",
            "note": f"지난번({last_advice['date']})에 경고한 {rules_str} 또 떴어요.",
            "repeated_rules": sorted(repeated),
        }

    if today_signal == "ok":
        return {
            "status": "complied",
            "note": f"지난번({last_advice['date']}) 경고 잘 지켰어요. 👍",
        }

    return {"status": "partial", "note": f"지난번({last_advice['date']}) 경고 일부 해소."}


# ───────── Selftest ─────────

def _selftest() -> None:
    import tempfile
    global LOG_FILE
    passed = 0
    with tempfile.TemporaryDirectory() as td:
        LOG_FILE = Path(td) / "advice_log.jsonl"

        today = date(2026, 4, 22)
        r1 = save_advice("daily", today, "warn", ["acwr_danger"], "회복 모드 가자")
        assert r1["period"] == "daily" and r1["signal"] == "warn"
        print("  ✓ case 1 save"); passed += 1

        r2 = save_advice("daily", today + timedelta(days=1), "ok", [], "잘했어")
        last = get_last_advice("daily", before=today + timedelta(days=2))
        assert last["signal"] == "ok"
        print("  ✓ case 2 get_last_advice"); passed += 1

        res = check_compliance(r1, ["acwr_danger", "z45_high"], "warn")
        assert res["status"] == "violated", res
        print("  ✓ case 3 compliance violated"); passed += 1

        res = check_compliance(r1, [], "ok")
        assert res["status"] == "complied", res
        print("  ✓ case 4 compliance complied"); passed += 1

        res = check_compliance(None, ["x"], "warn")
        assert res["status"] == "none"
        print("  ✓ case 5 no prior advice"); passed += 1

        res = check_compliance(r2, ["acwr_danger"], "warn")
        assert res["status"] == "neutral"
        print("  ✓ case 6 last was ok → neutral"); passed += 1

        recent = get_recent_advice("daily", days=14)
        assert len(recent) >= 1
        print("  ✓ case 7 get_recent_advice"); passed += 1

    print(f"✅ selftest passed: {passed}/7")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        print(__doc__)
        print(f"\nLog file: {LOG_FILE}")
        print(f"Records: {len(_read_all())}")
