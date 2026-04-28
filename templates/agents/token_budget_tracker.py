#!/usr/bin/env python3
"""token_budget_tracker — 세션/작업별 토큰 예산 추적 + 임계치 경고.

Part III(컨텍스트 관리) 보완 도구. cache_hit_tracker.py 와 역할 분리:
    - cache_hit_tracker: API 호출당 input/cache/output 숫자 "기록"
    - token_budget_tracker: 세션 누적 총량 + 예산 한도 + 임계치 경고 "예측/방지"

effective_input = input_tokens + cache_creation_input_tokens
    * cache_read 는 "캐시 재사용 = 예산 절감분" 이므로 누적에서 제외

사용:
    from token_budget_tracker import BudgetTracker
    bt = BudgetTracker("session_2026_04_20", budget=200_000, warn_at=0.7)
    bt.add("news_scrape", input_tokens=1200, output_tokens=300)
    if bt.should_compact():
        ...  # 호출자가 컴팩트/요약 판단

저장:
    ~/.claude/outputs/budget_logs/<session_id>.json  (atomic write)

CLI:
    python3 token_budget_tracker.py status <session_id>
    python3 token_budget_tracker.py add <session_id> --task X --input N --output N
                                       [--cache-read N] [--cache-creation N]
    python3 token_budget_tracker.py reset <session_id>
    python3 token_budget_tracker.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

BUDGET_DIR = Path.home() / ".claude/outputs/budget_logs"


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class BudgetTracker:
    """세션별 토큰 예산 트래커."""

    def __init__(
        self,
        session_id: str,
        budget: int = 200_000,
        warn_at: float = 0.7,
        base_dir: Path | None = None,
    ):
        self.session_id = session_id
        self.base_dir = base_dir or BUDGET_DIR
        self.path = self.base_dir / f"{session_id}.json"

        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            # 새 인자로 덮어쓰지 않음 (기존 세션 이어쓰기가 기본)
            # 단, 파일에 없으면 보강
            self.data.setdefault("budget", budget)
            self.data.setdefault("warn_at", warn_at)
            self.data.setdefault("warn_triggered", False)
            self.data.setdefault("critical_triggered", False)
            self.data.setdefault("calls", [])
        else:
            self.data = {
                "session_id": session_id,
                "budget": budget,
                "warn_at": warn_at,
                "started_at": datetime.now().isoformat(),
                "warn_triggered": False,
                "critical_triggered": False,
                "calls": [],
            }
            self._save()

    # --------- 내부 ---------

    def _save(self) -> None:
        self.data["updated_at"] = datetime.now().isoformat()
        _atomic_write(
            self.path, json.dumps(self.data, ensure_ascii=False, indent=2)
        )

    def _used(self) -> int:
        u = 0
        for c in self.data["calls"]:
            u += int(c.get("input", 0)) + int(c.get("cache_creation", 0))
            u += int(c.get("output", 0))
        return u

    # --------- 공개 API ---------

    def add(
        self,
        task: str,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_creation: int = 0,
    ) -> dict:
        """호출 기록. 누적 status 반환. 임계치 처음 넘을 때만 stderr 경고."""
        rec = {
            "at": datetime.now().isoformat(),
            "task": task,
            "input": int(input_tokens),
            "output": int(output_tokens),
            "cache_read": int(cache_read),
            "cache_creation": int(cache_creation),
        }
        self.data["calls"].append(rec)

        used = self._used()
        budget = self.data["budget"]
        warn_at = self.data["warn_at"]

        # 임계치 체크 (처음 넘을 때만)
        if used >= budget and not self.data.get("critical_triggered"):
            self.data["critical_triggered"] = True
            self.data["warn_triggered"] = True  # critical이면 warn도 true
            print(
                f"[budget/CRITICAL] session {self.session_id}: "
                f"예산 초과 ({used:,}/{budget:,} tokens, {used/budget*100:.0f}%)",
                file=sys.stderr,
            )
        elif (
            used >= budget * warn_at
            and not self.data.get("warn_triggered")
        ):
            self.data["warn_triggered"] = True
            print(
                f"[budget/WARN] session {self.session_id}: "
                f"{int(warn_at*100)}% 초과 ({used:,}/{budget:,} tokens)",
                file=sys.stderr,
            )

        self._save()
        return self.status()

    def status(self) -> dict[str, Any]:
        used = self._used()
        budget = self.data["budget"]
        by_task: dict[str, int] = {}
        for c in self.data["calls"]:
            t = c.get("task") or "(unnamed)"
            delta = int(c.get("input", 0)) + int(c.get("cache_creation", 0)) + int(
                c.get("output", 0)
            )
            by_task[t] = by_task.get(t, 0) + delta
        return {
            "session_id": self.session_id,
            "used": used,
            "budget": budget,
            "remaining": max(0, budget - used),
            "percent": round(used / budget * 100, 1) if budget else 0.0,
            "n_calls": len(self.data["calls"]),
            "warn_triggered": bool(self.data.get("warn_triggered")),
            "critical_triggered": bool(self.data.get("critical_triggered")),
            "by_task": by_task,
        }

    def reset(self) -> None:
        """파일 삭제 + 메모리 초기화."""
        if self.path.exists():
            self.path.unlink()
        self.data = {
            "session_id": self.session_id,
            "budget": self.data.get("budget", 200_000),
            "warn_at": self.data.get("warn_at", 0.7),
            "started_at": datetime.now().isoformat(),
            "warn_triggered": False,
            "critical_triggered": False,
            "calls": [],
        }
        self._save()

    def should_compact(self) -> bool:
        """used > budget * warn_at 이면 True."""
        budget = self.data["budget"]
        warn_at = self.data["warn_at"]
        return self._used() > budget * warn_at


# ------------- CLI -------------


def cmd_status(argv):
    if not argv:
        print("usage: status <session_id>", file=sys.stderr)
        sys.exit(2)
    bt = BudgetTracker(argv[0])
    print(json.dumps(bt.status(), ensure_ascii=False, indent=2))


def cmd_add(argv):
    if not argv:
        print("usage: add <session_id> --task X --input N --output N", file=sys.stderr)
        sys.exit(2)
    session_id = argv[0]
    ap = argparse.ArgumentParser(prog="add")
    ap.add_argument("--task", required=True)
    ap.add_argument("--input", type=int, required=True)
    ap.add_argument("--output", type=int, required=True)
    ap.add_argument("--cache-read", type=int, default=0, dest="cache_read")
    ap.add_argument("--cache-creation", type=int, default=0, dest="cache_creation")
    ap.add_argument("--budget", type=int, default=200_000)
    ap.add_argument("--warn-at", type=float, default=0.7, dest="warn_at")
    ns = ap.parse_args(argv[1:])
    bt = BudgetTracker(session_id, budget=ns.budget, warn_at=ns.warn_at)
    s = bt.add(
        task=ns.task,
        input_tokens=ns.input,
        output_tokens=ns.output,
        cache_read=ns.cache_read,
        cache_creation=ns.cache_creation,
    )
    print(json.dumps(s, ensure_ascii=False, indent=2))


def cmd_reset(argv):
    if not argv:
        print("usage: reset <session_id>", file=sys.stderr)
        sys.exit(2)
    bt = BudgetTracker(argv[0])
    bt.reset()
    print(f"✅ reset: {argv[0]}")


def main():
    if len(sys.argv) < 2:
        print(
            "usage: token_budget_tracker.py {status|add|reset|selftest} ...",
            file=sys.stderr,
        )
        sys.exit(2)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "status":
        cmd_status(rest)
    elif cmd == "add":
        cmd_add(rest)
    elif cmd == "reset":
        cmd_reset(rest)
    elif cmd == "selftest":
        _selftest()
    else:
        print(f"unknown: {cmd}", file=sys.stderr)
        sys.exit(1)


def _selftest():
    import io

    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # === case 1: 기본 추가 + status
        bt = BudgetTracker("s1", budget=1000, warn_at=0.7, base_dir=base)
        s = bt.add("t", input_tokens=60, output_tokens=40)
        assert s["used"] == 100, s
        assert s["percent"] == 10.0, s
        assert s["n_calls"] == 1
        assert s["remaining"] == 900
        assert s["by_task"]["t"] == 100
        print(f"  ✓ case 1 basic add (used=100, pct=10%)")
        passed += 1

        # === case 2: 경고 트리거 (처음만, 중복 금지)
        bt2 = BudgetTracker("s2", budget=1000, warn_at=0.7, base_dir=base)
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            bt2.add("x", input_tokens=500, output_tokens=300)  # 800 → warn
            err1 = sys.stderr.getvalue()
            sys.stderr = io.StringIO()
            bt2.add("x", input_tokens=50, output_tokens=0)  # 850, 중복 warn X
            err2 = sys.stderr.getvalue()
        finally:
            captured = sys.stderr.getvalue()
            sys.stderr = old_stderr
        assert "WARN" in err1, f"first WARN 기대: {err1!r}"
        assert "WARN" not in err2, f"중복 WARN 금지: {err2!r}"
        assert bt2.status()["warn_triggered"] is True
        print(f"  ✓ case 2 warn once only")
        passed += 1

        # === case 3: cache_read는 예산에 포함 안 됨
        bt3 = BudgetTracker("s3", budget=10_000, warn_at=0.7, base_dir=base)
        s = bt3.add(
            "cached", input_tokens=100, output_tokens=50, cache_read=5000
        )
        # effective = 100 + 50 = 150 (cache_read 500 무시)
        assert s["used"] == 150, f"cache_read 포함됨: {s}"
        # cache_creation은 포함
        s = bt3.add(
            "fresh", input_tokens=0, output_tokens=0, cache_creation=200
        )
        assert s["used"] == 350, f"cache_creation 누락: {s}"
        print(f"  ✓ case 3 cache_read 제외 / cache_creation 포함 (used=350)")
        passed += 1

        # === case 4: reset
        bt4 = BudgetTracker("s4", budget=1000, base_dir=base)
        bt4.add("a", 100, 100)
        assert bt4.status()["n_calls"] == 1
        assert bt4.path.exists()
        bt4.reset()
        st = bt4.status()
        assert st["n_calls"] == 0, st
        assert st["used"] == 0
        assert st["warn_triggered"] is False
        print(f"  ✓ case 4 reset clears state")
        passed += 1

        # === case 5: persistence
        bt5 = BudgetTracker("s5", budget=1000, base_dir=base)
        bt5.add("p", 200, 100)
        # 새 인스턴스로 이어받기
        bt5b = BudgetTracker("s5", base_dir=base)
        st = bt5b.status()
        assert st["used"] == 300, st
        assert st["n_calls"] == 1
        assert st["budget"] == 1000  # 기존 값 유지
        # should_compact
        bt5b.add("p", 500, 0)  # 총 800 > 700
        assert bt5b.should_compact() is True
        print(f"  ✓ case 5 persistence + should_compact")
        passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    main()
