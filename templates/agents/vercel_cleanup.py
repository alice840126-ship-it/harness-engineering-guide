#!/usr/bin/env python3
"""Vercel 프로젝트 정리 — 오래된 임시 배포(블로그/시각화/공유용) 자동 삭제.

**HARNESS_DOMAIN_REGISTRY.md** 의 "Vercel 프로젝트 수명관리" SPoE.

정책:
- 화이트리스트 프로젝트(영구 유지)는 절대 건드리지 않음.
- 그 외 프로젝트는 --updated 이 N일 초과면 삭제 후보.
- 기본 dry-run: 삭제 안 하고 목록만 출력.

사용:
    python3 vercel_cleanup.py list                # 전체 목록 + 분류
    python3 vercel_cleanup.py plan --days 30      # 30일 초과 삭제 대상 (dry-run)
    python3 vercel_cleanup.py exec --days 30      # 실제 삭제 (확인 플래그 필요)
    python3 vercel_cleanup.py selftest
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from vercel_adapter import find_cli


# 영구 유지 — 절대 삭제하지 않는 프로젝트 (정규식)
WHITELIST_PATTERNS = [
    r"^healthfit-ryu$",
    r"^saju-app$",
    r"^sajai-app$",
    # 그 외 장기 운영 프로젝트는 여기 추가
]


def _is_whitelisted(name: str) -> bool:
    return any(re.match(p, name) for p in WHITELIST_PATTERNS)


def _run_vercel(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    cli = find_cli()
    env = os.environ.copy()
    env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:" + env.get("PATH", "/usr/bin:/bin")
    return subprocess.run(
        [cli] + args,
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def list_projects() -> list[dict]:
    """Vercel 프로젝트 목록 반환. 각 dict는 {name, updated_label}."""
    r = _run_vercel(["projects", "ls"], timeout=90)
    if r.returncode != 0:
        raise RuntimeError(f"vercel projects ls 실패: {r.stderr}")

    projects = []
    for line in r.stdout.splitlines():
        # 예: "  healthfit-ryu  https://healthfit-ryu.vercel.app  2h  24.x"
        # 또는: "  2026-0420-xxx-04201137   --   41m   24.x"
        s = line.rstrip()
        if not s.strip():
            continue
        # 헤더 스킵
        if "Project Name" in s or "Latest Production" in s:
            continue
        parts = s.split()
        if len(parts) < 3:
            continue
        # 첫 필드 = 프로젝트명 (공백 없는 ID류)
        name = parts[0]
        if not re.match(r"^[a-zA-Z0-9_\-]+$", name):
            continue
        # updated 필드 추정 — 역순 3번째 (Node 버전 앞)
        # 안전하게 줄 전체에서 "Xh|Xd|Xm|Xmin|Xs" 패턴 추출
        m = re.search(r"\b(\d+\s*(?:s|m|min|h|d|mo|y))\b", s)
        updated = m.group(1) if m else "?"
        projects.append({"name": name, "updated": updated, "raw": s})
    return projects


def _parse_days(updated: str) -> int | None:
    """'2d' → 2, '2h' → 0, '27d' → 27, '1mo' → 30, '1y' → 365. 불확실하면 None."""
    m = re.match(r"(\d+)\s*(s|m|min|h|d|mo|y)$", updated.strip())
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit in ("s", "m", "min", "h"):
        return 0
    if unit == "d":
        return n
    if unit == "mo":
        return n * 30
    if unit == "y":
        return n * 365
    return None


def plan_cleanup(days: int) -> dict:
    """days 초과된(updated >= days) 비-화이트리스트 프로젝트 목록."""
    projects = list_projects()
    whitelist = [p for p in projects if _is_whitelisted(p["name"])]
    too_young = []
    candidates = []
    unknown = []
    for p in projects:
        if _is_whitelisted(p["name"]):
            continue
        d = _parse_days(p["updated"])
        if d is None:
            unknown.append(p)
        elif d >= days:
            candidates.append(p)
        else:
            too_young.append(p)
    return {
        "whitelist": whitelist,
        "candidates": candidates,
        "too_young": too_young,
        "unknown": unknown,
    }


def delete_project(name: str) -> bool:
    """단일 프로젝트 삭제. 성공 시 True."""
    if _is_whitelisted(name):
        raise ValueError(f"화이트리스트 프로젝트는 삭제 불가: {name}")
    r = _run_vercel(["projects", "rm", name, "--yes"], timeout=60)
    return r.returncode == 0


def exec_cleanup(days: int, confirm: bool = False) -> dict:
    """실제 삭제 실행. confirm=True 필수."""
    if not confirm:
        raise ValueError("exec_cleanup는 confirm=True 필수 (안전장치)")
    plan = plan_cleanup(days)
    deleted = []
    failed = []
    for p in plan["candidates"]:
        try:
            if delete_project(p["name"]):
                deleted.append(p["name"])
            else:
                failed.append(p["name"])
        except Exception as e:
            failed.append(f"{p['name']} ({e})")
    return {"deleted": deleted, "failed": failed, "plan": plan}


# ------------- CLI -------------

def _cli_list():
    ps = list_projects()
    print(f"총 {len(ps)}개 프로젝트:\n")
    wl = [p for p in ps if _is_whitelisted(p["name"])]
    rest = [p for p in ps if not _is_whitelisted(p["name"])]
    print(f"화이트리스트({len(wl)}): {[p['name'] for p in wl]}\n")
    print(f"기타({len(rest)}):")
    for p in rest:
        print(f"  {p['name']:<50} updated={p['updated']}")


def _cli_plan(days: int):
    plan = plan_cleanup(days)
    print(f"=== dry-run plan (days={days}) ===")
    print(f"화이트리스트(유지): {len(plan['whitelist'])}")
    print(f"너무 최근(유지):   {len(plan['too_young'])}")
    print(f"불명(유지):         {len(plan['unknown'])}")
    print(f"삭제 후보:          {len(plan['candidates'])}")
    for p in plan["candidates"]:
        print(f"  🗑️ {p['name']:<50} updated={p['updated']}")
    if plan["unknown"]:
        print(f"\n(updated 파싱 실패 — 수동 확인 필요):")
        for p in plan["unknown"][:5]:
            print(f"  ? {p['name']:<50} raw={p['updated']}")


def _cli_exec(days: int):
    ans = input(f"⚠️  {days}일 초과 프로젝트 실제 삭제하시겠습니까? (yes/NO): ")
    if ans.strip().lower() != "yes":
        print("취소됨.")
        return
    r = exec_cleanup(days, confirm=True)
    print(f"삭제 완료: {len(r['deleted'])}개")
    for n in r["deleted"]:
        print(f"  ✓ {n}")
    if r["failed"]:
        print(f"실패: {len(r['failed'])}개")
        for n in r["failed"]:
            print(f"  ✗ {n}")


def _selftest():
    """오프라인 selftest — 실제 vercel CLI 호출 안 함."""
    passed = 0

    # case 1: 화이트리스트 매칭
    assert _is_whitelisted("healthfit-ryu")
    assert _is_whitelisted("saju-app")
    assert not _is_whitelisted("blog-deploy-04201157")
    assert not _is_whitelisted("running-dashboard-04181447")
    print("  ✓ case 1 화이트리스트 매칭")
    passed += 1

    # case 2: _parse_days — 다양한 입력
    assert _parse_days("2h") == 0
    assert _parse_days("3d") == 3
    assert _parse_days("1mo") == 30
    assert _parse_days("2y") == 730
    assert _parse_days("abc") is None
    print("  ✓ case 2 _parse_days 정확")
    passed += 1

    # case 3: delete_project — 화이트리스트 거부
    try:
        delete_project("healthfit-ryu")
        assert False, "화이트리스트 삭제 통과 — 버그"
    except ValueError:
        pass
    print("  ✓ case 3 화이트리스트 삭제 방어")
    passed += 1

    # case 4: exec_cleanup confirm 없이 거부
    try:
        exec_cleanup(30)
        assert False, "confirm 없이 통과 — 버그"
    except ValueError:
        pass
    print("  ✓ case 4 exec_cleanup confirm 강제")
    passed += 1

    # case 5: plan 구조 — 빈 리스트에도 dict 반환 (list_projects 모킹)
    import unittest.mock as mock
    with mock.patch(__name__ + ".list_projects", return_value=[
        {"name": "healthfit-ryu", "updated": "2h", "raw": ""},
        {"name": "blog-old-123", "updated": "45d", "raw": ""},
        {"name": "blog-new-999", "updated": "2d", "raw": ""},
        {"name": "weird", "updated": "???", "raw": ""},
    ]):
        p = plan_cleanup(30)
        assert len(p["whitelist"]) == 1
        assert len(p["candidates"]) == 1
        assert p["candidates"][0]["name"] == "blog-old-123"
        assert len(p["too_young"]) == 1
        assert len(p["unknown"]) == 1
    print("  ✓ case 5 plan_cleanup 분류 정확")
    passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "plan", "exec", "selftest"])
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    if args.cmd == "selftest":
        _selftest()
    elif args.cmd == "list":
        _cli_list()
    elif args.cmd == "plan":
        _cli_plan(args.days)
    elif args.cmd == "exec":
        _cli_exec(args.days)
