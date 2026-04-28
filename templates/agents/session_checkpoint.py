#!/usr/bin/env python3
"""session_checkpoint — 긴 배치의 원자적 체크포인트/재개.

Part VII(회로차단) + 형님 feedback_token_expiry_resume 반영:
    - 토큰 만료·타임아웃·에러로 중단되면 처음부터 다시 돌지 말고
    - 마지막 완료 지점부터 이어서 돌기
    - 중복 실행 방지(멱등성)

파일 포맷: ~/.claude/data/checkpoints/<task_id>.json
    {
      "task_id": "blog_batch_2026_04_20",
      "started_at": "...",
      "updated_at": "...",
      "total": 50,
      "done": ["item-1", "item-2", ...],
      "failed": [{"item": "item-3", "error": "...", "at": "..."}],
      "state": {...}   # 사용자 정의 상태
    }

사용:
    from session_checkpoint import Checkpoint

    cp = Checkpoint("blog_batch_2026_04_20", total=50)
    for item in items:
        if cp.is_done(item):
            continue
        try:
            process(item)
            cp.mark_done(item)
        except Exception as e:
            cp.mark_failed(item, str(e))
            raise
    cp.finalize()

CLI:
    python3 session_checkpoint.py list                # 모든 체크포인트
    python3 session_checkpoint.py show <task_id>      # 상세
    python3 session_checkpoint.py reset <task_id>     # 삭제
    python3 session_checkpoint.py selftest
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

CHECKPOINT_DIR = Path.home() / ".claude/data/checkpoints"


def _atomic_write(path: Path, data: str) -> None:
    """쓰기 중 kill 당해도 파일 안 깨지게 tmp + rename."""
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


class Checkpoint:
    """배치 작업의 진행 상태를 원자적으로 저장/로드."""

    def __init__(self, task_id: str, total: int = 0, base_dir: Path | None = None):
        self.task_id = task_id
        self.base_dir = base_dir or CHECKPOINT_DIR
        self.path = self.base_dir / f"{task_id}.json"
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            # total은 새 값이 크면 업데이트
            if total > self.data.get("total", 0):
                self.data["total"] = total
        else:
            self.data = {
                "task_id": task_id,
                "started_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "total": total,
                "done": [],
                "failed": [],
                "state": {},
                "finalized": False,
            }
            self._save()

    def _save(self) -> None:
        self.data["updated_at"] = datetime.now().isoformat()
        _atomic_write(self.path,
                      json.dumps(self.data, ensure_ascii=False, indent=2))

    # --- 상태 조회 ---
    def is_done(self, item: str) -> bool:
        return item in self.data["done"]

    def progress(self) -> dict[str, Any]:
        done = len(self.data["done"])
        total = self.data.get("total", 0)
        return {
            "done": done,
            "total": total,
            "failed": len(self.data["failed"]),
            "pct": round(done / total * 100, 1) if total else 0.0,
            "remaining": max(0, total - done),
        }

    # --- 변경 ---
    def mark_done(self, item: str) -> None:
        if item not in self.data["done"]:
            self.data["done"].append(item)
        # 실패 목록에 있었으면 제거 (재시도 성공)
        self.data["failed"] = [f for f in self.data["failed"] if f.get("item") != item]
        self._save()

    def mark_failed(self, item: str, error: str) -> None:
        self.data["failed"].append({
            "item": item,
            "error": error[:500],
            "at": datetime.now().isoformat(),
        })
        self._save()

    def set_state(self, key: str, value: Any) -> None:
        self.data["state"][key] = value
        self._save()

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.data["state"].get(key, default)

    def finalize(self) -> None:
        self.data["finalized"] = True
        self.data["finalized_at"] = datetime.now().isoformat()
        self._save()

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self.data = {
            "task_id": self.task_id,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "total": self.data.get("total", 0),
            "done": [],
            "failed": [],
            "state": {},
            "finalized": False,
        }
        self._save()

    # --- 이터레이션 헬퍼 ---
    def filter_pending(self, items: list[str]) -> list[str]:
        """아직 안 한 것만 반환."""
        return [i for i in items if not self.is_done(i)]


# ------------- CLI -------------

def cmd_list(argv):
    if not CHECKPOINT_DIR.exists():
        print("(no checkpoints)")
        return
    for p in sorted(CHECKPOINT_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        done = len(d.get("done", []))
        total = d.get("total", 0)
        pct = f"{done/total*100:.0f}%" if total else "?"
        status = "✅" if d.get("finalized") else "⏳"
        print(f"{status} {d['task_id']:40} {done}/{total} ({pct})  updated {d.get('updated_at', '')[:19]}")


def cmd_show(argv):
    if not argv:
        print("usage: show <task_id>", file=sys.stderr)
        sys.exit(2)
    p = CHECKPOINT_DIR / f"{argv[0]}.json"
    if not p.exists():
        print(f"❌ 없음: {p}")
        sys.exit(1)
    print(p.read_text(encoding="utf-8"))


def cmd_reset(argv):
    if not argv:
        print("usage: reset <task_id>", file=sys.stderr)
        sys.exit(2)
    cp = Checkpoint(argv[0])
    cp.reset()
    print(f"✅ reset: {argv[0]}")


def main():
    if len(sys.argv) < 2:
        cmd_list([])
        return
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "list":
        cmd_list(rest)
    elif cmd == "show":
        cmd_show(rest)
    elif cmd == "reset":
        cmd_reset(rest)
    elif cmd == "selftest":
        _selftest()
    else:
        print(f"unknown: {cmd}")
        sys.exit(1)


def _selftest():
    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        # === case 1: fresh + mark_done 이어서 진행
        cp = Checkpoint("t1", total=3, base_dir=base)
        assert cp.progress() == {"done": 0, "total": 3, "failed": 0, "pct": 0.0, "remaining": 3}
        cp.mark_done("a")
        cp.mark_done("b")
        prog = cp.progress()
        assert prog["done"] == 2 and prog["pct"] == 66.7, prog
        print(f"  ✓ case 1 fresh mark_done {prog}")
        passed += 1

        # === case 2: 재로드 시 이어서 (is_done 멱등)
        cp2 = Checkpoint("t1", total=3, base_dir=base)
        assert cp2.is_done("a") and cp2.is_done("b")
        assert not cp2.is_done("c")
        pending = cp2.filter_pending(["a", "b", "c"])
        assert pending == ["c"], pending
        print(f"  ✓ case 2 resume filter_pending={pending}")
        passed += 1

        # === case 3: fail → 재시도 성공 시 failed에서 제거
        cp3 = Checkpoint("t2", total=2, base_dir=base)
        cp3.mark_failed("x", "boom")
        assert len(cp3.data["failed"]) == 1
        cp3.mark_done("x")
        assert len(cp3.data["failed"]) == 0, "retry 성공 시 failed 제거"
        assert cp3.is_done("x")
        print(f"  ✓ case 3 fail→retry→clear")
        passed += 1

        # === case 4: 원자성 — tmp 파일 남지 않음
        cp4 = Checkpoint("t3", total=100, base_dir=base)
        for i in range(20):
            cp4.mark_done(f"i{i}")
        cp4.set_state("last_batch", 20)
        tmp_files = list(base.glob(".tmp.*"))
        assert not tmp_files, f"tmp 파일 잔존: {tmp_files}"
        # 재로드해서 state 복원
        cp4b = Checkpoint("t3", base_dir=base)
        assert cp4b.get_state("last_batch") == 20
        assert cp4b.progress()["done"] == 20
        print(f"  ✓ case 4 atomic + state restore")
        passed += 1

        # === case 5: finalize + reset
        cp5 = Checkpoint("t4", total=1, base_dir=base)
        cp5.mark_done("only")
        cp5.finalize()
        assert cp5.data["finalized"]
        cp5.reset()
        assert not cp5.is_done("only")
        assert cp5.progress()["done"] == 0
        print(f"  ✓ case 5 finalize + reset")
        passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    main()
