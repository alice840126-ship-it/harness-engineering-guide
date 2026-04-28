#!/usr/bin/env python3
"""러닝 종합 코칭 에이전트.

Daily: rule-based (AI 호출 없음, 즉시 반환)
Weekly/Monthly: Claude CLI 호출 (형님 말투 + 3-5 액션 아이템)

모든 빌더는 {"title": str, "html": str, "signal": "ok"|"warn"|"tip", "triggered_rules": [str], "source": "rule"|"ai"} 반환.
대시보드에서 hero-grid 바로 아래 삽입 목적.
"""
from __future__ import annotations
import sys, json, os, subprocess, shutil
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Any

sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")

from advice_log import save_advice, get_last_advice, check_compliance
from health_metrics_pull import recovery_snapshot, consecutive_rest_days, vo2max_trend_summary

DATA_FILE = Path.home() / ".claude/data/running_log.jsonl"
LOAD_FILE = Path.home() / ".claude/data/training_load.jsonl"

# ───────── 레이스 목표 ─────────
HALF_MARATHON_DATE = date(2026, 6, 7)    # 하프마라톤 D-day

# ───────── 필터 임계값 ─────────
THRESHOLDS = {
    "cadence_low": 175,       # spm 미만 → 보폭 과다 / 회전수 부족
    "cadence_ok_low": 175,
    "cadence_ok_high": 190,
    "cadence_high": 195,      # 초과 → 과회전
    "vo_high": 80.0,          # mm 상하진폭 — 과하면 수직낭비
    "vr_high": 9.5,           # % — 수직진폭/보폭 비율
    "stance_high": 280.0,     # ms — 접지 시간 길면 느린 반응
    "acwr_warn": 1.3,
    "acwr_danger": 1.5,
    "tsb_fatigue": -20.0,
    "tsb_fresh": 5.0,
    "z12_min_ratio": 70.0,    # Z1+Z2 최소 비중 (폴라리즈드)
    "z45_max_ratio": 20.0,    # Z4+Z5 누적이 20% 넘으면 과부하
}


# ───────── 데이터 로더 ─────────

def _load_runs() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    rows = []
    for line in DATA_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            s = json.loads(line)
            if s.get("workout_type") != "러닝":
                continue
            s["_date"] = datetime.strptime(s["date"], "%Y-%m-%d").date()
            rows.append(s)
        except Exception:
            continue
    rows.sort(key=lambda r: r["_date"])
    return rows


def _load_load() -> list[dict]:
    if not LOAD_FILE.exists():
        return []
    rows = []
    for line in LOAD_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    rows.sort(key=lambda r: r["date"])
    return rows


def _load_for(d: date, load: list[dict]) -> dict | None:
    tgt = d.strftime("%Y-%m-%d")
    best = None
    for r in load:
        if r["date"] <= tgt:
            best = r
        else:
            break
    return best


# ───────── HTML 헬퍼 ─────────

def _signal_color(signal: str) -> tuple[str, str]:
    return {
        "ok":   ("✅", "#34c759"),
        "warn": ("⚠️", "#ff3b30"),
        "tip":  ("💡", "#ff9500"),
    }[signal]


def _build_summary_card(title: str, signal: str, bullets: list[str], footer: str = "") -> str:
    """hero-grid 바로 아래 꽂을 "종합 코칭 요약" 카드 HTML."""
    icon, color = _signal_color(signal)
    items = "".join(
        f'<li style="margin:6px 0;line-height:1.55;color:#1d1d1f;">{b}</li>'
        for b in bullets
    )
    footer_html = (
        f'<div style="margin-top:10px;padding-top:10px;border-top:1px solid #e5e5ea;'
        f'font-size:11px;color:#6e6e73;">{footer}</div>'
        if footer else ""
    )
    return (
        f'<div class="card coach-summary" style="border-left:4px solid {color};'
        f'background:linear-gradient(135deg,#fbfbfd 0%,#f5f5f7 100%);">'
        f'<div class="card-title" style="color:{color};font-size:15px;">'
        f'<span style="margin-right:6px;">{icon}</span>{title}</div>'
        f'<ul style="margin:12px 0 0 0;padding-left:20px;font-size:13px;">'
        f'{items}</ul>'
        f'{footer_html}'
        f'</div>'
    )


# ───────── 룰 평가 코어 ─────────

def _evaluate_rules(sessions: list[dict], load_rec: dict | None) -> tuple[list[tuple[str, str]], list[str]]:
    """세션들과 로드 레코드로 (signal, bullet) 튜플 리스트 + 트리거된 룰 이름 반환.

    signal: ok | warn | tip
    """
    bullets: list[tuple[str, str]] = []
    triggered: list[str] = []

    # ── 케이던스 ──
    cads = [s.get("cadence") for s in sessions if s.get("cadence")]
    if cads:
        avg_cad = sum(cads) / len(cads)
        if avg_cad < THRESHOLDS["cadence_low"]:
            triggered.append("cadence_low")
            bullets.append((
                "warn",
                f"형님 발걸음이 좀 느려요 — <b>{avg_cad:.0f}spm</b>. "
                f"보폭이 너무 큰 거 같아요. <b>178 BPM 메트로놈</b> 켜고 박자 맞춰봐요."
            ))
        elif avg_cad > THRESHOLDS["cadence_high"]:
            triggered.append("cadence_high")
            bullets.append((
                "tip",
                f"형님 발이 좀 퍼덕거려요 — <b>{avg_cad:.0f}spm</b>. "
                f"보폭 살짝 키우면 훨씬 편해요."
            ))
        else:
            bullets.append((
                "ok",
                f"케이던스 <b>{avg_cad:.0f}spm</b> — 딱 좋아요 형님. 이 리듬 그대로."
            ))

    # ── 수직진폭 / 수직비율 ──
    vos = [(s.get("form_summary") or {}).get("vertical_oscillation") for s in sessions]
    vos = [v for v in vos if v]
    vrs = [(s.get("form_summary") or {}).get("vertical_ratio") for s in sessions]
    vrs = [v for v in vrs if v]
    if vos:
        avg_vo = sum(vos) / len(vos)
        if avg_vo > THRESHOLDS["vo_high"]:
            triggered.append("vo_high")
            bullets.append((
                "warn",
                f"형님 위아래로 너무 튀어요 — <b>수직진폭 {avg_vo:.1f}mm</b>. "
                f"에너지 낭비에요. 코어 꽉 잡고 <b>무릎 아래로 착지</b>하는 느낌으로."
            ))
    if vrs:
        avg_vr = sum(vrs) / len(vrs)
        if avg_vr > THRESHOLDS["vr_high"]:
            triggered.append("vr_high")
            bullets.append((
                "warn",
                f"형님 보폭이 좀 커요 — <b>수직비율 {avg_vr:.1f}%</b>. "
                f"회전수만 조금 올려도 자동으로 잡혀요."
            ))

    # ── 접지 시간 ──
    sts = [(s.get("form_summary") or {}).get("stance_time") for s in sessions]
    sts = [v for v in sts if v]
    if sts:
        avg_st = sum(sts) / len(sts)
        if avg_st > THRESHOLDS["stance_high"]:
            triggered.append("stance_high")
            bullets.append((
                "tip",
                f"형님 발이 바닥에 오래 붙어있어요 — <b>접지 {avg_st:.0f}ms</b>. "
                f"뛰기 전에 <b>A-skip 드릴 2분</b>만 해줘도 확 달라져요."
            ))

    # ── ACWR / TSB (부하 상태) ──
    if load_rec:
        acwr = load_rec.get("acwr", 0) or 0
        tsb = load_rec.get("tsb", 0) or 0
        ctl = load_rec.get("ctl", 0) or 0
        if acwr >= THRESHOLDS["acwr_danger"]:
            triggered.append("acwr_danger")
            bullets.append((
                "warn",
                f"형님 지금 <b>부상 위험 커요</b> — ACWR {acwr:.2f}. "
                f"다음 주는 무리하지 말고 <b>Z2 회복조깅 30분</b>만 가요."
            ))
        elif acwr >= THRESHOLDS["acwr_warn"]:
            triggered.append("acwr_warn")
            bullets.append((
                "warn",
                f"형님 부하가 슬슬 오르는 중이에요 — ACWR {acwr:.2f}. "
                f"이번 주는 <b>현상 유지만</b> 하는 게 안전해요."
            ))
        if tsb <= THRESHOLDS["tsb_fatigue"]:
            triggered.append("tsb_fatigue")
            bullets.append((
                "warn",
                f"형님 몸이 많이 쌓였어요 — TSB {tsb:+.0f}. "
                f"하루이틀은 <b>30분 이하 Z2만</b> 가볍게 풀어주세요."
            ))
        elif tsb >= THRESHOLDS["tsb_fresh"]:
            bullets.append((
                "ok",
                f"형님 컨디션 좋아요 — TSB {tsb:+.0f} · CTL {ctl:.0f}. "
                f"<b>템포런이나 장거리</b> 노려볼 타이밍이에요."
            ))

    # ── Z1+Z2 비율 (폴라리즈드 80/20) ──
    z_totals = {"Z0":0,"Z1":0,"Z2":0,"Z3":0,"Z4":0,"Z5":0}
    for s in sessions:
        z = s.get("hr_zones") or {}
        for k in z_totals:
            z_totals[k] += z.get(k, 0) or 0
    total_hr = sum(z_totals.values())
    if total_hr > 0:
        low_pct = (z_totals["Z1"] + z_totals["Z2"]) / total_hr * 100
        high_pct = (z_totals["Z4"] + z_totals["Z5"]) / total_hr * 100
        if low_pct < THRESHOLDS["z12_min_ratio"]:
            triggered.append("z12_low")
            bullets.append((
                "tip",
                f"형님 편한 페이스가 좀 부족해요 — Z1+Z2 <b>{low_pct:.0f}%</b>. "
                f"주 1회는 <b>대화 가능한 속도</b>로만 뛰어봐요."
            ))
        if high_pct > THRESHOLDS["z45_max_ratio"]:
            triggered.append("z45_high")
            bullets.append((
                "warn",
                f"형님 고강도를 너무 많이 섞었어요 — Z4+Z5 <b>{high_pct:.0f}%</b>. "
                f"이대로 가면 <b>레이스 전에 몸 터져요</b>."
            ))

    return bullets, triggered


def _aggregate_signal(bullets: list[tuple[str, str]]) -> str:
    """전체 bullet의 최악 신호 반환."""
    if any(b[0] == "warn" for b in bullets):
        return "warn"
    if any(b[0] == "tip" for b in bullets):
        return "tip"
    return "ok"


# ───────── Daily 코치 (rule-based) ─────────

def _praise_bullet(triggered: list[str], load_rec: dict | None,
                   total_km: float, sessions: list[dict]) -> str | None:
    """오늘·이번주 잘했으면 칭찬 한마디. 조건 안 맞으면 None."""
    if triggered:
        return None
    if not load_rec:
        return None
    acwr = load_rec.get("acwr") or 0
    tsb = load_rec.get("tsb") or 0
    if not (0.8 <= acwr <= 1.3 and -10 <= tsb <= 5):
        return None
    # Z1+Z2 비중도 같이 본다 (폴라리즈드)
    z_totals = {"Z1":0,"Z2":0,"Z4":0,"Z5":0}
    for s in sessions:
        z = s.get("hr_zones") or {}
        for k in z_totals:
            z_totals[k] += z.get(k, 0) or 0
    total_z = sum(z_totals.values())
    if total_z == 0:
        return f"👍 형님 오늘 완벽해요 — 부하도 딱이고 컨디션도 좋아요. 이대로만 가요."
    low_pct = (z_totals["Z1"] + z_totals["Z2"]) / total_z * 100
    if low_pct >= 70:
        return (f"🏆 형님 오늘 진짜 교과서대로 뛰었어요 — Z2 {low_pct:.0f}% · "
                f"ACWR {acwr:.2f} · TSB {tsb:+.0f}. 훈련 장인 다 됐네요.")
    return (f"👍 형님 부하 밸런스 좋아요 — ACWR {acwr:.2f} · TSB {tsb:+.0f}. "
            f"다음엔 Z2 비중만 조금 더 올려보면 완벽해요.")


def _compliance_bullet(target_date: date, triggered: list[str],
                       signal: str, period: str) -> str | None:
    """지난번 조언과 비교한 한 줄. 비교할 게 없으면 None."""
    last = get_last_advice(period, before=target_date)
    if not last:
        return None
    res = check_compliance(last, triggered, signal)
    if res["status"] == "violated":
        return f"🗣️ {res['note']} 왜 안지켜요 형님…"
    if res["status"] == "complied":
        return f"🎯 {res['note']}"
    if res["status"] == "partial":
        return f"⚖️ {res['note']} 조금만 더 가봐요."
    return None


def daily_coach(target_date: date) -> dict:
    """Daily 코치 — AI 경유 (폴백: rule). Hero 블록의 종합평 자리.
    2026-04-25: 휴식일이면 rest_day_coach로 자동 분기."""
    runs = _load_runs()
    today_sessions = [s for s in runs if s["_date"] == target_date]
    load = _load_load()
    load_rec = _load_for(target_date, load)

    if not today_sessions:
        return rest_day_coach(target_date, load_rec)

    return _ai_coach("오늘", target_date, today_sessions, load_rec)


def _build_rest_day_ai_prompt(snap: dict, vo: dict | None, prior_advice: dict | None,
                              load_rec: dict | None, target_date: date, rest_streak: int) -> str:
    """휴식일 전용 AI 프롬프트 — 유머러스, 따뜻한 톤, 어제 비교 강조."""
    half_d = (HALF_MARATHON_DATE - target_date).days
    phase = _race_phase(half_d)

    # 메트릭 한 줄씩
    metric_lines = []
    for fname, label, unit in [("hrv", "HRV", ""), ("resting_hr", "안정심박", "bpm"),
                                ("steps", "걸음", ""), ("exercise_min", "운동시간", "분"),
                                ("stand_hours", "스탠드", "시간")]:
        m = snap["metrics"].get(fname)
        if not m:
            continue
        sign = "+" if m["diff"] > 0 else ""
        metric_lines.append(f"  - {label}: 오늘 {m['today']}{unit} (30일 평균 {m['baseline_avg']}{unit}, {sign}{m['pct']:.0f}%) [{'좋아짐' if m['is_better'] else '평소보다 낮음'}]")

    # 휴식일 vs 운동일 패턴
    rva_lines = []
    rva = snap["rest_vs_active_30d"]
    for fname, label in [("hrv", "HRV"), ("resting_hr", "안정심박")]:
        v = rva.get(fname)
        if v and v["better_when_resting"]:
            rva_lines.append(f"  - {label}: 휴식일 평균 {v['rest_avg']} vs 운동일 평균 {v['active_avg']} (휴식일이 더 좋음)")

    vo_block = ""
    if vo and vo.get("avg_30d") is not None:
        trend = vo.get("trend_30d", 0) or 0
        direction = "상승 중 (체력 늘고 있음)" if trend > 0.1 else "하락 중" if trend < -0.1 else "유지"
        vo_block = f"\n## VO2max 체력 트렌드\n- 최근 측정: {vo.get('latest','?')} ({vo.get('latest_date','?')})\n- 평균: 7일 {vo.get('avg_7d','?')} / 30일 {vo.get('avg_30d','?')} / 90일 {vo.get('avg_90d','?')}\n- 30일 추세: {trend:+.2f} → {direction}\n"

    prior_block = ""
    if prior_advice:
        followed = prior_advice.get("signal") == "warn" and rest_streak >= 1
        prior_block = (
            f"\n## 지난번 ({prior_advice['date']}) 조언\n"
            f"- signal: {prior_advice['signal']}\n"
            f"- 요약: {prior_advice.get('summary','')[:200]}\n"
            f"- **형님이 따랐나? {'YES — 어제 쉬라고 했고 오늘 진짜 안 뜀 (칭찬 강조)' if followed else 'N/A'}**\n"
        )

    load_block = ""
    if load_rec:
        load_block = (
            f"\n## 부하 상태\n"
            f"- ACWR: {load_rec.get('acwr', 0):.2f} (위험선 1.5)\n"
            f"- TSB: {load_rec.get('tsb', 0):+.0f} (피로선 -30)\n"
            f"- CTL/ATL: {load_rec.get('ctl', 0):.0f} / {load_rec.get('atl', 0):.0f}\n"
        )

    return f"""너는 형님(류웅수)의 러닝 코치야. 오늘은 형님이 안 뛰신 휴식일.
회복 데이터를 보고 **유머러스하고 따뜻한 톤**으로 코칭 멘트를 만들어줘.
형님이 매일 10시에 보는 건강 대시보드의 "오늘의 회복 코칭" 카드에 들어갈 내용이야.

## 레이스 카운트다운
- 하프마라톤: {HALF_MARATHON_DATE} · D-{half_d}일 · 단계: {phase}

## 오늘 회복 지표 (today vs 30일 baseline)
{chr(10).join(metric_lines) if metric_lines else "- 데이터 없음"}

## 30일 휴식 효과 패턴
{chr(10).join(rva_lines) if rva_lines else "- 패턴 데이터 부족"}
{vo_block}{prior_block}{load_block}
## 휴식 누적
- 연속 휴식 {rest_streak}일

## 작성 규칙 (반드시 지켜)
1. 톤: 따뜻한 형님 호칭 + 유머. "잘 쉬셨네요" 같은 칭찬 + 가끔 농담
2. 4~6개 bullet (• 마크 사용)
3. 첫 bullet은 **상황 한 줄 요약** (휴식 N일차, 어제 조언 따랐다면 강조)
4. 중간 bullets는 **회복 지표 해석 + VO2max 트렌드 + 휴식 효과 패턴**
5. 마지막 bullet은 **내일 액션 한 줄** (Z2 30분, 휴식 유지 등)
6. 이모지 사용 (💤 🟢 🟡 📈 💪 🎯 등)
7. **숫자 인용은 정확히** (예: "HRV 36 (+38%)", "ACWR 2.62")
8. 어제 조언이 'warn'이고 형님이 휴식했으면 → 첫 bullet에 칭찬 강조 ("어제 빨간불 보고 진짜 안 뜨신 거, 이게 진짜 러너 마인드 👏")

예시 톤:
- "💤 휴식 1일차 — 다리도 쉬는 소리 들리고 있어요"
- "🟢 HRV 36 (+38%) — 몸이 '드디어 쉬어준다'고 환호하는 중"
- "📈 VO2max 30일 평균이 90일 평균보다 +1.5 위 — 형님 체력은 진짜 늘고 있어요"
- "🎯 내일도 무리 금지. 무릎 상태 보고 Z2 30분이면 충분"

프리앰블·끝맺음 인사말 없이 bullet만 출력해."""


def rest_day_coach(target_date: date, load_rec: dict | None = None) -> dict:
    """휴식일 전용 코치 — AI 호출 (유머러스 톤) + rule-based fallback.

    데이터 소스:
    - health_metrics_pull.recovery_snapshot: HRV/안정심박/걸음 today vs 30일 baseline
    - rest_vs_active_30d: 30일 동안 휴식일 평균 vs 운동일 평균
    - vo2max_trend_summary: 누적 체력 트렌드
    - advice_log: 어제 조언 + 형님이 따랐는지 체크
    - training_load: ACWR/TSB 회복 추세
    """
    snap = recovery_snapshot(target_date)
    bullets: list[str] = []
    signal = "ok"  # 기본은 "잘 쉬고 계시네요"

    # ── 1. 휴식 일수 + 어제 조언 비교 ─────────────────────────
    rest_streak = snap["consecutive_rest_days"]
    last_advice = get_last_advice("daily", before=target_date)
    yesterday_was_warn = last_advice and last_advice.get("signal") == "warn"

    if yesterday_was_warn and rest_streak >= 1:
        # 어제 경고 있었고 진짜 안 뜀 → 칭찬
        bullets.append(
            f"🎯 형님 어제 {last_advice['date']} 조언({last_advice.get('summary','')[:50]}) 잘 들으셨네요. "
            f"오늘 안 뛰신 거 정확한 판단이에요."
        )
    elif rest_streak == 1:
        bullets.append(f"💤 오늘 휴식 1일차 — 회복 모드 진입.")
    elif rest_streak == 2:
        bullets.append(f"💤 휴식 2일 연속 — 몸 풀어지는 중. 내일은 컨디션 보고 가볍게 갈만해요.")
    elif rest_streak >= 3:
        bullets.append(f"⚠️ 휴식 {rest_streak}일 연속 — 슬슬 다시 움직일 타이밍이에요. 내일 Z2 30분이라도 가요.")
        signal = "tip"

    # ── 2. 오늘 메트릭 vs 30일 베이스라인 (회복 + 활동) ──
    # VO2max는 매일 측정 안 되므로 별도 트렌드 카드로 분리 (아래 step 2.5)
    metric_specs = [
        ("hrv", "HRV", ""),
        ("resting_hr", "안정심박", " bpm"),
        ("steps", "걸음", ""),
        ("exercise_min", "운동시간", "분"),
        ("stand_hours", "스탠드", "시간"),
    ]
    metric_lines = []
    for fname, label, unit in metric_specs:
        m = snap["metrics"].get(fname)
        if not m:
            continue
        arrow = "🟢" if m["is_better"] else "🟡"
        sign = "+" if m["diff"] > 0 else ""
        metric_lines.append(f"{arrow} {label} {m['today']}{unit} (30일 평균 {m['baseline_avg']}{unit} 대비 {sign}{m['diff']}{unit}, {sign}{m['pct']:.0f}%)")
    if metric_lines:
        bullets.append("📊 오늘 회복 지표:")
        for line in metric_lines:
            bullets.append(f"  {line}")

    # ── 2.5. VO2max 트렌드 (누적 체력 변화) ──
    vo = snap.get("vo2max_trend") or {}
    if vo.get("avg_30d") is not None:
        trend_line = f"💪 VO2max 체력 트렌드: 최근 측정 <b>{vo.get('latest', '?')}</b> ({vo.get('latest_date', '?')})"
        if vo.get("avg_7d") is not None:
            trend_line += f" · 7일 평균 {vo['avg_7d']}"
        trend_line += f" · 30일 평균 {vo['avg_30d']}"
        if vo.get("avg_90d") is not None:
            trend_line += f" · 90일 평균 {vo['avg_90d']}"
        # 방향성
        if vo.get("trend_30d") is not None:
            t = vo["trend_30d"]
            arrow = "📈 상승" if t > 0.1 else "📉 하락" if t < -0.1 else "➡️ 유지"
            trend_line += f" → {arrow} ({t:+.2f} / 30일)"
        trend_line += f" · 표본 {vo.get('sample_n_30d', 0)}일/30일"
        bullets.append(trend_line)

    # ── 3. 휴식일 vs 운동일 30일 패턴 ─────────────────────────
    rva = snap["rest_vs_active_30d"]
    pattern_lines = []
    if rva.get("hrv") and rva["hrv"]["better_when_resting"]:
        v = rva["hrv"]
        pattern_lines.append(
            f"HRV: 휴식일 평균 {v['rest_avg']} vs 운동일 평균 {v['active_avg']} (휴식일이 +{v['diff']:.1f} 높음 — 회복 효율 좋은 체질)"
        )
    if rva.get("resting_hr") and rva["resting_hr"]["better_when_resting"]:
        v = rva["resting_hr"]
        pattern_lines.append(
            f"안정심박: 휴식일 {v['rest_avg']} vs 운동일 {v['active_avg']} ({abs(v['diff']):.1f}bpm 낮음)"
        )
    if pattern_lines:
        bullets.append("📈 30일 휴식 효과 패턴:")
        for line in pattern_lines:
            bullets.append(f"  • {line}")

    # ── 4. 부하 추세 (ACWR이 떨어지고 있나) ─────────────────────
    if load_rec:
        acwr = load_rec.get("acwr", 0) or 0
        tsb = load_rec.get("tsb", 0) or 0
        if acwr >= 1.5:
            bullets.append(f"⚠️ ACWR {acwr:.2f} — 아직 위험 구간. 1.5 밑으로 내려올 때까지 휴식 유지가 정답.")
            signal = "warn"
        elif acwr >= 1.3:
            bullets.append(f"📉 ACWR {acwr:.2f} — 회복 진행 중. 1.3 밑으로 더 떨어지면 가볍게 시작 가능.")
        if tsb <= -30:
            bullets.append(f"💧 TSB {tsb:+.0f} — 피로 누적. 휴식이 정확한 선택.")

    # ── 5. 마무리 한 줄 ─────────────────────────────────────
    if signal == "warn":
        bullets.append("🎯 오늘은 무조건 휴식. 내일 다시 봐요.")
    elif rest_streak >= 3:
        bullets.append("🎯 푹 쉬셨으니 내일 가볍게 30분 Z2 추천. 무릎 상태 먼저 체크.")
    else:
        bullets.append("🎯 회복 잘 되고 있어요. 내일 컨디션 보고 결정하면 됨.")

    triggered = ["rest_day"]
    if signal == "warn":
        triggered.append("acwr_warn_during_rest")

    # ── 6. AI 코치 시도 (유머러스 톤) → 실패 시 위 rule bullets fallback ─────
    vo = snap.get("vo2max_trend") or {}
    ai_prompt = _build_rest_day_ai_prompt(snap, vo, last_advice, load_rec, target_date, rest_streak)
    ai_raw = _call_claude_coach(ai_prompt, timeout=180)

    if ai_raw:
        ai_bullets = _md_to_bullet_html(ai_raw)
        if ai_bullets:
            head = f"<b>💤 휴식 {rest_streak}일 · D-{(HALF_MARATHON_DATE - target_date).days}일 (하프)</b>"
            bullets = [head] + ai_bullets
            source = "ai_rest_day"
        else:
            source = "rule_rest_day"
    else:
        source = "rule_rest_day"

    html = _build_summary_card(
        "오늘의 회복 코칭",
        signal,
        bullets,
        footer=f"기준일: {target_date} · 휴식 {rest_streak}일 연속 · {source}"
    )

    # advice_log 저장 (다음번 비교 가능하게)
    try:
        save_advice(
            period="daily",
            signal=signal,
            triggered_rules=triggered,
            summary=" / ".join([b[:80] for b in bullets[:3]]),
            target_date=target_date,
        )
    except Exception as e:
        print(f"[rest_day_coach] advice_log save 실패 (비치명): {e}", file=sys.stderr)

    return {
        "title": "오늘의 회복 코칭",
        "html": html,
        "signal": signal,
        "triggered_rules": triggered,
        "source": source,
    }


# 후방호환 alias (dashboard_coach_injector 등 기존 호출부 유지용)
rule_based_daily_coach = daily_coach


# ───────── Weekly / Monthly — AI 코치 ─────────

CLAUDE_BIN = "/Users/oungsooryu/.npm-global/bin/claude"


def _build_ai_prompt(period: str, stats: dict, triggered: list[str],
                     rule_bullets: list[str], prior_advice: dict | None = None,
                     target_date: date | None = None) -> str:
    """AI 코칭 프롬프트. 재미·서사 중심. 룰 결과 + 지난번 조언 + D-day 맥락 주입."""
    stats_lines = "\n".join(f"- {k}: {v}" for k, v in stats.items())
    triggered_line = ", ".join(triggered) if triggered else "없음"
    rule_brief = "\n".join(f"- {b}" for b in rule_bullets) if rule_bullets else "- (룰 알림 없음)"

    # D-day 계산
    today = target_date or date.today()
    half_d = (HALF_MARATHON_DATE - today).days
    phase = _race_phase(half_d)
    dday_block = (
        f"\n## 레이스 카운트다운\n"
        f"- 하프마라톤: {HALF_MARATHON_DATE.strftime('%Y-%m-%d')} · **D-{half_d}일**\n"
        f"- 현재 훈련 단계: **{phase}**\n"
    )

    prior_block = ""
    if prior_advice:
        prior_block = (
            f"\n## 지난번 ({prior_advice['date']}) {prior_advice['period']} 조언\n"
            f"- signal: {prior_advice['signal']}\n"
            f"- 트리거: {', '.join(prior_advice.get('triggered_rules') or []) or '없음'}\n"
            f"- 요약: {prior_advice.get('summary', '')[:300]}\n"
        )

    # 일간은 매일 보는 거라 짧게 (3~4 bullets). 주간/월간은 풍성하게.
    if period == "오늘":
        return f"""너는 형님의 러닝 코치 친동생이야. 오늘 러닝 데이터 보고 **짧고 유머러스한** 코칭을 써.
매일 아침 대시보드 맨 위에서 형님이 이걸 읽어. 길면 피곤, 재미없으면 안 봐. 재미 + 핵심만.

## 데이터
{stats_lines}

## 자동 트리거된 룰
{triggered_line}

## 룰 기반 1차 분석 (참고만 — 이대로 쓰면 재미없음. 풀어서 써라)
{rule_brief}
{dday_block}{prior_block}
## 작성 규칙 (절대 준수)

### 0. 🚫 수치 부풀림·라벨 사기 금지 (최우선 — 위반 시 글 폐기)

**수치는 데이터에 적힌 그대로. 절대 올림·반올림·부풀리지 마.**

❌ 금지 예시:
- 데이터: +35% → "약 40% 더" / "거의 40%" / "40% 가까이" (모두 위반 — 35는 35다)
- 데이터: 32.3km → "약 35km" / "30km대 후반" (위반 — 32.3km로 정확히 써)
- 데이터: TRIMP 477 → "거의 500" (위반)
- 데이터: 5.32km → "5km 조금 넘게" (어쩔 수 없으면 "5.3km")

✅ 올바른 예시:
- +35% → "35% 더" / "37%면 37%로" (소수점 첫째자리까지 OK)
- 32.3km → "32.3km" 또는 "32km 정도"
- 5.32km → "5.3km"

**라벨도 데이터 그대로:**
- 데이터 라벨이 "최근 7일"이면 "이번 주(월~일)" 바꿔치기 금지. rolling 7일 ≠ ISO 주.
- 데이터 라벨이 "최근 30일"이면 "이번 달" 바꿔치기 금지. rolling 30일 ≠ 캘린더 월.
- "이번 주"·"이번 달"은 데이터에 명시적으로 그렇게 적힌 경우에만. 애매하면 "최근 7일"·"최근 한 달".

**자가 검증 체크 (출력 전 반드시):**
1. 모든 수치가 데이터에 있는 그 숫자인가? (35→40 같은 부풀림 0건?)
2. "이번 주"·"이번 달"이라고 쓴 곳이 정말 캘린더 기준 데이터인가?
3. "약·거의·가까이·넘게" 같은 부드러운 표현으로 숫자를 부풀리지 않았나?

### 1. 🚫 영문/수치 약어 금지 (가장 중요)
형님은 ACWR·TSB·TRIMP·CTL·ATL·VO₂max·Z1~Z5 같은 용어 **몰라**. 써도 "이게 뭔 소리야" 반응.
**반드시 일상어로 풀어 써.** 숫자는 은유/비유로 전환.

번역 치트시트:
- ACWR 높음 → "몸이 벅차다", "감당 속도보다 빨리 달림", "오버페이스", "배터리 경고등"
- TSB 마이너스 → "피로 쌓임", "기름 떨어져감", "졸린 몸"
- TRIMP 높음 → "최근 7일 빡셌다", "평소의 2배로 달림" (※ "이번 주"라고 쓰면 안 돼 — rolling 7일은 월~일이 아님)
- 무산소/Z4·Z5 → "숨차는 강도", "빡세게 달림"
- 유산소/Z2 → "대화되는 속도", "편한 조깅"
- 케이던스 → 그대로 OK (한국 러너도 씀) or "발 회전수"
- 페이스 7'15"/km → "1km 7분 15초"
- 부상 위험 → "삐끗 주의", "무릎 경고"

### 2. 구조 — <li> 3개 (데이터 좋으면 4개)

<li> **한줄 진단 — 유머 + 비유 필수**
   ❌ "오늘 5.3km · 7'15"/km — 수고했어요"  (재미없음, 정보 나열)
   ✅ "하프 <b>D-{half_d}</b>인데 오늘 <b>5km 조깅</b>, 완전 몸풀기 데이트 코스네요 🚶"
   ✅ "형님 오늘 페이스 <b>1km 7분</b>, 소금빵 먹으러 슬렁슬렁 나가는 속도예요 🥐"

<li> **몸 상태 + 내일 액션**
   ❌ "ACWR 2.29, TSB -45 — 내일 Z2 30분"
   ✅ "최근 7일 평소의 <b>2배</b>로 달려서 몸이 벅찬 상태에요. 내일은 <b>쉬거나 30분 편한 조깅</b> 정도가 딱."
   ✅ "배터리 빨간불이에요 형님 — 내일은 <b>완전 쉬고</b> 넷플릭스 각."

<li> **한 줄 마무리 — 농담/칭찬/경고 택1**
   - 칭찬: "발 회전수 <b>184</b> 오늘도 깔끔했어요 👏"
   - 농담: "러닝 끝났으니 오늘 아점은 든든하게 각이에요 🍳"
   - 경고 유머: "어제도 빨간불, 오늘도 빨간불 — 이대로 가면 하프는 보고만 뛰어요 😅"
   - 지난번 비교: "어제 경고 그대로라 오늘도 같은 말 해야 해요 🙄"

<li> (선택 4번째) 진짜 특별할 때만 — 평소엔 3개.

### 3. 톤
- "형님" 호칭 + 친근 경어체 ("~해요/~네요")
- **친동생 텐션** — 약간 까불고, 놀리고, 응원하고
- 음식·날씨·생활 비유 환영 (소금빵, 넷플릭스, 날씨, 배터리, 자동차 기름 등)
- 이모지 1~2개 OK (과하지 않게)
- 금지: 영문 약어, 숫자 나열, "다양한 측면에서", "종합적으로"

### 4. 형식
- <li>...</li> × 3개 (최대 4개). <ul> 넣지 마.
- <b>태그로 숫자·키워드만 강조.
- 각 bullet은 **1~2문장**. 절대 길게 쓰지 마.

지금 바로 <li>로 시작하는 HTML만 출력."""

    return f"""너는 형님의 러닝 코치 친동생이야. {period} 데이터를 보고 **재밌고 풍부한 종합 코칭**을 작성해.
형님이 대시보드 맨 위에서 이걸 읽는 거라 **첫 문장부터 눈길 확 끌어야** 해.

## 데이터
{stats_lines}

## 자동 트리거된 룰
{triggered_line}

## 룰 기반 1차 분석 (참고만 — 이걸 그대로 쓰지 말고 풀어서 써)
{rule_brief}
{dday_block}{prior_block}
## 작성 규칙 (절대 준수)

### 0. 🚫 수치 부풀림 금지 (최우선 — 위반 시 글 폐기)

**수치는 데이터에 적힌 그대로. 절대 올림·반올림·부풀리지 마.**

❌ 금지: +35% → "약 40%" / 32.3km → "약 35km" / 477 → "거의 500"
✅ 허용: +35% → "35% 더" / 32.3km → "32.3km" / 477 → "477"
✅ 허용: 소수점 첫째자리까지 (5.32km → "5.3km")

- 데이터의 라벨(예: "이번 주 총거리", "이번 달 TRIMP 합")을 그대로 사용. ISO 주(월~일) / 캘린더 월(1일~말일) 기준이야.
- 데이터에 없는 다른 윈도우(rolling 7일, 최근 30일 등)를 임의로 만들어 쓰지 마.
- "약·거의·가까이·넘게" 같은 부드러운 표현으로 숫자를 부풀리지 마.

**자가 검증 (출력 전 반드시):** 모든 수치가 데이터의 그 숫자인가? 부풀림 0건?

### 1. 🚫 영문 약어 절대 금지 — 일상어로만 (위반 시 글 폐기)

형님은 ACWR · TSB · TRIMP · CTL · ATL · VO₂max · Z1~Z5 같은 용어 **완전히 몰라**. 이 용어가 한 번이라도 카드에 등장하면 "이게 뭔 소리야" 반응. **풀어 쓰는 것도 금지** ("ACWR 2.62"는 절대 X, "ACWR이 뭐냐면..."도 X). 처음부터 일상어로만 써.

번역 치트시트:
- ACWR 높음 → "몸이 벅차다", "감당 속도보다 빨리 달림", "오버페이스", "배터리 경고등"
- TSB 마이너스 → "피로 쌓임", "기름 떨어져감", "졸린 몸"
- TRIMP 높음 → "이번 주 빡셌다", "평소의 2배로 달림"
- 무산소/Z4·Z5 → "숨차는 강도", "빡세게 달림"
- 유산소/Z2 → "대화되는 속도", "편한 조깅"
- 케이던스 → "발 회전수" (또는 "케이던스" 그대로 OK)
- 페이스 7'15"/km → "1km 7분 15초"
- 부상 위험 → "삐끗 주의", "무릎 경고"

### 2. 스토리텔링 — 숫자를 "의미"로 번역
숫자를 나열하지 마. 비유·은유로 풀어.
- ❌ "ACWR 2.62. 부상 고위험."
- ❌ "ACWR 2.62는 체력 쌓이는 속도보다 피로가 빠르다는 신호" (약어 등장)
- ✅ "형님 몸이 지금 빨간불 구간이에요 — 체력 쌓이는 속도보다 피로가 훨씬 빨리 쌓이고 있어요."
- ✅ "쉽게 말해 <b>배터리 12%</b>짜리 핸드폰으로 장거리 뛰는 중."

### 3. 필수 구조 (bullet **4개**, 짧고 굵게)

<li> **첫 bullet — 한 문장 은유 + D-day 긴장감** (숫자 1개만)

<li> **두번째 bullet — 현 상태 진단 + 원인 한 줄** (숫자 2개 정도, 비유로)

<li> **세번째 bullet — 💪 VO2max(유산소 체력) 트렌드 한 줄 (필수)**
   데이터에 "VO2max 체력 트렌드"가 있으면 반드시 한 줄로 언급 — 러너에게 가장 중요한 장기 지표.
   예: "💪 유산소 체력은 90일 평균보다 +1.5 올라옴 — 형님 폐가 진짜 부자 되는 중이에요 📈"
   예: "💪 심폐 능력은 90일 평균 대비 +1.5 — 보이지 않는 곳에서 체력이 쌓이는 중"
   ※ "VO2max"라는 용어는 OK (러너들 사이 통용 — 단 "유산소 체력"·"심폐 능력"으로 풀어줘도 좋음)

<li> **네번째 bullet — 다음 행동** (숫자 박은 구체 처방, 1줄)

<li> **(선택) 다섯번째 — 칭찬 or 농담 마무리**
   지난번 조언 비교 가능하면 추가 ("어제 경고 잘 지켰네요 👏" / "또 무시했네요 😅")

### 4. 톤
- "형님" 호칭 + 친근 경어체 + 친동생 텐션
- 비유 환영 (배터리·빨간불·소금빵·넷플릭스·자동차 기름)
- 이모지 1~2개 OK
- 금지: 영문 약어, "다양한 측면에서", "종합적으로", "~해야 합니다"

### 5. 형식
- **<li>...</li> × 3~4개만**. <ul> 넣지 마.
- <b>태그로 숫자·키워드만 강조.
- 각 bullet **1~2문장**. 길게 쓰지 마.

지금 바로 <li>로 시작하는 HTML만 출력."""


def _race_phase(days_to_race: int) -> str:
    """하프마라톤 D-day로 훈련 단계 판정."""
    if days_to_race < 0:
        return "레이스 종료 — 회복기"
    if days_to_race <= 10:
        return "테이퍼링 (거리·강도 감량, 컨디션 세팅)"
    if days_to_race <= 28:
        return "피크 빌드업 (장거리·템포 최대치)"
    if days_to_race <= 56:
        return "빌드업 (주간 거리 증량 + 강도 훈련 도입)"
    if days_to_race <= 84:
        return "베이스 빌드 (Z2 볼륨 위주, 기초 체력 축적)"
    return "오프시즌 (유지 훈련)"


def _build_trend_stats(target_date: date, runs: list[dict],
                       load: list[dict]) -> dict:
    """오늘 기준 최근 7일/30일 트렌드 + PR 요약. _ai_coach stats에 병합용."""
    recent7 = [s for s in runs if (target_date - s["_date"]).days in range(0, 7) and s["_date"] <= target_date]
    recent30 = [s for s in runs if (target_date - s["_date"]).days in range(0, 30) and s["_date"] <= target_date]

    km7 = sum(s.get("distance_km") or 0 for s in recent7)
    km30 = sum(s.get("distance_km") or 0 for s in recent30)
    sess7 = len(recent7)
    sess30 = len(recent30)

    # PR (최근 1년 내)
    year_ago = target_date - timedelta(days=365)
    year_runs = [s for s in runs if year_ago <= s["_date"] <= target_date]
    longest = max((s.get("distance_km") or 0 for s in year_runs), default=0)
    # 5km+ 최고 페이스
    fast_pace = None
    for s in year_runs:
        d = s.get("distance_km") or 0
        dur = s.get("duration_sec") or 0
        if d >= 5 and dur > 0:
            p = dur / d
            if fast_pace is None or p < fast_pace:
                fast_pace = p

    out = {
        "최근 7일 거리": f"{km7:.1f}km ({sess7}회)",
        "최근 30일 거리": f"{km30:.1f}km ({sess30}회, 평균 주간 {km30/30*7:.1f}km)",
    }
    if longest > 0:
        out["1년내 최장거리"] = f"{longest:.1f}km"
    if fast_pace:
        fm, fs = int(fast_pace // 60), int(fast_pace % 60)
        out["1년내 최고 페이스(5km+)"] = f"{fm}'{fs:02d}\"/km"

    # 7일 TRIMP 합 vs 30일 평균주 (부하 추세)
    t7 = sum(s.get("trimp") or 0 for s in recent7)
    t30 = sum(s.get("trimp") or 0 for s in recent30)
    if t30 > 0:
        avg_weekly_trimp = t30 / 30 * 7
        if avg_weekly_trimp > 0:
            # 라벨 정확성: rolling 7일(today-6 ~ today)이지 ISO week(월~일) 아님 — LLM 부풀림 방지
            out["최근 7일 TRIMP (rolling)"] = f"{t7:.0f} (30일 평균 주간 {avg_weekly_trimp:.0f} 대비 {(t7/avg_weekly_trimp-1)*100:+.0f}%)"

    # 2026-04-28 추가: VO2max + 회복 지표 (운동일 daily/weekly/monthly 종합 코칭에 자동 표시)
    try:
        vo = vo2max_trend_summary(today=target_date)
        if vo and vo.get("avg_30d") is not None:
            avg7 = vo.get("avg_7d")
            avg30 = vo["avg_30d"]
            avg90 = vo.get("avg_90d")
            trend_msg = ""
            if vo.get("trend_90d_vs_30d") is not None:
                t = vo["trend_90d_vs_30d"]
                arrow = "상승 중 (체력 늘고 있음)" if t > 0.1 else "하락 중" if t < -0.1 else "유지"
                trend_msg = f" / 30일 평균이 90일 평균 대비 {t:+.2f} → {arrow}"
            out["VO2max 체력 트렌드"] = f"최근 측정 {vo.get('latest','?')} ({vo.get('latest_date','?')}) · 7일 {avg7} · 30일 {avg30} · 90일 {avg90}{trend_msg}"

        from health_metrics_pull import recent_avg
        hrv7 = recent_avg("hrv", days=7, today=target_date)
        hrv30 = recent_avg("hrv", days=30, today=target_date)
        if hrv7 is not None and hrv30 is not None:
            diff = hrv7 - hrv30
            arrow = "회복 중" if diff > 0.5 else "피로 누적" if diff < -0.5 else "유지"
            out["심박변동성 (회복 지표)"] = f"최근 7일 평균 {hrv7:.1f} vs 30일 평균 {hrv30:.1f} ({diff:+.1f}, {arrow})"

        rhr7 = recent_avg("resting_hr", days=7, today=target_date)
        rhr30 = recent_avg("resting_hr", days=30, today=target_date)
        if rhr7 is not None and rhr30 is not None:
            diff = rhr7 - rhr30
            arrow = "회복 중" if diff < -0.5 else "피로 신호" if diff > 0.5 else "유지"
            out["안정시 맥박"] = f"최근 7일 평균 {rhr7:.1f}bpm vs 30일 평균 {rhr30:.1f}bpm ({diff:+.1f}, {arrow})"
    except Exception as _e:
        print(f"[trend_stats] vo2max/hrv 추가 실패 (비치명): {_e}", file=sys.stderr)

    return out


def _md_to_bullet_html(text: str) -> list[str]:
    """Claude 응답에서 <li>…</li> 추출 (폴백: 줄바꿈으로 나눔)."""
    import re
    lis = re.findall(r"<li[^>]*>(.*?)</li>", text, re.DOTALL)
    if lis:
        return [li.strip() for li in lis if li.strip()]
    # 폴백: - 로 시작하는 라인
    lines = [l.strip().lstrip("-•").strip() for l in text.splitlines() if l.strip().startswith(("-", "•"))]
    return lines[:5] if lines else [text.strip()[:400]]


def _call_claude_coach(prompt: str, timeout: int = 420) -> str | None:
    """Claude CLI 호출. 실패 시 None 반환."""
    if not Path(CLAUDE_BIN).exists() and not shutil.which("claude"):
        return None
    cmd = [CLAUDE_BIN if Path(CLAUDE_BIN).exists() else "claude",
           "-p", "--output-format", "text"]
    # 2026-04-27: launchd 환경 PATH 보강 — node 없어서 claude CLI exit 127 fix
    _env = {**os.environ}
    _env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:" + _env.get("PATH", "")
    try:
        r = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=timeout, env=_env
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        print(f"[coach] CLI exit {r.returncode}: {r.stderr[:200]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"[coach] CLI timeout after {timeout}s", file=sys.stderr)
    except Exception as e:
        print(f"[coach] CLI error: {e}", file=sys.stderr)
    return None


def _ai_coach(period: str, target_date: date, sessions: list[dict],
              load_rec: dict | None) -> dict:
    """Weekly/Monthly 공통 AI 코치. 실패 시 rule-based로 폴백."""
    bullets_tuple, triggered = _evaluate_rules(sessions, load_rec)
    rule_bullets = [b[1] for b in bullets_tuple]

    # 집계
    total_km = sum(s.get("distance_km") or 0 for s in sessions)
    total_sec = sum(s.get("duration_sec") or 0 for s in sessions)
    total_trimp = sum(s.get("trimp") or 0 for s in sessions)
    cads = [s.get("cadence") for s in sessions if s.get("cadence")]
    vos = [(s.get("form_summary") or {}).get("vertical_oscillation") for s in sessions]
    vos = [v for v in vos if v]
    avg_cad = sum(cads) / len(cads) if cads else 0
    avg_vo = sum(vos) / len(vos) if vos else 0
    pace = total_sec / total_km if total_km else 0
    pm, ps = int(pace // 60), int(pace % 60)

    stats = {
        f"{period} 총거리": f"{total_km:.1f}km",
        f"{period} 세션수": f"{len(sessions)}회",
        "평균 페이스": f"{pm}'{ps:02d}\"/km" if total_km else "-",
        f"{period} TRIMP 합": f"{total_trimp:.0f}",
        "평균 케이던스": f"{avg_cad:.0f}spm" if cads else "데이터없음",
        "평균 수직진폭": f"{avg_vo:.1f}mm" if vos else "데이터없음",
        "현재 CTL/ATL/TSB": (f"{load_rec.get('ctl',0):.0f} / {load_rec.get('atl',0):.0f} / {load_rec.get('tsb',0):+.0f}"
                            if load_rec else "데이터없음"),
        "현재 ACWR": f"{load_rec.get('acwr',0):.2f}" if load_rec else "데이터없음",
    }

    # 트렌드 지표 병합 — daily만. weekly/monthly는 ISO주/캘린더월 데이터만 보여서 윈도우 혼란 방지 (2026-04-28)
    if period == "오늘":
        try:
            all_runs = _load_runs()
            all_load = _load_load()
            stats.update(_build_trend_stats(target_date, all_runs, all_load))
        except Exception as e:
            print(f"[coach] trend stats skip: {e}", file=sys.stderr)

    # period → advice_log period 매핑
    if "오늘" in period:
        log_period = "daily"
    elif "주" in period:
        log_period = "weekly"
    else:
        log_period = "monthly"
    prior = get_last_advice(log_period, before=target_date)

    prompt = _build_ai_prompt(period, stats, triggered, rule_bullets,
                              prior_advice=prior, target_date=target_date)
    raw = _call_claude_coach(prompt)

    signal = _aggregate_signal(bullets_tuple) if bullets_tuple else "tip"

    if raw:
        bullets = _md_to_bullet_html(raw)
        head = f"<b>{period} {total_km:.1f}km · {len(sessions)}회 · {pm}'{ps:02d}\"/km</b> — 수고했어요 형님."
        bullets = [head] + bullets
        html = _build_summary_card(
            f"{period + '의' if period == '오늘' else period} 종합 코칭",
            signal,
            bullets,
            footer=f"AI 코치 · 트리거 {len(triggered)}개 · {target_date}"
        )
        source = "ai"
    else:
        # 폴백 — rule bullets + compliance + 칭찬
        head = (
            "tip",
            f"<b>{period} {total_km:.1f}km · {len(sessions)}회 · {pm}'{ps:02d}\"/km</b> — 수고했어요 형님."
        )
        combined = [head] + bullets_tuple
        # 비교구조 삽입
        comp = _compliance_bullet(target_date, triggered, signal, log_period)
        if comp:
            combined.insert(1, ("tip", comp))
        # 칭찬
        praise = _praise_bullet(triggered, load_rec, total_km, sessions)
        if praise:
            combined.append(("ok", praise))
            if signal == "tip":
                signal = "ok"
        html = _build_summary_card(
            f"{period + '의' if period == '오늘' else period} 종합 코칭",
            signal,
            [b[1] for b in combined],
            footer=f"룰 기반 폴백 · 트리거 {len(triggered)}개 · {target_date}"
        )
        source = "rule"

    # advice_log 저장
    try:
        plain = " / ".join(rule_bullets[:3]) if rule_bullets else f"{period} {total_km:.1f}km"
        save_advice(log_period, target_date, signal, triggered, plain)
    except Exception as e:
        print(f"[coach] advice_log save 실패 (비치명): {e}", file=sys.stderr)

    return {"title": f"{period + '의' if period == '오늘' else period} 종합 코칭", "html": html, "signal": signal,
            "triggered_rules": triggered, "source": source}


def _recovery_effect_card(window_days: int, today: date, period_label: str) -> str:
    """휴식일 회복 효과 카드 — 간소화 버전 (2026-04-28).

    형님 피드백 반영:
    - 디테일 줄이고 3~4줄로 압축
    - 어려운 약어(ACWR/HRV) 안 쓰기 ("심박변동성"으로 풀어쓰기)
    - 유머러스 마무리 강화
    - 윈도우: weekly=7일, monthly=30일 (이전: 30/90)
    """
    from health_metrics_pull import compare_rest_vs_active
    import random

    hrv = compare_rest_vs_active("hrv", window_days=window_days, today=today)
    rhr = compare_rest_vs_active("resting_hr", window_days=window_days, today=today)

    bullets: list[str] = []

    if not hrv and not rhr:
        bullets.append(f"⏳ {period_label} 데이터 표본이 적어요. 다음 회차에 다시 봐요.")
        signal = "tip"
    else:
        # 1줄: 운동/휴식 비율 + 회복 효과
        if hrv:
            active_n, rest_n = hrv["active_n"], hrv["rest_n"]
            total = active_n + rest_n
            ratio = (active_n / total * 100) if total else 0
            bullets.append(
                f"📊 {period_label}: 운동 <b>{active_n}일</b> · 휴식 <b>{rest_n}일</b> (운동 {ratio:.0f}%)"
            )

        # 2줄: 회복 신호 (HRV "심박변동성", 안정심박 "쉴 때 맥박" 풀어쓰기)
        if hrv and hrv["better_when_resting"]:
            bullets.append(
                f"💚 쉬는 날 <b>심박변동성 +{hrv['diff']:.1f}</b> 좋아짐 — 몸이 쉬자마자 회복 모드"
            )
        if rhr and rhr["better_when_resting"]:
            bullets.append(
                f"❤️ 쉬는 날 <b>맥박 -{abs(rhr['diff']):.1f}</b>bpm 떨어짐 — 심장이 한숨 돌리는 중"
            )

        # 3줄: 유머러스 마무리 (회복 효과에 따라 분기)
        good = (hrv and hrv["better_when_resting"]) or (rhr and rhr["better_when_resting"])
        if good:
            quips = [
                "💬 형님 몸은 솔직해요. 쉬면 좋아진다고 데이터가 자랑하는 중 🛋️",
                "💬 휴식 = 무료 회복 부스터. 안 쓰면 진짜 손해 🥃",
                "💬 다리도 한숨 자고 싶대요. 가끔은 좀 풀어줘요 😴",
                "💬 결론: 휴식은 게으름이 아니라 전략. 형님 데이터가 증명함 ✨",
            ]
        else:
            quips = [
                "💬 쉬어도 회복이 부진 — 잠? 술? 짚이는 거 있죠 🤔",
                "💬 휴식만으론 부족. 수면·식사도 한번 챙겨봐요 🍽️",
            ]
        bullets.append(random.choice(quips))
        signal = "ok"

    return _build_summary_card(
        f"휴식일 회복 효과 ({period_label})",
        signal,
        bullets,
        footer=f"분석 기간: 최근 {window_days}일 · health_metrics_pull.compare_rest_vs_active"
    )


def weekly_coach(target_date: date) -> dict:
    runs = _load_runs()
    load = _load_load()
    load_rec = _load_for(target_date, load)

    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    week_sessions = [s for s in runs if monday <= s["_date"] <= sunday]
    period = "이번 주"

    # 이번 주 기록 없으면 지난 주로 폴백
    if not week_sessions:
        last_monday = monday - timedelta(days=7)
        last_sunday = sunday - timedelta(days=7)
        week_sessions = [s for s in runs if last_monday <= s["_date"] <= last_sunday]
        if week_sessions:
            period = "지난 주"
            # 지난 주 load_rec이 더 대표성 있게 — 지난주 일요일 값 사용
            load_rec = _load_for(last_sunday, load) or load_rec

    if not week_sessions:
        html = _build_summary_card(
            "이번 주 종합 코칭", "tip",
            ["이번 주·지난 주 모두 러닝 기록 없음. 월·수·금 15분씩이라도 재시동 걸자."],
            footer=f"기준일: {target_date}"
        )
        # 회복 효과 카드는 운동 기록이 없어도 health_metrics만 있으면 가능
        html += "\n" + _recovery_effect_card(window_days=7, today=target_date, period_label="이번 주 7일")
        return {"title": "이번 주 종합 코칭", "html": html, "signal": "tip",
                "triggered_rules": [], "source": "rule"}
    result = _ai_coach(period, target_date, week_sessions, load_rec)
    # 보너스: 휴식일 회복 효과 카드 (30일 윈도우 — 주간 트렌드 보기 적합)
    result["html"] = result["html"] + "\n" + _recovery_effect_card(
        window_days=7, today=target_date, period_label="이번 주 7일"
    )
    return result


def monthly_coach(target_date: date) -> dict:
    runs = _load_runs()
    month_start = target_date.replace(day=1)
    month_sessions = [s for s in runs if month_start <= s["_date"] <= target_date]
    load = _load_load()
    load_rec = _load_for(target_date, load)
    if not month_sessions:
        html = _build_summary_card(
            "이번 달 종합 코칭", "tip",
            ["이번 달 러닝 기록 없음."],
            footer=f"기준일: {target_date}"
        )
        html += "\n" + _recovery_effect_card(window_days=30, today=target_date, period_label="최근 30일")
        return {"title": "이번 달 종합 코칭", "html": html, "signal": "tip",
                "triggered_rules": [], "source": "rule"}
    result = _ai_coach("이번 달", target_date, month_sessions, load_rec)
    # 보너스: 휴식일 회복 효과 카드 (90일 윈도우 — 월간은 장기 패턴 보기 적합)
    result["html"] = result["html"] + "\n" + _recovery_effect_card(
        window_days=30, today=target_date, period_label="최근 30일"
    )
    return result


# ───────── CLI ─────────

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    target = date.today()
    if len(sys.argv) > 2:
        target = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    if mode == "daily":
        r = rule_based_daily_coach(target)
    elif mode == "weekly":
        r = weekly_coach(target)
    elif mode == "monthly":
        r = monthly_coach(target)
    else:
        print(f"usage: {sys.argv[0]} [daily|weekly|monthly] [YYYY-MM-DD]", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({
        "title": r["title"],
        "signal": r["signal"],
        "triggered_rules": r["triggered_rules"],
        "source": r["source"],
        "html_len": len(r["html"]),
    }, ensure_ascii=False, indent=2))
