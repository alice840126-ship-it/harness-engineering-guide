#!/usr/bin/env python3
"""healthfit_dashboard_gen.py 결과물에 종합 코칭 카드를 주입하는 post-processor.

흐름:
  1. python3 ~/.claude/scripts/healthfit_dashboard_gen.py all 실행
  2. /tmp/healthfit-dashboard/{daily,weekly,monthly}.html 읽기
  3. running_coach_agent에서 코칭 카드 HTML 생성
  4. <div class="goal-box"> 바로 앞에 카드 삽입 (hero-grid 다음)
  5. 재기록

민감파일(healthfit_dashboard_gen.py)을 건드리지 않기 위한 우회.
"""
from __future__ import annotations
import sys, json, subprocess, re
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from running_coach_agent import rule_based_daily_coach, weekly_coach, monthly_coach

DASH_DIR = Path("/tmp/healthfit-dashboard")
GEN_SCRIPT = Path.home() / ".claude/scripts/healthfit_dashboard_gen.py"


def run_generator(target: date | None = None) -> dict:
    """기존 대시보드 생성기 실행.
    2026-04-28 fix: target 인자를 GEN_SCRIPT에 명시 전달 (이전엔 today 강제 → 코치 카드와 헤더 mismatch)."""
    cmd = ["python3", str(GEN_SCRIPT), "all"]
    if target is not None:
        cmd.append(target.isoformat())
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"[injector] gen failed: {r.stderr[:300]}", file=sys.stderr)
        return {}
    try:
        return json.loads(r.stdout.splitlines()[-1])
    except Exception:
        return {}


_COACH_BLOCK_RE = re.compile(
    r'\s*<div class="card coach-summary"[^>]*>.*?</ul>\s*(?:<div[^>]*>.*?</div>\s*)?</div>',
    re.DOTALL,
)
def _find_hero_grid_close(html: str) -> int:
    """hero-grid의 진짜 닫는 </div> 바로 다음 위치 반환. 못 찾으면 -1."""
    start_tag = '<div class="hero-grid">'
    start = html.find(start_tag)
    if start == -1:
        return -1
    depth = 1
    pos = start + len(start_tag)
    while pos < len(html) and depth > 0:
        nxt_open = html.find('<div', pos)
        nxt_close = html.find('</div>', pos)
        if nxt_close == -1:
            return -1
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            pos = nxt_open + 4
        else:
            depth -= 1
            pos = nxt_close + 6
    return pos if depth == 0 else -1


def inject_coach_summary_top(html: str, card_html: str) -> tuple[str, bool]:
    """hero-grid 블록 바로 뒤에 종합 코칭 카드 삽입.

    위치: hero-grid(닫힘) → [여기] → (기존 다음 섹션: goal-box/경고/카드).
    이미 삽입됐으면 기존 카드를 제거 후 재삽입 (idempotent).
    """
    if not card_html:
        return html, False

    # 이미 삽입된 경우 → 제거 후 재삽입
    html = _COACH_BLOCK_RE.sub("", html, count=1)

    insert_at = _find_hero_grid_close(html)
    if insert_at == -1:
        print("[injector] hero-grid close not found", file=sys.stderr)
        return html, False

    new_html = (
        html[:insert_at]
        + "\n\n  " + card_html.strip() + "\n"
        + html[insert_at:]
    )
    return new_html, True


def inject_into_file(path: Path, coach_result: dict) -> dict:
    """단일 HTML 파일에 코칭 카드 주입. 검증 결과 dict 반환."""
    if not path.exists():
        return {"ok": False, "reason": "file_missing", "path": str(path)}
    html = path.read_text(encoding="utf-8")
    before_len = len(html)
    new_html, injected = inject_coach_summary_top(html, coach_result["html"])
    if not injected:
        return {"ok": False, "reason": "no_anchor", "path": str(path)}
    path.write_text(new_html, encoding="utf-8")

    # 검증: 카드가 실제로 존재하고 hero-grid 뒤, goal-box 앞에 있는지
    v_html = path.read_text(encoding="utf-8")
    hero_pos = v_html.find('<div class="hero-grid">')
    coach_pos = v_html.find('<div class="card coach-summary"')
    goal_pos = v_html.find('<div class="goal-box">')
    order_ok = (hero_pos != -1 and coach_pos != -1 and goal_pos != -1
                and hero_pos < coach_pos < goal_pos)

    return {
        "ok": order_ok,
        "path": str(path),
        "signal": coach_result["signal"],
        "triggered": coach_result["triggered_rules"],
        "source": coach_result["source"],
        "before_len": before_len,
        "after_len": len(v_html),
        "added_chars": len(v_html) - before_len,
        "hero_pos": hero_pos,
        "coach_pos": coach_pos,
        "goal_pos": goal_pos,
    }


def run(target: date | None = None, skip_generator: bool = False) -> dict:
    if target is None:
        target = date.today()

    if not skip_generator:
        run_generator(target)

    # 코치 결과 생성
    daily_r = rule_based_daily_coach(target)
    weekly_r = weekly_coach(target)
    monthly_r = monthly_coach(target)

    results = {
        "target": str(target),
        "daily": inject_into_file(DASH_DIR / "daily.html", daily_r),
        "weekly": inject_into_file(DASH_DIR / "weekly.html", weekly_r),
        "monthly": inject_into_file(DASH_DIR / "monthly.html", monthly_r),
    }
    return results


if __name__ == "__main__":
    target = date.today()
    skip_gen = "--skip-gen" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--date="):
            target = datetime.strptime(a.split("=", 1)[1], "%Y-%m-%d").date()
    r = run(target=target, skip_generator=skip_gen)
    print(json.dumps(r, ensure_ascii=False, indent=2))
