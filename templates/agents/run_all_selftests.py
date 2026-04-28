#!/usr/bin/env python3
"""run_all_selftests — 8개 하네스 도구 통합 검증 러너.

각 에이전트의 `selftest`를 subprocess로 순차 실행하고
하나라도 실패하면 즉시 중단. 루프 N회 반복 검증용.

사용:
    python3 run_all_selftests.py           # 1회
    python3 run_all_selftests.py --loops 5  # 5회 연속
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent

TARGETS: list[tuple[str, list[str]]] = [
    ("pipeline_observer",    [sys.executable, str(HERE / "pipeline_observer.py"), "selftest"]),
    ("blog_verdict_agent",   [sys.executable, str(HERE / "blog_verdict_agent.py"), "selftest"]),
    ("blog_rewrite_loop",    [sys.executable, str(HERE / "orchestrators/blog_rewrite_loop.py")]),  # 기본=selftest
    ("agent_registry",       [sys.executable, str(HERE / "agent_registry.py"), "selftest"]),
    ("prompt_cache_hints",   [sys.executable, str(HERE / "prompt_cache_hints.py"), "selftest"]),
    ("session_checkpoint",   [sys.executable, str(HERE / "session_checkpoint.py"), "selftest"]),
    ("image_dedup",          [sys.executable, str(HERE / "image_dedup.py"), "selftest"]),
    ("cache_hit_tracker",    [sys.executable, str(HERE / "cache_hit_tracker.py"), "selftest"]),
    ("injection_shield",     [sys.executable, str(HERE / "injection_shield.py"), "selftest"]),
    ("pipeline_agent_smoke", [sys.executable, str(HERE / "pipeline_agent_smoke.py")]),
    ("harness_integration",  [sys.executable, str(HERE / "harness_integration.py"), "selftest"]),
    ("subagent_linter",      [sys.executable, str(HERE / "subagent_linter.py"), "selftest"]),
    ("token_budget_tracker", [sys.executable, str(HERE / "token_budget_tracker.py"), "selftest"]),
    ("vercel_adapter",       [sys.executable, str(HERE / "vercel_adapter.py"), "selftest"]),
    ("vercel_cleanup",       [sys.executable, str(HERE / "vercel_cleanup.py"), "selftest"]),
    ("scaffold",             [sys.executable, str(HERE / "scaffold.py"), "selftest"]),
    ("aos_dashboard",        [sys.executable, str(HERE / "aos_dashboard.py"), "selftest"]),
    ("aos_drift_check",      [sys.executable, str(HERE / "aos_drift_check.py"), "selftest"]),
    ("pre_write_harness",    [sys.executable, str(Path.home() / ".claude/hooks/pre_write_harness_check.py"), "selftest"]),
    # 블로그 키워드 헌터 (searchers + 메인 스크립트)
    ("youtube_search",       [sys.executable, str(HERE / "searchers/youtube_search.py"), "selftest"]),
    ("instagram_chrome",     [sys.executable, str(HERE / "searchers/instagram_chrome.py"), "selftest"]),
    ("datalab_gap",          [sys.executable, str(HERE / "searchers/datalab_gap.py"), "selftest"]),
    ("reddit_trends",        [sys.executable, str(HERE / "searchers/reddit_trends.py"), "selftest"]),
    ("tiktok_search",        [sys.executable, str(HERE / "searchers/tiktok_search.py"), "selftest"]),
    ("blog_keyword_hunter",  [sys.executable, str(Path.home() / ".claude/scripts/blog_keyword_hunter.py"), "selftest"]),
    ("blog_keyword_weekly",  [sys.executable, str(Path.home() / ".claude/scripts/blog_keyword_weekly.py"), "selftest"]),
]


def run_once() -> tuple[int, int, list[str]]:
    ok = 0
    fail = 0
    fails: list[str] = []
    for name, cmd in TARGETS:
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        dur = time.time() - t0
        if r.returncode == 0:
            # 각 selftest의 마지막 "✅ selftest passed" 라인 추출
            last = [l for l in r.stdout.splitlines() if "passed" in l]
            tail = last[-1] if last else "(ok)"
            print(f"  ✅ {name:24} {dur:>5.2f}s  {tail}")
            ok += 1
        else:
            print(f"  ❌ {name:24} {dur:>5.2f}s  EXIT {r.returncode}")
            print("     STDOUT:", r.stdout[-400:].replace("\n", "\n     "))
            print("     STDERR:", r.stderr[-400:].replace("\n", "\n     "))
            fail += 1
            fails.append(name)
    return ok, fail, fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loops", type=int, default=1)
    args = ap.parse_args()

    all_ok = True
    total_start = time.time()
    for i in range(1, args.loops + 1):
        print(f"\n========== Loop {i}/{args.loops} ==========")
        ok, fail, fails = run_once()
        print(f"  → {ok} ok / {fail} fail")
        if fail:
            print(f"  실패: {fails}")
            all_ok = False
            break
    total = time.time() - total_start
    print(f"\n총 소요: {total:.1f}s")
    if all_ok:
        print(f"🎉 ALL GREEN across {args.loops} loops × {len(TARGETS)} agents = {args.loops * len(TARGETS)} selftests")
        sys.exit(0)
    else:
        print("❌ 일부 실패 — 위 로그 확인")
        sys.exit(1)


if __name__ == "__main__":
    main()
