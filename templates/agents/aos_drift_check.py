#!/usr/bin/env python3
"""aos_drift_check.py — SPoE(Single Point of Entry) Drift 주기 탐지

대상 디렉토리의 .py 파일을 스캔해서 HARNESS_DOMAIN_REGISTRY가 금지한 패턴
(예: subprocess로 vercel 직접 호출, requests로 텔레그램 API 직접 호출)을 찾는다.

CLI:
    aos_drift_check.py scan           # 실제 스캔 + 위반 개수 출력, 위반 있으면 exit 1
    aos_drift_check.py run            # scan + 위반 시 텔레그램 알림 (cron 진입점)
    aos_drift_check.py selftest       # 자체 테스트

SPoE 매핑은 HARNESS_DOMAIN_REGISTRY.md 기준:
    - vercel/netlify CLI 직접 호출 → vercel_adapter.py 사용
    - api.telegram.org requests 직접 호출 → telegram_sender.py 사용
    - anthropic.Anthropic()/client.messages.create → summarizer.py + cache_hit_tracker
    - requests + bs4 뉴스 스크랩 → news_scraper.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

HOME = Path.home()
AGENTS_DIR = Path("/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
SCRIPTS_DIR = HOME / ".claude/scripts"

# 도메인별 금지 패턴. (도메인명, 정규식, 권장 SPoE, 파일명 whitelist)
# whitelist: SPoE 모듈 자체는 내부적으로 저 패턴을 써야 하므로 제외.
RULES: list[tuple[str, re.Pattern, str, set[str]]] = [
    (
        "vercel",
        re.compile(r"""subprocess\.[^\n(]*\(\s*\[?\s*["']vercel["']"""),
        "vercel_adapter.deploy_dir",
        {"vercel_adapter.py", "aos_drift_check.py", "subagent_linter.py"},
    ),
    (
        "netlify",
        re.compile(r"""subprocess\.[^\n(]*\(\s*\[?\s*["']netlify["']"""),
        "vercel_adapter.deploy_dir (Vercel 전환 완료)",
        set(),
    ),
    (
        "telegram_direct",
        re.compile(r"""api\.telegram\.org"""),
        "telegram_sender.send_telegram_html / send_alert",
        {"telegram_sender.py", "aos_drift_check.py"},
    ),
    (
        "anthropic_raw",
        re.compile(r"""client\.messages\.create\s*\("""),
        "summarizer.Summarizer + cache_hit_tracker.record",
        {"summarizer.py", "cache_hit_tracker.py", "blog_verdict_agent.py"},
    ),
    (
        "requests_bs4_news",
        re.compile(r"""from\s+bs4\s+import|import\s+bs4"""),
        "news_scraper.NewsScraper",
        {"news_scraper.py", "web_data_scraper.py", "naver_blog_scraper.py", "news_image_collector.py",
         "geeknews_searcher.py", "github_trending_searcher.py", "ih_searcher.py", "x_searcher.py"},
    ),
]


def iter_py_files(*dirs: Path) -> Iterable[Path]:
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.py")):
            # venv·__pycache__·.venv 등 제외
            if any(part.startswith(".") or part in {"__pycache__", "venv", "node_modules"} for part in p.parts):
                continue
            yield p


def scan_file(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    violations = []
    for domain, pat, spoe, whitelist in RULES:
        if path.name in whitelist:
            continue
        for m in pat.finditer(text):
            # 라인 번호 계산
            line_no = text.count("\n", 0, m.start()) + 1
            violations.append({
                "file": str(path),
                "line": line_no,
                "domain": domain,
                "match": m.group(0)[:80],
                "spoe": spoe,
            })
    return violations


def scan_all(dirs: Iterable[Path]) -> list[dict]:
    out = []
    for p in iter_py_files(*dirs):
        out.extend(scan_file(p))
    return out


def format_report(violations: list[dict]) -> str:
    if not violations:
        return "✅ SPoE drift 없음 — 금지 패턴 미검출"
    lines = [f"🚨 SPoE drift {len(violations)}건 발견:"]
    for v in violations[:30]:
        rel = v["file"].replace(str(HOME), "~")
        lines.append(f"  • {rel}:{v['line']} [{v['domain']}] → {v['spoe']}")
    if len(violations) > 30:
        lines.append(f"  … 외 {len(violations)-30}건")
    return "\n".join(lines)


def run_scan(notify: bool = False) -> int:
    violations = scan_all([AGENTS_DIR, SCRIPTS_DIR])
    report = format_report(violations)
    print(report)
    if violations and notify:
        try:
            sys.path.insert(0, str(AGENTS_DIR))
            from telegram_sender import TelegramSender  # type: ignore
            TelegramSender().send_markdown(f"*AOS Drift 탐지*\n```\n{report[:3500]}\n```")
        except Exception as e:  # pragma: no cover
            print(f"[warn] 텔레그램 알림 실패: {e}", file=sys.stderr)
    return 1 if violations else 0


def _selftest() -> int:
    import tempfile
    passed = 0
    total = 5

    # case 1: 금지 패턴 감지
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        (tp / "bad.py").write_text('import subprocess\nsubprocess.run(["vercel", "deploy"])\n')
        v = scan_all([tp])
        assert any(x["domain"] == "vercel" for x in v), f"vercel 패턴 감지 실패: {v}"
        passed += 1
        print("✓ case 1 vercel subprocess 감지")

    # case 2: whitelist 제외
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        (tp / "vercel_adapter.py").write_text('subprocess.run(["vercel"])\n')
        v = scan_all([tp])
        assert not v, f"whitelist 미작동: {v}"
        passed += 1
        print("✓ case 2 whitelist(vercel_adapter.py) 제외")

    # case 3: telegram 직접 호출
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        (tp / "bad.py").write_text('url = "https://api.telegram.org/botXXX/sendMessage"\n')
        v = scan_all([tp])
        assert any(x["domain"] == "telegram_direct" for x in v)
        passed += 1
        print("✓ case 3 api.telegram.org 감지")

    # case 4: clean file
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        (tp / "ok.py").write_text('from telegram_sender import TelegramSender\nTelegramSender().send("hi")\n')
        v = scan_all([tp])
        assert not v
        passed += 1
        print("✓ case 4 clean 파일 통과")

    # case 5: report format
    report = format_report([{"file": "/a/b.py", "line": 3, "domain": "vercel", "match": "x", "spoe": "y"}])
    assert "SPoE drift 1건" in report and "b.py:3" in report
    passed += 1
    print("✓ case 5 report 포맷")

    print(f"✅ selftest passed: {passed}/{total}")
    return 0 if passed == total else 1


def main():
    ap = argparse.ArgumentParser(description="AOS SPoE Drift detector")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="스캔만 (exit 1 if 위반)")
    sub.add_parser("run", help="scan + 위반 시 텔레그램 (cron 진입점)")
    sub.add_parser("selftest")
    args = ap.parse_args()

    if args.cmd == "selftest":
        return _selftest()
    if args.cmd == "scan":
        return run_scan(notify=False)
    if args.cmd == "run":
        return run_scan(notify=True)
    return 2


if __name__ == "__main__":
    sys.path.insert(0, str(AGENTS_DIR))
    from harness_integration import run_as_automation  # type: ignore
    # selftest/scan/run 모두 직접 main()으로 — run_as_automation은 cron "run"에서만
    if len(sys.argv) >= 2 and sys.argv[1] == "run":
        sys.exit(run_as_automation("aos_drift_check", lambda: run_scan(notify=True),
                                    keyword="aos_drift", notify_on_fail=False))
    sys.exit(main())
