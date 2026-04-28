#!/usr/bin/env python3
"""pipeline_observer — 파이프라인 각 스테이지 관찰성 로거.

Context manager 패턴으로 각 스테이지의 시간·토큰·실패 이유를 JSONL로 기록한다.
~/.claude/outputs/pipeline_logs/YYYY-MM-DD.jsonl 에 누적.

사용법:
    from pipeline_observer import PipelineObserver

    obs = PipelineObserver(pipeline="blog", keyword="오칼로니 만드는 방법")
    with obs.stage("naver-analyzer") as s:
        result = run_analyzer(...)
        s.attrs(tokens=1234, blog_count=10)
    with obs.stage("blog-writer") as s:
        ...
    obs.close()

CLI (리포트 보기):
    python3 pipeline_observer.py report            # 오늘 로그 요약
    python3 pipeline_observer.py report 2026-04-20 # 특정 날짜
    python3 pipeline_observer.py stats blog        # 파이프라인별 평균 시간
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path.home() / ".claude/outputs/pipeline_logs"


def _log_path(d: date | None = None) -> Path:
    d = d or date.today()
    return LOG_DIR / f"{d.strftime('%Y-%m-%d')}.jsonl"


def _write(rec: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = _log_path()
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


class _StageCtx:
    """Stage context object — with 블록 안에서 attrs() 호출 가능."""

    def __init__(self, observer: "PipelineObserver", stage: str):
        self.observer = observer
        self.stage = stage
        self.started_at = time.time()
        self.stage_id = uuid.uuid4().hex[:8]
        self._attrs: dict[str, Any] = {}
        self.status = "running"
        self.error: str | None = None

    def attrs(self, **kw) -> None:
        """스테이지 종료 전 추가 속성 기록 (tokens, counts, urls 등)."""
        self._attrs.update(kw)

    def fail(self, reason: str) -> None:
        """명시적 실패 마킹 (예외 아니어도)."""
        self.status = "failed"
        self.error = reason


class PipelineObserver:
    """파이프라인 실행을 관찰하고 JSONL로 기록."""

    def __init__(self, pipeline: str, keyword: str = "", run_id: str | None = None,
                 extra: dict | None = None):
        self.pipeline = pipeline
        self.keyword = keyword
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.started_at = time.time()
        self.extra = extra or {}
        self.host = socket.gethostname()
        self._stages: list[dict] = []
        self._closed = False

        _write({
            "type": "pipeline_start",
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "keyword": self.keyword,
            "host": self.host,
            "started_at": datetime.now().isoformat(),
            "extra": self.extra,
        })

    @contextmanager
    def stage(self, name: str):
        ctx = _StageCtx(self, name)
        _write({
            "type": "stage_start",
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "stage": name,
            "stage_id": ctx.stage_id,
            "started_at": datetime.now().isoformat(),
        })
        try:
            yield ctx
        except Exception as e:
            ctx.status = "error"
            ctx.error = f"{type(e).__name__}: {e}"
            dur = time.time() - ctx.started_at
            _write({
                "type": "stage_end",
                "run_id": self.run_id,
                "pipeline": self.pipeline,
                "stage": name,
                "stage_id": ctx.stage_id,
                "status": "error",
                "duration_sec": round(dur, 3),
                "error": ctx.error,
                "traceback": traceback.format_exc(),
                "attrs": ctx._attrs,
                "ended_at": datetime.now().isoformat(),
            })
            self._stages.append({"stage": name, "status": "error", "duration_sec": dur})
            raise
        else:
            dur = time.time() - ctx.started_at
            status = ctx.status if ctx.status != "running" else "ok"
            _write({
                "type": "stage_end",
                "run_id": self.run_id,
                "pipeline": self.pipeline,
                "stage": name,
                "stage_id": ctx.stage_id,
                "status": status,
                "duration_sec": round(dur, 3),
                "error": ctx.error,
                "attrs": ctx._attrs,
                "ended_at": datetime.now().isoformat(),
            })
            self._stages.append({"stage": name, "status": status, "duration_sec": dur})

    def close(self, status: str = "ok") -> None:
        if self._closed:
            return
        self._closed = True
        dur = time.time() - self.started_at
        _write({
            "type": "pipeline_end",
            "run_id": self.run_id,
            "pipeline": self.pipeline,
            "keyword": self.keyword,
            "status": status,
            "duration_sec": round(dur, 3),
            "stage_count": len(self._stages),
            "stage_summary": self._stages,
            "ended_at": datetime.now().isoformat(),
        })

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close("error" if exc_type else "ok")
        return False


# ------------- CLI: report -------------

def _load_day(d: date) -> list[dict]:
    p = _log_path(d)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def cmd_report(argv: list[str]) -> None:
    d = date.fromisoformat(argv[0]) if argv else date.today()
    recs = _load_day(d)
    if not recs:
        print(f"(no logs for {d})")
        return
    runs: dict[str, dict] = {}
    for r in recs:
        rid = r.get("run_id")
        if not rid:
            continue
        if rid not in runs:
            runs[rid] = {"pipeline": r.get("pipeline"), "keyword": r.get("keyword", ""),
                         "stages": [], "status": "?", "duration": 0}
        if r["type"] == "stage_end":
            runs[rid]["stages"].append(r)
        elif r["type"] == "pipeline_end":
            runs[rid]["status"] = r.get("status", "?")
            runs[rid]["duration"] = r.get("duration_sec", 0)
    print(f"=== Pipeline Report for {d} ===\n")
    for rid, r in runs.items():
        badge = "✅" if r["status"] == "ok" else "❌"
        print(f"{badge} {r['pipeline']} [{rid}] {r['keyword']} — {r['duration']:.1f}s")
        for s in r["stages"]:
            sbadge = "✓" if s["status"] == "ok" else "✗"
            err = f" ({s['error']})" if s.get("error") else ""
            print(f"    {sbadge} {s['stage']}: {s['duration_sec']:.1f}s{err}")
        print()


def cmd_stats(argv: list[str]) -> None:
    pipeline = argv[0] if argv else None
    # 최근 7일
    from datetime import timedelta
    totals: dict[str, list[float]] = {}
    for i in range(7):
        d = date.today() - timedelta(days=i)
        for r in _load_day(d):
            if r.get("type") != "stage_end":
                continue
            if pipeline and r.get("pipeline") != pipeline:
                continue
            key = f"{r.get('pipeline')}/{r.get('stage')}"
            totals.setdefault(key, []).append(r.get("duration_sec", 0))
    if not totals:
        print("(no data)")
        return
    print(f"=== Stage Stats (last 7 days){' — ' + pipeline if pipeline else ''} ===")
    print(f"{'stage':40} {'N':>5} {'avg(s)':>8} {'max(s)':>8}")
    for k, durs in sorted(totals.items(), key=lambda kv: -sum(kv[1])):
        avg = sum(durs) / len(durs)
        print(f"{k:40} {len(durs):>5} {avg:>8.2f} {max(durs):>8.2f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "report":
        cmd_report(rest)
    elif cmd == "stats":
        cmd_stats(rest)
    elif cmd == "selftest":
        _selftest()
    else:
        print(f"unknown: {cmd}")
        sys.exit(1)


def _selftest():
    """5회 검증 루프용 self-test."""
    import tempfile
    global LOG_DIR
    with tempfile.TemporaryDirectory() as tmp:
        LOG_DIR = Path(tmp) / "logs"
        # 1. 정상 플로우
        obs = PipelineObserver("test", keyword="kw1")
        with obs.stage("s1") as s:
            time.sleep(0.05)
            s.attrs(tokens=100)
        with obs.stage("s2") as s:
            s.attrs(count=5)
        obs.close()
        # 2. 예외 플로우
        obs2 = PipelineObserver("test", keyword="kw2")
        try:
            with obs2.stage("boom"):
                raise ValueError("intentional")
        except ValueError:
            pass
        obs2.close("error")
        # 3. with 문 사용
        with PipelineObserver("test", keyword="kw3") as obs3:
            with obs3.stage("quick"):
                pass
        # 4. fail() 명시
        obs4 = PipelineObserver("test", keyword="kw4")
        with obs4.stage("soft") as s:
            s.fail("validation_failed")
        obs4.close()
        # 5. 로그 읽기 검증
        recs = _load_day(date.today())
        assert len(recs) >= 4 * 3, f"expected >= 12 records, got {len(recs)}"
        types = {r["type"] for r in recs}
        assert types >= {"pipeline_start", "stage_start", "stage_end", "pipeline_end"}
        # 에러 기록 확인
        err_recs = [r for r in recs if r.get("type") == "stage_end" and r.get("status") == "error"]
        assert any("intentional" in (r.get("error") or "") for r in err_recs), "error trace missing"
        # soft fail 확인
        fail_recs = [r for r in recs if r.get("type") == "stage_end" and r.get("status") == "failed"]
        assert fail_recs, "soft-fail missing"
        print(f"✅ selftest passed: {len(recs)} records written")


if __name__ == "__main__":
    main()
