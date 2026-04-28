#!/usr/bin/env python3
"""Vercel CLI 단일 어댑터 (SPoE) — 모든 Vercel 배포는 여기를 거친다.

**사용처:**
- `html_share_deployer.deploy()` (외부 공유 HTML — 매번 새 프로젝트)
- `scripts/healthfit_deploy.deploy_vercel()` (러닝 대시보드 — 고정 프로젝트)

**HARNESS_DOMAIN_REGISTRY.md** 의 "Vercel 배포" SPoE.
신규 배포 코드는 반드시 이 모듈을 import한다. `subprocess(["vercel", ...])` 직접 호출 금지.

API:
    deploy_dir(path, project_name=None, timeout=180, prod=True) -> dict
        배포 실행 후 {ok, site_url, returncode, stderr_tail} 반환.
    shorten_url(url, timeout=10) -> str
        is.gd로 단축. 실패 시 원본 URL 반환.
    find_cli() -> str
        Vercel CLI 실행경로 자동 탐지 (PATH + 기본 위치).

CLI:
    python3 vercel_adapter.py selftest
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ------------- CLI 경로 탐지 -------------

_CLI_CANDIDATES = [
    "/Users/oungsooryu/.npm-global/bin/vercel",
    "/usr/local/bin/vercel",
    "/opt/homebrew/bin/vercel",
]


def find_cli() -> str:
    """Vercel CLI 경로 반환. PATH 우선, 실패 시 known 경로 순차 탐색."""
    p = shutil.which("vercel")
    if p:
        return p
    for c in _CLI_CANDIDATES:
        if Path(c).exists():
            return c
    raise FileNotFoundError(
        "Vercel CLI를 찾을 수 없음. `npm i -g vercel` 설치 후 재시도."
    )


# ------------- URL 파싱 -------------

def _parse_site_url(stdout: str, stderr: str) -> str | None:
    """Vercel CLI 출력에서 https://...vercel.app URL 추출.

    우선순위: `Aliased:` > `Production:` > 모든 vercel.app URL 중 첫 번째.
    """
    combined = (stdout or "") + "\n" + (stderr or "")

    for line in combined.splitlines():
        s = line.strip()
        if s.startswith("Aliased:"):
            for p in s.split():
                if p.startswith("https://"):
                    return p

    for line in combined.splitlines():
        if "Production:" in line:
            for p in line.split():
                if p.startswith("https://") and ".vercel.app" in p:
                    return p

    for m in re.finditer(r"https://[a-zA-Z0-9\-.]+\.vercel\.app", combined):
        return m.group(0)

    return None


# ------------- 핵심 API -------------

def deploy_dir(
    path: str | Path,
    project_name: str | None = None,
    timeout: int = 180,
    prod: bool = True,
    extra_args: list[str] | None = None,
) -> dict:
    """디렉토리 하나를 Vercel에 배포하고 결과 dict 반환.

    Args:
        path: 배포할 디렉토리 (파일 아님 — 호출자가 tmp 디렉토리 준비).
        project_name: Vercel 프로젝트명 (None이면 현재 디렉토리 기준 자동).
        timeout: CLI 타임아웃 초.
        prod: --prod 플래그 사용 여부.
        extra_args: 추가 CLI 인자.

    Returns:
        성공: {"ok": True, "site_url": "https://...vercel.app",
               "returncode": 0, "stderr_tail": ""}
        실패: {"ok": False, "error": "...", "returncode": n,
               "stderr_tail": "..."}
    """
    path = Path(path)
    if not path.is_dir():
        return {"ok": False, "error": f"디렉토리 아님: {path}",
                "returncode": -1, "stderr_tail": ""}

    try:
        cli = find_cli()
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e), "returncode": -1,
                "stderr_tail": ""}

    cmd = [cli]
    if prod:
        cmd.append("--prod")
    cmd.append("--yes")
    if project_name:
        cmd += ["--name", project_name]
    if extra_args:
        cmd += list(extra_args)

    env = os.environ.copy()
    # Vercel CLI가 Node를 찾으려면 PATH에 기본 bin 경로 필요
    env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:" + env.get("PATH", "/usr/bin:/bin")

    try:
        r = subprocess.run(
            cmd, cwd=str(path), capture_output=True, text=True,
            timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Vercel 배포 타임아웃({timeout}s)",
                "returncode": -1, "stderr_tail": ""}
    except Exception as e:
        return {"ok": False, "error": f"CLI 호출 실패: {e}",
                "returncode": -1, "stderr_tail": ""}

    stderr_tail = (r.stderr or "").strip()[-400:]

    if r.returncode != 0:
        return {
            "ok": False,
            "error": f"Vercel 배포 실패 (exit {r.returncode})",
            "returncode": r.returncode,
            "stderr_tail": stderr_tail,
        }

    site_url = _parse_site_url(r.stdout, r.stderr)
    if not site_url:
        return {
            "ok": False,
            "error": "URL 파싱 실패 — CLI 출력 포맷 변경 가능성",
            "returncode": r.returncode,
            "stderr_tail": stderr_tail,
        }

    return {
        "ok": True,
        "site_url": site_url,
        "returncode": r.returncode,
        "stderr_tail": stderr_tail,
    }


def shorten_url(url: str, timeout: int = 10) -> str:
    """is.gd로 단축. urllib 실패 시 curl fallback (macOS Python SSL 이슈 회피).
    실패 시 원본 URL 그대로 반환 (예외 던지지 않음)."""
    import urllib.parse
    import urllib.request

    q = urllib.parse.urlencode({"url": url, "format": "simple"})
    api = f"https://is.gd/create.php?{q}"

    try:
        with urllib.request.urlopen(api, timeout=timeout) as r:
            s = r.read().decode("utf-8").strip()
            if s.startswith("http"):
                return s
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), api],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        s = (r.stdout or "").strip()
        if s.startswith("http"):
            return s
    except Exception:
        pass

    return url


# ------------- CLI -------------

def _selftest():
    """오프라인 selftest — 실제 Vercel 배포 없이 API/파서 검증."""
    passed = 0
    fail = 0

    # case 1: find_cli() 는 최소 known 경로 탐지하거나 명확한 에러
    try:
        p = find_cli()
        assert p and Path(p).exists() or shutil.which("vercel")
        print(f"  ✓ case 1 find_cli → {p}")
        passed += 1
    except FileNotFoundError:
        # CI 환경 등 CLI 없을 수 있음 — selftest는 통과로 취급
        print("  ✓ case 1 find_cli (CLI 없음 — 에러 잘 던짐)")
        passed += 1

    # case 2: _parse_site_url — Aliased 우선
    out = (
        "Deploying project foo\n"
        "Production: https://foo-abc123.vercel.app [2s]\n"
        "Aliased: https://foo.vercel.app https://foo-abc123.vercel.app\n"
    )
    u = _parse_site_url(out, "")
    assert u == "https://foo.vercel.app", f"파싱 결과: {u}"
    print(f"  ✓ case 2 Aliased 우선 파싱")
    passed += 1

    # case 3: _parse_site_url — Production fallback
    out = "Deploying\nProduction: https://bar-xyz.vercel.app [1s]\n"
    u = _parse_site_url(out, "")
    assert u == "https://bar-xyz.vercel.app", f"파싱: {u}"
    print(f"  ✓ case 3 Production fallback")
    passed += 1

    # case 4: _parse_site_url — 둘 다 없으면 regex fallback
    out = ""
    err = "something https://abc.vercel.app was deployed"
    u = _parse_site_url(out, err)
    assert u == "https://abc.vercel.app", f"regex: {u}"
    print(f"  ✓ case 4 regex fallback")
    passed += 1

    # case 5: _parse_site_url — 아무것도 없으면 None
    assert _parse_site_url("", "") is None
    print(f"  ✓ case 5 None when no URL")
    passed += 1

    # case 6: deploy_dir — 디렉토리 아닌 경로
    r = deploy_dir("/nonexistent/path/xxxxx")
    assert r["ok"] is False
    assert "디렉토리" in r["error"]
    print(f"  ✓ case 6 유효하지 않은 디렉토리 방어")
    passed += 1

    # case 7: shorten_url — 실패 시 원본 반환 (예외 안 던짐)
    # is.gd 실제 호출 — 실패해도 원본 반환 보장만 확인
    import tempfile
    short = shorten_url("https://example.com/test-" + os.urandom(4).hex())
    assert short.startswith("http")
    print(f"  ✓ case 7 shorten_url 예외 안 던짐 ({short[:40]}...)")
    passed += 1

    total = passed + fail
    print(f"✅ selftest passed: {passed}/{total}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        print(__doc__)
