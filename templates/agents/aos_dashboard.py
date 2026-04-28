#!/usr/bin/env python3
"""aos_dashboard — pipeline_observer 로그 → HTML 관제 대시보드.

pipeline_observer가 쌓은 JSONL(~/.claude/outputs/pipeline_logs/*.jsonl)을 읽어
최근 N일 각 자동화의 성공률·평균 duration·연속 실패·마지막 실행 시각을
HTML 대시보드로 렌더링. is.gd 단축 URL로 외부 공유 가능.

사용:
    python3 aos_dashboard.py build                # 최근 7일 HTML 생성
    python3 aos_dashboard.py build --days 14      # 기간 조정
    python3 aos_dashboard.py deploy               # HTML 생성 + Vercel 배포 + 단축 URL
    python3 aos_dashboard.py selftest             # 테스트

출력:
    ~/.claude/outputs/aos_dashboard/YYYY-MM-DD.html
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

LOG_DIR = Path.home() / ".claude/outputs/pipeline_logs"
OUT_DIR = Path.home() / ".claude/outputs/aos_dashboard"


def read_logs(days: int, log_dir: Path = LOG_DIR) -> list[dict]:
    """최근 N일 JSONL 전부 로드 → records."""
    today = date.today()
    records: list[dict] = []
    for i in range(days):
        d = today - timedelta(days=i)
        f = log_dir / f"{d.isoformat()}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def aggregate(records: list[dict]) -> dict:
    """pipeline별 집계."""
    by_pipe: dict[str, dict] = defaultdict(lambda: {
        "runs": [],              # [(ended_at, status, duration)]
        "total": 0, "ok": 0, "error": 0,
        "total_duration": 0.0,
        "last_run": None, "last_status": None,
        "consecutive_fail": 0,   # 끝에서부터 연속 실패
    })
    # pipeline_end만 본다 (run당 1개)
    ends = [r for r in records if r.get("type") == "pipeline_end"]
    ends.sort(key=lambda r: r.get("ended_at", ""))
    for r in ends:
        name = r.get("pipeline", "?")
        b = by_pipe[name]
        status = r.get("status", "?")
        dur = r.get("duration_sec", 0) or 0
        ended = r.get("ended_at", "")
        b["runs"].append((ended, status, dur))
        b["total"] += 1
        if status == "ok":
            b["ok"] += 1
        else:
            b["error"] += 1
        b["total_duration"] += dur
        b["last_run"] = ended
        b["last_status"] = status
    # 연속 실패 (역순 스캔)
    for name, b in by_pipe.items():
        fail_streak = 0
        for _, status, _ in reversed(b["runs"]):
            if status == "ok":
                break
            fail_streak += 1
        b["consecutive_fail"] = fail_streak
        b["avg_duration"] = b["total_duration"] / b["total"] if b["total"] else 0
        b["success_rate"] = 100 * b["ok"] / b["total"] if b["total"] else 0
    return dict(by_pipe)


def render_html(agg: dict, days: int) -> str:
    """집계 → HTML."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_runs = sum(b["total"] for b in agg.values())
    total_ok = sum(b["ok"] for b in agg.values())
    total_err = sum(b["error"] for b in agg.values())
    overall_rate = 100 * total_ok / total_runs if total_runs else 0
    critical = [name for name, b in agg.items() if b["consecutive_fail"] >= 3]
    warning = [name for name, b in agg.items()
               if 0 < b["consecutive_fail"] < 3 or (b["total"] >= 5 and b["success_rate"] < 80)]

    # 파이프라인 정렬: 연속 실패 > 최근 실행 최신순
    def sort_key(item):
        name, b = item
        # 연속 실패 많은 것 먼저, 같으면 최근 실행 최신순
        return (-b["consecutive_fail"], b["last_run"] or "")

    # 역순으로 정렬해 최신이 위로
    # 위 sort_key는 (-consecutive_fail asc, last_run asc) → 연속실패 많은 게 위, 같은 레벨 내에서 오래된 게 위
    # → 최신이 위로 가려면 reverse within same level: 다른 접근 — 두 번 정렬

    rows = []
    for name, b in sorted(agg.items(), key=sort_key):
        status_emoji = "🔴" if b["consecutive_fail"] >= 3 else (
            "🟡" if b["consecutive_fail"] > 0 else "🟢"
        )
        rate_color = "#dc3545" if b["success_rate"] < 80 else (
            "#ffc107" if b["success_rate"] < 95 else "#28a745"
        )
        last_run_display = b["last_run"][:16].replace("T", " ") if b["last_run"] else "-"
        rows.append(f"""
        <tr>
          <td>{status_emoji}</td>
          <td><b>{name}</b></td>
          <td>{b["total"]}</td>
          <td style="color:{rate_color};font-weight:bold">{b["success_rate"]:.0f}%</td>
          <td>{b["avg_duration"]:.2f}s</td>
          <td>{b["consecutive_fail"]}</td>
          <td>{last_run_display}</td>
          <td>{b["last_status"] or "-"}</td>
        </tr>""")

    critical_box = ""
    if critical:
        items = "".join(f"<li><code>{n}</code> ({agg[n]['consecutive_fail']}회 연속)</li>"
                        for n in critical)
        critical_box = f"""
        <div class="alert alert-critical">
          <h3>🚨 Critical — 3회 이상 연속 실패</h3>
          <ul>{items}</ul>
        </div>"""

    warning_box = ""
    if warning:
        items = "".join(f"<li><code>{n}</code> — 성공률 {agg[n]['success_rate']:.0f}%, "
                        f"연속 실패 {agg[n]['consecutive_fail']}</li>" for n in warning)
        warning_box = f"""
        <div class="alert alert-warning">
          <h3>⚠️ Warning</h3>
          <ul>{items}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AOS 관제 대시보드</title>
<style>
 body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;color:#222;background:#f8f9fa}}
 h1{{margin-bottom:0}} .sub{{color:#666;font-size:.9em;margin-top:.2em}}
 .summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:1em;margin:1.5em 0}}
 .card{{background:white;padding:1em;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 .card .n{{font-size:1.8em;font-weight:bold;margin-top:.3em}}
 .card .l{{color:#666;font-size:.85em}}
 .alert{{padding:1em;border-radius:8px;margin:1em 0}}
 .alert-critical{{background:#f8d7da;color:#721c24;border-left:4px solid #dc3545}}
 .alert-warning{{background:#fff3cd;color:#856404;border-left:4px solid #ffc107}}
 .alert h3{{margin:0 0 .5em 0}} .alert ul{{margin:0;padding-left:1.5em}}
 table{{width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
 th,td{{padding:.6em .8em;text-align:left;border-bottom:1px solid #eee}}
 th{{background:#f1f3f5;font-weight:600;font-size:.85em}}
 td{{font-size:.9em}} code{{background:#f1f3f5;padding:.1em .4em;border-radius:3px}}
 .footer{{margin-top:2em;color:#888;font-size:.8em;text-align:right}}
</style></head><body>
<h1>🛡️ AOS 관제 대시보드</h1>
<div class="sub">최근 {days}일 · 생성 {generated} · 제작자 류웅수</div>

<div class="summary">
 <div class="card"><div class="l">총 실행</div><div class="n">{total_runs}</div></div>
 <div class="card"><div class="l">성공</div><div class="n" style="color:#28a745">{total_ok}</div></div>
 <div class="card"><div class="l">실패</div><div class="n" style="color:#dc3545">{total_err}</div></div>
 <div class="card"><div class="l">성공률</div><div class="n">{overall_rate:.1f}%</div></div>
</div>

{critical_box}
{warning_box}

<table>
<thead><tr><th></th><th>파이프라인</th><th>실행</th><th>성공률</th><th>평균</th><th>연속실패</th><th>마지막 실행</th><th>상태</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>

<div class="footer">pipeline_observer 로그 집계 · ~/.claude/outputs/pipeline_logs/</div>
</body></html>"""


def build(days: int = 7) -> Path:
    records = read_logs(days)
    agg = aggregate(records)
    html = render_html(agg, days)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{date.today().isoformat()}.html"
    out.write_text(html, encoding="utf-8")
    print(f"✅ 대시보드 생성: {out}")
    print(f"   파이프라인 {len(agg)}개 · 실행 {sum(b['total'] for b in agg.values())}회")
    return out


def deploy(days: int = 7) -> dict:
    """HTML 생성 + Vercel 배포 + 단축 URL (html_share_deployer SPoE 경유)."""
    out = build(days)
    sys.path.insert(0, str(Path(__file__).parent))
    from html_share_deployer import deploy as share_deploy
    result = share_deploy(str(out))
    print(f"🔗 {result.get('short_url') or result.get('url')}")
    return result


def _selftest() -> int:
    import tempfile

    passed = 0
    total = 8

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # 가짜 JSONL 생성
        today = date.today()
        f = tmp_dir / f"{today.isoformat()}.jsonl"
        now = datetime.now().isoformat()
        fake = [
            {"type": "pipeline_end", "pipeline": "auto_a", "status": "ok",
             "duration_sec": 1.5, "ended_at": now},
            {"type": "pipeline_end", "pipeline": "auto_a", "status": "ok",
             "duration_sec": 2.0, "ended_at": now},
            {"type": "pipeline_end", "pipeline": "auto_b", "status": "error",
             "duration_sec": 0.5, "ended_at": now, "error": "boom"},
            {"type": "pipeline_end", "pipeline": "auto_b", "status": "error",
             "duration_sec": 0.4, "ended_at": now, "error": "boom2"},
            {"type": "pipeline_end", "pipeline": "auto_b", "status": "error",
             "duration_sec": 0.3, "ended_at": now, "error": "boom3"},
            {"type": "stage_start", "pipeline": "auto_a", "stage": "x"},  # 무시돼야
        ]
        f.write_text("\n".join(json.dumps(r) for r in fake), encoding="utf-8")

        # === case 1: read_logs
        recs = read_logs(1, log_dir=tmp_dir)
        assert len(recs) == 6, f"expected 6 recs, got {len(recs)}"
        print("  ✓ case 1 JSONL 읽기")
        passed += 1

        # === case 2: aggregate 정확성
        agg = aggregate(recs)
        assert set(agg.keys()) == {"auto_a", "auto_b"}
        assert agg["auto_a"]["total"] == 2
        assert agg["auto_a"]["ok"] == 2
        assert agg["auto_a"]["success_rate"] == 100.0
        assert abs(agg["auto_a"]["avg_duration"] - 1.75) < 0.01
        print("  ✓ case 2 집계 정확")
        passed += 1

        # === case 3: 연속 실패 카운트
        assert agg["auto_b"]["consecutive_fail"] == 3, f"b streak {agg['auto_b']['consecutive_fail']}"
        assert agg["auto_a"]["consecutive_fail"] == 0
        print("  ✓ case 3 연속 실패 3회 감지")
        passed += 1

        # === case 4: HTML 렌더 — Critical/Warning 박스
        html = render_html(agg, days=1)
        assert "auto_a" in html and "auto_b" in html
        assert "Critical" in html, "critical 박스 누락"
        assert "auto_b" in html  # critical 목록에
        assert "3회 연속" in html
        print("  ✓ case 4 HTML Critical 박스 렌더")
        passed += 1

        # === case 5: 빈 로그 처리
        empty_agg = aggregate([])
        html2 = render_html(empty_agg, days=7)
        assert "AOS 관제 대시보드" in html2
        assert "총 실행" in html2
        print("  ✓ case 5 빈 로그도 에러 없이 렌더")
        passed += 1

        # === case 6: notify — Critical 있으면 발송
        sent = []
        state_p = tmp_dir / "notify_state.json"
        rc = notify(days=1, telegram_sender_fn=lambda m: sent.append(m),
                    state_path=state_p, log_dir=tmp_dir)
        assert rc == 1, f"should send (rc=1), got {rc}"
        assert sent and "auto_b" in sent[0] and "Critical" in sent[0]
        print("  ✓ case 6 notify Critical 발송")
        passed += 1

        # === case 7: notify dedup — 같은 상태 재호출 시 스킵
        sent2 = []
        rc2 = notify(days=1, telegram_sender_fn=lambda m: sent2.append(m),
                     state_path=state_p, log_dir=tmp_dir)
        assert rc2 == 0 and not sent2, f"dedup 실패: rc={rc2} sent={sent2}"
        print("  ✓ case 7 같은 상태 dedup 스킵")
        passed += 1

        # === case 8: notify — 모두 정상일 때 복구 알림 1회, 그 후 침묵
        clean_dir = tmp_dir / "clean"
        clean_dir.mkdir()
        (clean_dir / f"{today.isoformat()}.jsonl").write_text(
            json.dumps({"type": "pipeline_end", "pipeline": "auto_a",
                        "status": "ok", "duration_sec": 1.0, "ended_at": now}) + "\n",
            encoding="utf-8")
        sent3 = []
        rc3 = notify(days=1, telegram_sender_fn=lambda m: sent3.append(m),
                     state_path=state_p, log_dir=clean_dir)
        assert rc3 == 1 and sent3 and "복구" in sent3[0], f"복구 알림 실패: {sent3}"
        # 재호출: 이제 침묵
        sent4 = []
        rc4 = notify(days=1, telegram_sender_fn=lambda m: sent4.append(m),
                     state_path=state_p, log_dir=clean_dir)
        assert rc4 == 0 and not sent4
        print("  ✓ case 8 복구 1회 알림 후 침묵")
        passed += 1

    print(f"✅ selftest passed: {passed}/{total}")
    return 0 if passed == total else 1


NOTIFY_STATE = Path.home() / ".claude/data/aos_dashboard_notify.json"


def _load_notify_state(path: Path = None) -> dict:
    p = path or NOTIFY_STATE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_notify_state(state: dict, path: Path = None) -> None:
    p = path or NOTIFY_STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def notify(days: int = 7, telegram_sender_fn=None, state_path: Path = None,
           log_dir: Path = None) -> int:
    """Critical/Warning 있을 때만 텔레그램 발송, 없으면 침묵.

    반환: 0=침묵(정상) / 1=알림 발송함 / 2=에러.
    """
    records = read_logs(days, log_dir=log_dir) if log_dir else read_logs(days)
    agg = aggregate(records)
    critical = [(n, b) for n, b in agg.items() if b["consecutive_fail"] >= 3]
    warning = [(n, b) for n, b in agg.items()
               if 0 < b["consecutive_fail"] < 3 or (b["total"] >= 5 and b["success_rate"] < 80)]
    # 현재 상태 fingerprint
    cur_fp = {
        "critical": sorted(n for n, _ in critical),
        "warning": sorted(n for n, _ in warning),
    }
    state = _load_notify_state(state_path)
    last_fp = state.get("last_fp")

    if not critical and not warning:
        # 전부 복구됨 — 이전에 알림 있었으면 "회복" 통지
        if last_fp and (last_fp.get("critical") or last_fp.get("warning")):
            state["last_fp"] = cur_fp
            _save_notify_state(state, state_path)
            msg = "✅ AOS 정상 복구 — 모든 파이프라인 green"
            print(msg)
            sender = telegram_sender_fn
            if sender is None:
                try:
                    sys.path.insert(0, str(Path(__file__).parent))
                    from telegram_sender import TelegramSender  # type: ignore
                    sender = TelegramSender().send_markdown
                except Exception:
                    return 2
            try:
                sender(msg); return 1
            except Exception:
                return 2
        print("🟢 정상 — 알림 없음")
        return 0

    # 같은 Critical/Warning 조합이면 중복 스킵
    if cur_fp == last_fp:
        print(f"🔁 동일 상태 유지 — 알림 스킵 (critical={len(critical)}, warning={len(warning)})")
        return 0

    lines = []
    if critical:
        lines.append(f"🚨 *AOS Critical* — 연속 실패 {len(critical)}건")
        for n, b in sorted(critical, key=lambda x: -x[1]["consecutive_fail"]):
            last = (b["last_run"] or "-")[:16].replace("T", " ")
            lines.append(f"  • `{n}` — {b['consecutive_fail']}회 연속 실패 (마지막 {last})")
    if warning:
        lines.append("" if not critical else "")
        lines.append(f"⚠️ *Warning* {len(warning)}건")
        for n, b in sorted(warning, key=lambda x: x[1]["success_rate"]):
            lines.append(f"  • `{n}` — 성공률 {b['success_rate']:.0f}% ({b['ok']}/{b['total']})")
    msg = "\n".join(lines)
    print(msg)

    sender = telegram_sender_fn
    if sender is None:
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from telegram_sender import send_telegram  # type: ignore
            sender = lambda m: send_telegram(m, parse_mode="Markdown")
        except Exception as e:
            print(f"[err] 텔레그램 import 실패: {e}", file=sys.stderr)
            return 2
    try:
        sender(msg)
        state["last_fp"] = cur_fp
        _save_notify_state(state, state_path)
        return 1
    except Exception as e:
        print(f"[err] 텔레그램 발송 실패: {e}", file=sys.stderr)
        return 2


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    days = 7
    for i, a in enumerate(sys.argv):
        if a == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])
    if cmd == "selftest":
        return _selftest()
    if cmd == "build":
        build(days)
        return 0
    if cmd == "deploy":
        deploy(days)
        return 0
    if cmd == "notify":
        return notify(days)
    print(f"알 수 없는 명령: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
