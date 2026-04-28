#!/usr/bin/env python3
"""cache_hit_tracker — Anthropic prompt cache 효율 추적기.

Anthropic API 응답 usage 블록:
    {
        "input_tokens": 123,
        "cache_creation_input_tokens": 4500,  # 캐시에 새로 쓴 토큰
        "cache_read_input_tokens": 8000,      # 캐시에서 읽은 토큰 (≒ 10배 싸다)
        "output_tokens": 234
    }

이 스크립트는:
    1. record(usage, task=...) — 매 API 호출 후 로깅 (JSONL append)
    2. report(days=7)          — 주간 캐시 적중률/절감액 리포트
    3. 주간 리포트를 텔레그램으로 쏠 수 있게 포맷

캐시 적중률 계산:
    cache_hit_rate = cache_read / (input + cache_read)
        * cache_read만 실제 절감. input + cache_creation은 "새 요청"
    절감 추정 = cache_read * 0.9  (캐시 읽기 비용 ~10% 가정)

저장:
    ~/.claude/data/cache_usage.jsonl
        {"at": "...", "task": "...", "input": N, "cache_creation": N,
         "cache_read": N, "output": N, "model": "..."}

CLI:
    python3 cache_hit_tracker.py record-stdin   # stdin JSON 받아서 기록
    python3 cache_hit_tracker.py report [N]     # 최근 N일(기본 7)
    python3 cache_hit_tracker.py selftest
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

USAGE_FILE = Path.home() / ".claude/data/cache_usage.jsonl"


def record(
    usage: dict,
    task: str = "",
    model: str = "",
    path: Path | None = None,
) -> dict:
    """API usage 1건을 JSONL에 append."""
    rec = {
        "at": datetime.now().isoformat(),
        "task": task,
        "model": model or usage.get("model", ""),
        "input": int(usage.get("input_tokens", 0) or 0),
        "cache_creation": int(usage.get("cache_creation_input_tokens", 0) or 0),
        "cache_read": int(usage.get("cache_read_input_tokens", 0) or 0),
        "output": int(usage.get("output_tokens", 0) or 0),
    }
    p = path or USAGE_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load(days: int = 7, path: Path | None = None) -> list[dict]:
    p = path or USAGE_FILE
    if not p.exists():
        return []
    cutoff = datetime.now() - timedelta(days=days)
    recs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        try:
            t = datetime.fromisoformat(r["at"])
        except Exception:
            continue
        if t >= cutoff:
            recs.append(r)
    return recs


def summarize(recs: list[dict]) -> dict[str, Any]:
    if not recs:
        return {"calls": 0, "input": 0, "cache_read": 0, "cache_creation": 0,
                 "output": 0, "hit_rate": 0.0, "saved_tokens": 0,
                 "by_task": {}, "by_model": {}}
    agg = {"input": 0, "cache_read": 0, "cache_creation": 0, "output": 0}
    by_task: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    for r in recs:
        for k in agg:
            agg[k] += r.get(k, 0)
        t = r.get("task") or "(unnamed)"
        m = r.get("model") or "(unknown)"
        for bucket_key, bucket in ((t, by_task), (m, by_model)):
            b = bucket.setdefault(bucket_key, {"calls": 0, "input": 0,
                                                 "cache_read": 0,
                                                 "cache_creation": 0,
                                                 "output": 0})
            b["calls"] += 1
            for k in agg:
                b[k] += r.get(k, 0)

    total_read_candidate = agg["input"] + agg["cache_read"]
    hit_rate = (agg["cache_read"] / total_read_candidate) if total_read_candidate else 0.0
    # cache_read 가 풀프라이스 대비 ~10% 비용 → 절감 ~= cache_read * 0.9
    saved_tokens = int(agg["cache_read"] * 0.9)

    # per-task/model hit_rate
    def _attach_rate(b):
        denom = b["input"] + b["cache_read"]
        b["hit_rate"] = round(b["cache_read"] / denom, 3) if denom else 0.0
        return b

    return {
        "calls": len(recs),
        "input": agg["input"],
        "cache_read": agg["cache_read"],
        "cache_creation": agg["cache_creation"],
        "output": agg["output"],
        "hit_rate": round(hit_rate, 3),
        "saved_tokens": saved_tokens,
        "by_task": {k: _attach_rate(v) for k, v in by_task.items()},
        "by_model": {k: _attach_rate(v) for k, v in by_model.items()},
    }


def format_report(summary: dict, days: int) -> str:
    lines = [
        f"=== Cache Hit Report (last {days}d) ===",
        f"calls:          {summary['calls']}",
        f"input tokens:   {summary['input']:,}",
        f"cache read:     {summary['cache_read']:,}",
        f"cache creation: {summary['cache_creation']:,}",
        f"output tokens:  {summary['output']:,}",
        f"hit rate:       {summary['hit_rate']*100:.1f}%",
        f"saved (est):    {summary['saved_tokens']:,} tokens",
        "",
    ]
    if summary["by_task"]:
        lines.append("by task:")
        rows = sorted(summary["by_task"].items(),
                       key=lambda kv: -kv[1]["cache_read"])
        for name, b in rows[:10]:
            lines.append(
                f"  {name[:30]:30} calls={b['calls']:>4} "
                f"hit={b['hit_rate']*100:>5.1f}% "
                f"read={b['cache_read']:>8,} input={b['input']:>8,}"
            )
    if summary["by_model"]:
        lines.append("")
        lines.append("by model:")
        for name, b in summary["by_model"].items():
            lines.append(
                f"  {name[:30]:30} calls={b['calls']:>4} "
                f"hit={b['hit_rate']*100:>5.1f}%"
            )
    return "\n".join(lines)


# ------------- CLI -------------

def cmd_record_stdin(argv):
    """stdin JSON → record. 사용: echo '{"input_tokens":...}' | python3 cache_hit_tracker.py record-stdin [task] [model]."""
    task = argv[0] if argv else ""
    model = argv[1] if len(argv) > 1 else ""
    data = sys.stdin.read()
    usage = json.loads(data)
    r = record(usage, task=task, model=model)
    print(json.dumps(r, ensure_ascii=False))


def cmd_report(argv):
    days = int(argv[0]) if argv else 7
    recs = load(days=days)
    s = summarize(recs)
    print(format_report(s, days))


def main():
    if len(sys.argv) < 2:
        cmd_report([])
        return
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "record-stdin":
        cmd_record_stdin(rest)
    elif cmd == "report":
        cmd_report(rest)
    elif cmd == "selftest":
        _selftest()
    else:
        print(f"unknown: {cmd}")
        sys.exit(1)


def _selftest():
    import tempfile

    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "usage.jsonl"

        # === case 1: record 1건
        r = record({"input_tokens": 100, "cache_read_input_tokens": 500,
                     "cache_creation_input_tokens": 200, "output_tokens": 50},
                    task="blog", model="claude-opus", path=tmp_path)
        assert r["input"] == 100 and r["cache_read"] == 500
        assert tmp_path.exists()
        print(f"  ✓ case 1 record 1건")
        passed += 1

        # === case 2: 여러 건 append + load
        for i in range(5):
            record({"input_tokens": 50, "cache_read_input_tokens": 900,
                     "cache_creation_input_tokens": 0, "output_tokens": 20},
                    task="blog", model="claude-opus", path=tmp_path)
        for i in range(3):
            record({"input_tokens": 200, "cache_read_input_tokens": 0,
                     "cache_creation_input_tokens": 100, "output_tokens": 80},
                    task="analysis", model="claude-sonnet", path=tmp_path)
        # load 직접 (tmp path)
        recs = []
        for line in tmp_path.read_text(encoding="utf-8").splitlines():
            recs.append(json.loads(line))
        assert len(recs) == 9
        print(f"  ✓ case 2 append x9 ({len(recs)} recs)")
        passed += 1

        # === case 3: summarize 계산
        s = summarize(recs)
        assert s["calls"] == 9
        # input 합: 100 + 5*50 + 3*200 = 950
        assert s["input"] == 950, s["input"]
        # cache_read: 500 + 5*900 = 5000
        assert s["cache_read"] == 5000, s["cache_read"]
        # hit_rate: 5000 / (950 + 5000) = 5000/5950 ≈ 0.840
        assert 0.83 < s["hit_rate"] < 0.85, s["hit_rate"]
        # saved: 5000 * 0.9 = 4500
        assert s["saved_tokens"] == 4500
        print(f"  ✓ case 3 summarize (hit={s['hit_rate']*100:.1f}%, saved={s['saved_tokens']})")
        passed += 1

        # === case 4: by_task 분리
        assert "blog" in s["by_task"] and "analysis" in s["by_task"]
        assert s["by_task"]["blog"]["calls"] == 6
        assert s["by_task"]["analysis"]["calls"] == 3
        # analysis는 cache_read=0 → hit_rate=0
        assert s["by_task"]["analysis"]["hit_rate"] == 0.0
        # blog은 높은 hit_rate
        assert s["by_task"]["blog"]["hit_rate"] > 0.9
        print(f"  ✓ case 4 by_task (blog hit={s['by_task']['blog']['hit_rate']*100:.1f}%)")
        passed += 1

        # === case 5: format_report + 빈 데이터
        report = format_report(s, 7)
        assert "hit rate:" in report and "by task:" in report
        assert "blog" in report
        # 빈 데이터
        s_empty = summarize([])
        assert s_empty["calls"] == 0 and s_empty["hit_rate"] == 0.0
        report_empty = format_report(s_empty, 7)
        assert "calls:" in report_empty
        print(f"  ✓ case 5 format_report ({len(report)} chars)")
        passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    main()
