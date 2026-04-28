#!/usr/bin/env python3
"""HealthFit 대시보드 카드 HTML 생성기.

기존 22개 카드의 실데이터 주입 + 신규 17개 카드 HTML 블록 빌더.
healthfit_dashboard_gen.py 에서 import 하여 사용.

의존:
    - ~/.claude/data/running_log.jsonl (확장된 fit_parser 결과)
    - ~/.claude/data/training_load.jsonl (CTL/ATL/TSB/ACWR)
"""
from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from pathlib import Path

RUNNING_LOG = Path.home() / ".claude/data/running_log.jsonl"
LOAD_FILE = Path.home() / ".claude/data/training_load.jsonl"


# ───────── 로더 ─────────

def load_sessions() -> list[dict]:
    if not RUNNING_LOG.exists():
        return []
    rows = []
    for line in RUNNING_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            s = json.loads(line)
            s["_date"] = datetime.strptime(s["date"], "%Y-%m-%d").date()
            rows.append(s)
        except Exception:
            continue
    return rows


def load_load() -> list[dict]:
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


def get_load_for(d: date, load: list[dict] | None = None) -> dict | None:
    """해당 날짜 이전(포함) 가장 가까운 load 레코드."""
    if load is None:
        load = load_load()
    tgt = d.strftime("%Y-%m-%d")
    best = None
    for r in load:
        if r["date"] <= tgt:
            best = r
        else:
            break
    return best


# ───────── 유틸 ─────────

def fmt_mmss(sec: float | int) -> str:
    s = int(round(sec or 0))
    return f"{s // 60}:{s % 60:02d}"


def fmt_pace(sec_per_km: float | None) -> str:
    if not sec_per_km or sec_per_km <= 0:
        return "-"
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km - m * 60))
    if s == 60:
        m += 1; s = 0
    return f"{m}'{s:02d}\""


def coach_note(signal: str, text: str) -> str:
    cfg = {"ok": ("✅", "#34c759"), "warn": ("⚠️", "#ff3b30"), "tip": ("💡", "#ff9500")}
    icon, color = cfg[signal]
    return (f'<div class="coach-note" style="margin-top:12px;padding:10px 12px;'
            f'background:#f7f8fa;border-left:3px solid {color};border-radius:6px;'
            f'font-size:12px;line-height:1.55;color:#1d1d1f;font-weight:500;">'
            f'<span style="margin-right:6px;">{icon}</span>{text}</div>')


def card_open(title: str, desc: str, accent: str = "orange") -> str:
    return (f'<div class="card"><div class="card-title" style="color:var(--{accent})">{title}</div>'
            f'<div class="card-desc">{desc}</div>')


# ───────── 1. HR 존 카드 (기존 데일리 교체) ─────────

def render_hr_zones_card(session: dict, duration_sec: int) -> str:
    z = session.get("hr_zones") or {}
    total = max(z.get("total", duration_sec), 1)
    rows = []
    for i in [5, 4, 3, 2, 1]:
        key = f"Z{i}"
        sec = z.get(key, 0)
        pct = int(round(sec / total * 100))
        rows.append(
            f'<div class="zone-row"><div class="zone-name z{i}">Z{i}</div>'
            f'<div class="zone-bar-wrap"><div class="zone-bar z{i}" style="width:{pct}%"></div></div>'
            f'<div class="zone-val">{fmt_mmss(sec)} · {pct}%</div></div>'
        )
    hr_avg = session.get("heart_rate_avg")
    hr_max = session.get("heart_rate_max")
    hr_part = (f'<div class="kv" style="margin-top:10px; border-top:1px solid var(--line); padding-top:10px;">'
               f'<span class="k">평균 심박수</span><span class="v">{hr_avg or "-"} bpm '
               f'<span class="hint">(최대 {hr_max or "-"})</span></span></div>')
    # 90% 이상이 Z4-Z5면 경고
    z45 = z.get("Z4", 0) + z.get("Z5", 0)
    warn = ""
    if z45 / total > 0.7:
        warn = ('<div style="font-size:11px; color:var(--red); margin-top:8px; font-weight:600;">'
                f'⚠️ 전체 시간의 {int(round(z45/total*100))}%가 Z4-Z5 고강도. 회복 러닝 보강 필요.</div>')
    coach = _coach_heart(hr_avg)
    body = '<div class="zones">' + "".join(rows) + '</div>' + hr_part + warn + coach
    return body


def _coach_heart(hr: int | None) -> str:
    if not hr:
        return coach_note("tip", "형님 심박 데이터가 없어요. 다음엔 심박 벨트 꼭 차고 뛰어요 — 강도 판단이 안 되거든요.")
    if hr < 140:
        return coach_note("ok", f"형님 평균 <b>{hr}bpm</b> — 진짜 딱 좋은 회복 구간이에요. 이런 날이 쌓여서 장거리 엔진이 만들어져요.")
    if hr < 160:
        return coach_note("ok", f"형님 평균 <b>{hr}bpm</b> — 유산소 타겟 안에 딱 들어왔어요. 하프 페이스 잘 만드는 중이에요.")
    if hr < 170:
        return coach_note("warn", f"형님 평균 <b>{hr}bpm</b> — 숨찬 구간에서 너무 오래 머물렀어요. 내일은 <b>150 아래</b>로 눌러서 풀어주세요.")
    return coach_note("warn", f"형님 평균 <b>{hr}bpm</b> — 이건 거의 전력이에요. 이틀은 쉬거나 <b>30분만 가볍게</b> 가요.")


# ───────── 2. 체력·피로·컨디션 (CTL/ATL/TSB) ─────────

def render_fitness_trio_card(d: date, load: list[dict]) -> str:
    r = get_load_for(d, load)
    if not r:
        return coach_note("tip", "형님 훈련 부하 데이터 아직 준비 중이에요. 며칠만 더 쌓이면 나옵니다.")
    ctl, atl, tsb, acwr = r["ctl"], r["atl"], r["tsb"], r["acwr"]
    tsb_color = "#34c759" if tsb >= 0 else "#ff3b30"
    # ACWR 게이지 위치: 0.8=25%, 1.0=50%, 1.3=75%, 1.5=92%, 2.0=100%
    marker_pct = min(100, max(5, int(acwr * 48)))
    ratio_state = "매우 높음" if acwr >= 1.5 else "높음" if acwr >= 1.3 else "적정" if acwr >= 0.8 else "낮음"
    ratio_color = "#ff3b30" if acwr >= 1.3 else "#34c759" if acwr >= 0.8 else "#ff9500"
    body = (
        '<div class="fitness-row">'
        f'<div class="fit-cell"><div><span class="dot" style="background:#007aff"></span>'
        f'<span style="font-size:11px">체력</span></div>'
        f'<div class="v" style="color:#007aff">{int(round(ctl))}</div>'
        f'<div class="lab">장기부하 (CTL)</div><div class="hint">지난 42일 평균</div></div>'
        f'<div class="fit-cell"><div><span class="dot" style="background:#ff3b30"></span>'
        f'<span style="font-size:11px">피로</span></div>'
        f'<div class="v" style="color:#ff3b30">{int(round(atl))}</div>'
        f'<div class="lab">단기부하 (ATL)</div><div class="hint">지난 7일 누적</div></div>'
        f'<div class="fit-cell"><div><span class="dot" style="background:#34c759"></span>'
        f'<span style="font-size:11px">컨디션</span></div>'
        f'<div class="v" style="color:{tsb_color}">{int(round(tsb)):+d}</div>'
        f'<div class="lab">폼 (TSB)</div>'
        f'<div class="hint">{"피크" if tsb > 5 else "회복중" if tsb > -10 else "피로 초과" if tsb > -30 else "과피로"}</div></div>'
        '</div>'
        f'<div style="font-size:13px; margin-top:14px; font-weight:600;">부하비율 {acwr:.2f} · '
        f'<span style="color:{ratio_color}">{ratio_state}</span></div>'
        f'<div class="ratio-bar"><div class="ratio-marker" style="left:{marker_pct}%"></div></div>'
        '<div class="ratio-scale"><span>낮음 0.8</span><span>적정 1.0</span><span>높음 1.3</span><span>위험 1.5+</span></div>'
    )
    if acwr >= 1.5:
        body += ('<div style="font-size:11px; color:var(--muted); margin-top:8px;">'
                 '단기 피로(ATL)가 장기 체력(CTL)을 크게 앞지름. 부상 위험 구간.</div>')
        body += coach_note("warn", f"형님 부하비율 <b>{acwr:.2f}</b>이면 몸이 체력보다 빨리 쌓이는 중이에요. 이번 주 한 번은 장거리 대신 <b>30분 회복 조깅</b>으로 바꿔봐요.")
    elif acwr >= 1.3:
        body += coach_note("warn", f"형님 부하비율 <b>{acwr:.2f}</b> — 상승 구간이에요. 다음 주는 <b>+10% 이내</b>로만 늘려요.")
    else:
        body += coach_note("ok", f"부하비율 <b>{acwr:.2f}</b> — 안정 구간이에요 형님. 이 리듬 그대로 가요.")
    return body


# ───────── 3. 훈련부하 초점 (28일 HRZ 누적) ─────────

def render_focus_28d_card(end_date: date, sessions: list[dict]) -> str:
    start = end_date - timedelta(days=27)
    window = [s for s in sessions if start <= s["_date"] <= end_date and s.get("hr_zones")]
    totals = {"low": 0, "high": 0, "anaerobic": 0}
    for s in window:
        z = s["hr_zones"]
        totals["low"] += (z.get("Z0", 0) + z.get("Z1", 0) + z.get("Z2", 0)) / 60
        totals["high"] += z.get("Z3", 0) / 60 + z.get("Z4", 0) / 60
        totals["anaerobic"] += z.get("Z5", 0) / 60
    total = sum(totals.values())
    if total == 0:
        return '<div style="color:var(--muted);font-size:12px;">최근 28일 심박존 데이터 없음.</div>'
    pct_low = int(round(totals["low"] / total * 100))
    pct_high = int(round(totals["high"] / total * 100))
    pct_ana = 100 - pct_low - pct_high
    body = (
        f'<div class="focus-row"><div class="focus-label">'
        f'<span>무산소 <span style="font-size:10px;color:var(--muted);">(숨 가쁜 전력질주)</span></span>'
        f'<span><b>{pct_ana}%</b> · {int(totals["anaerobic"])}분</span></div>'
        f'<div class="focus-bar-wrap"><div class="focus-bar" style="width:{pct_ana}%;background:#af52de"></div></div></div>'
        f'<div class="focus-row"><div class="focus-label">'
        f'<span>높은유산소 <span style="font-size:10px;color:var(--muted);">(빠른 템포)</span></span>'
        f'<span><b>{pct_high}%</b> · {int(totals["high"])}분</span></div>'
        f'<div class="focus-bar-wrap"><div class="focus-bar" style="width:{pct_high}%;background:#ff9500"></div></div></div>'
        f'<div class="focus-row"><div class="focus-label">'
        f'<span>낮은유산소 <span style="font-size:10px;color:var(--muted);">(편한 페이스)</span></span>'
        f'<span><b>{pct_low}%</b> · {int(totals["low"])}분</span></div>'
        f'<div class="focus-bar-wrap"><div class="focus-bar" style="width:{pct_low}%;background:#5ac8fa"></div></div></div>'
    )
    if pct_low < 20:
        body += ('<div style="font-size:11px; color:var(--red); margin-top:10px; font-weight:600;">'
                 f'⚠️ 낮은유산소 {pct_low}%는 너무 적다. 마라톤 기반 체력은 편한 페이스에서 만들어진다.</div>')
        body += coach_note("warn", "형님 낮은유산소가 20% 미만이면 기초체력이 안 쌓여요. 주 1회는 무조건 <b>대화 가능한 속도</b>로만 뛰어요.")
    elif pct_low < 50:
        body += coach_note("tip", f"형님 낮은유산소 <b>{pct_low}%</b> — 이상적인 80%까지 이지런 조금씩 늘려봐요.")
    else:
        body += coach_note("ok", f"낮은유산소 <b>{pct_low}%</b> — 폴라리즈드 구조 훌륭해요 형님.")
    return body


# ───────── 4. 러닝 파워 (오늘) ─────────

def render_power_card(session: dict) -> str:
    rd = session.get("running_details") or {}
    avg_p = rd.get("avg_power")
    max_p = rd.get("max_power")
    if not avg_p:
        return ('<div style="color:var(--muted);font-size:12px;">파워 데이터 없음 (Apple Watch Series 9+ / Stryd 필요).</div>'
                + coach_note("tip", "형님 파워미터 없어도 괜찮아요. 심박 + 스플릿 페이스만 봐도 강도는 충분히 읽혀요."))
    total_joules = int(round(avg_p * (session.get("duration_sec") or 0)))
    body = (
        f'<div class="kv"><span class="k">평균 파워</span><span class="v">{int(avg_p)} W</span></div>'
        f'<div class="kv"><span class="k">최대 파워</span><span class="v">{int(max_p)} W</span></div>'
        f'<div class="kv"><span class="k">총 일량</span><span class="v">{total_joules//1000} kJ</span></div>'
    )
    pz = session.get("power_zones") or {}
    if pz:
        total = max(pz.get("total", 1), 1)
        colors = {"Z1": "#5ac8fa", "Z2": "#34c759", "Z3": "#ffcc00", "Z4": "#ff9500", "Z5": "#ff3b30", "Z6": "#af52de", "Z7": "#e74c3c"}
        body += '<div style="margin-top:12px;font-size:11px;color:var(--muted);margin-bottom:6px;">파워 존 분포</div>'
        for zk in ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"]:
            sec = pz.get(zk, 0)
            if sec == 0:
                continue
            pct = int(round(sec / total * 100))
            body += (f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:11px;">'
                     f'<span style="width:24px;color:{colors[zk]};font-weight:700">{zk}</span>'
                     f'<div style="flex:1;height:8px;background:var(--line);border-radius:4px;overflow:hidden;">'
                     f'<div style="width:{pct}%;height:100%;background:{colors[zk]}"></div></div>'
                     f'<span style="width:70px;text-align:right">{fmt_mmss(sec)} · {pct}%</span></div>')
    body += coach_note("tip", f"형님 평균 <b>{int(avg_p)}W</b> — 파워 존 분포로 언덕·바람 영향 뺀 실제 출력 확인할 수 있어요.")
    return body


# ───────── 5. 러닝 폼 (오늘) ─────────

def render_form_card(session: dict) -> str:
    rd = session.get("running_details") or {}
    fs = session.get("form_summary") or {}
    cadence = session.get("cadence")
    max_cad = session.get("max_cadence")
    gct = rd.get("avg_stance_time")
    vo = rd.get("avg_vertical_oscillation")
    step_len = rd.get("avg_step_length")
    vr = rd.get("avg_vertical_ratio")

    if not any([gct, vo, step_len, vr]):
        return ('<div style="color:var(--muted);font-size:12px;">러닝 폼 데이터 없음 (고급 다이나믹스 미지원).</div>'
                + coach_note("tip", "형님 케이던스만 보여도 충분해요. <b>170spm 이상</b> 유지가 베스트예요."))

    body = ""
    if cadence:
        body += f'<div class="kv"><span class="k">분당 걸음수 <span class="hint">(케이던스)</span></span><span class="v">{cadence} spm{f" <span class=\"hint\">(최대 {max_cad})</span>" if max_cad else ""}</span></div>'
    if step_len:
        body += f'<div class="kv"><span class="k">보폭</span><span class="v">{step_len/10:.0f} cm</span></div>'
    if vo:
        body += f'<div class="kv"><span class="k">수직 진동 <span class="hint">(위아래 흔들림)</span></span><span class="v">{vo/10:.1f} cm</span></div>'
    if gct:
        body += f'<div class="kv"><span class="k">지면접촉 시간 (GCT)</span><span class="v">{int(gct)} ms</span></div>'
    if vr:
        body += f'<div class="kv"><span class="k">수직 비율 <span class="hint">(낮을수록 좋음)</span></span><span class="v">{vr:.1f}%</span></div>'
    if session.get("hr_drift_pct") is not None:
        drift = session["hr_drift_pct"]
        color = "#ff3b30" if drift > 5 else "#34c759"
        body += f'<div class="kv"><span class="k">심박 드리프트 <span class="hint">(후반 페이스 유지)</span></span><span class="v" style="color:{color}">{drift:+.1f}%</span></div>'

    # 코칭
    if gct and gct < 220:
        body += coach_note("ok", f"형님 접지 <b>{int(gct)}ms</b> — 엘리트 구간이에요. 이 리듬 그대로 가요.")
    elif gct and gct < 260:
        body += coach_note("tip", f"형님 접지 <b>{int(gct)}ms</b> — 준수해요. 회전수만 살짝 올리면 더 효율적이에요.")
    else:
        body += coach_note("tip", "형님 접지가 200ms 이하면 효율 상급, 300ms 넘어가면 질질 끌리는 중이에요. 리듬 무너지면 <b>보폭 줄이고 회전수</b>부터 올려봐요.")
    return body


# ───────── 6. TRIMP / 노력 ─────────

def render_effort_card(session: dict, d: date, load: list[dict]) -> str:
    trimp = session.get("trimp")
    mets = session.get("mets")
    r = get_load_for(d, load)
    trimp_per_min = None
    if trimp and session.get("duration_sec"):
        trimp_per_min = round(trimp / (session["duration_sec"] / 60), 2)
    body = ""
    if trimp is not None:
        body += f'<div class="kv"><span class="k">TRIMP <span class="hint">(심박 부하)</span></span><span class="v">{trimp:.0f}</span></div>'
    if trimp_per_min:
        body += f'<div class="kv"><span class="k">TRIMP/분 <span class="hint">(시간당 강도)</span></span><span class="v">{trimp_per_min}</span></div>'
    if mets:
        body += f'<div class="kv"><span class="k">METs <span class="hint">(대사당량)</span></span><span class="v">{mets}</span></div>'
    if r:
        body += f'<div class="kv"><span class="k">누적 부하 (CTL)</span><span class="v">{r["ctl"]:.0f}</span></div>'
    body += coach_note("tip", "형님, 노력 점수는 <b>심박 × 시간</b>이에요. 같은 거리라도 심박 20만 올라가면 체감 강도는 1.5배예요.")
    return body


# ───────── 7. 오늘의 건강 (FIT 러닝 기반) ─────────

def render_health_card(
    session: dict,
    recent_sessions: list[dict] | None = None,
    health_metrics: dict | None = None,
) -> str:
    """FIT 러닝 세션 + (옵션) Apple Health 일별 지표.

    `health_metrics`는 `health_metrics_pull` SPoE에서 만든 dict:
        {"vo2max": (37.5, "2026-04-22"),   # (값, 측정일) 또는 None
         "vo2max_trend30": +0.3,            # 30일 추세 (선택)
         "hrv_avg7": 28.5,                  # 최근 7일 평균
         "resting_hr_avg7": 73.4}
    호출자 책임으로 채워서 넘긴다 (None 키는 표시 생략).
    delta는 최근 14일 러닝 평균 대비."""
    cal = session.get("calories") or 0
    dur_sec = session.get("duration_sec") or 0
    dur_min = round(dur_sec / 60)
    strides = (session.get("running_details") or {}).get("total_strides") or 0
    steps = strides * 2
    hr_avg = session.get("heart_rate_avg")
    hr_max = session.get("heart_rate_max")
    drift = session.get("hr_drift_pct")

    # 최근 14일 평균 (자기 자신 제외)
    avg_cal = avg_dur_min = avg_steps = avg_hr_avg = None
    if recent_sessions:
        cals = [s.get("calories") for s in recent_sessions if s.get("calories")]
        durs = [s.get("duration_sec") for s in recent_sessions if s.get("duration_sec")]
        strides_list = [(s.get("running_details") or {}).get("total_strides") for s in recent_sessions]
        strides_list = [x for x in strides_list if x]
        hrs = [s.get("heart_rate_avg") for s in recent_sessions if s.get("heart_rate_avg")]
        if cals: avg_cal = sum(cals) / len(cals)
        if durs: avg_dur_min = (sum(durs) / len(durs)) / 60
        if strides_list: avg_steps = (sum(strides_list) / len(strides_list)) * 2
        if hrs: avg_hr_avg = sum(hrs) / len(hrs)

    def delta_html(cur, avg, unit="", up_good=True):
        if avg is None or not cur:
            return '<div class="delta" style="color:var(--muted);">기준 없음</div>'
        diff = cur - avg
        sign = "+" if diff >= 0 else ""
        is_up = diff >= 0
        cls = "delta-up" if (is_up == up_good) else "delta-down"
        arrow = "↑" if is_up else "↓"
        return f'<div class="delta {cls}">{arrow} 평균 대비 {sign}{diff:,.0f}{unit}</div>'

    cells = []
    # 활동에너지
    cells.append(
        '<div class="health-cell">'
        '<div class="lab">활동에너지</div>'
        f'<div><span class="v">{cal:,}</span><span class="u">kcal</span></div>'
        + delta_html(cal, avg_cal, "kcal", up_good=True)
        + '</div>'
    )
    # 운동 시간
    cells.append(
        '<div class="health-cell">'
        '<div class="lab">운동 시간</div>'
        f'<div><span class="v">{dur_min}</span><span class="u">분</span></div>'
        + delta_html(dur_min, avg_dur_min, "분", up_good=True)
        + '</div>'
    )
    # 걸음수 (러닝 stride × 2)
    if steps:
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">걸음수 <span class="hint">(러닝)</span></div>'
            f'<div><span class="v">{steps:,}</span><span class="u">걸음</span></div>'
            + delta_html(steps, avg_steps, "걸음", up_good=True)
            + '</div>'
        )
    # 평균 심박
    if hr_avg:
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">평균 심박</div>'
            f'<div><span class="v">{hr_avg}</span><span class="u">bpm</span></div>'
            + delta_html(hr_avg, avg_hr_avg, "bpm", up_good=False)
            + '</div>'
        )
    # 최고 심박
    if hr_max:
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">최고 심박</div>'
            f'<div><span class="v">{hr_max}</span><span class="u">bpm</span></div>'
            '<div class="delta" style="color:var(--muted);">피크 강도</div>'
            '</div>'
        )
    # 심박 드리프트
    if drift is not None:
        color = "var(--red)" if drift > 5 else "var(--muted)"
        flag = "⚠️ 후반 지침" if drift > 5 else ("↑ 페이스 유지" if drift < 0 else "안정")
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">심박 드리프트 <span class="hint">(후반 유지력)</span></div>'
            f'<div><span class="v" style="color:{color}">{drift:+.1f}</span><span class="u">%</span></div>'
            f'<div class="delta" style="color:var(--muted);">{flag}</div>'
            '</div>'
        )

    body = '<div class="health-grid">' + "".join(cells) + '</div>'

    # ───── Apple Health 지표 (VO2max / HRV / 안정시 심박) ─────
    hm_cells = []
    has_hm = False
    if health_metrics:
        vo = health_metrics.get("vo2max")
        if vo:
            v_val, v_date = vo
            trend = health_metrics.get("vo2max_trend30")
            if trend is not None:
                arrow = "↑" if trend > 0 else ("↓" if trend < 0 else "→")
                cls = "delta-up" if trend > 0 else ("delta-down" if trend < 0 else "delta")
                trend_html = f'<div class="delta {cls}">{arrow} 30일 {trend:+.1f}</div>'
            else:
                trend_html = f'<div class="delta" style="color:var(--muted);">{v_date} 측정</div>'
            hm_cells.append(
                '<div class="health-cell">'
                '<div class="lab">VO₂max <span class="hint">(유산소 능력)</span></div>'
                f'<div><span class="v">{v_val:.1f}</span><span class="u">mL/kg/min</span></div>'
                + trend_html + '</div>'
            )
            has_hm = True
        hrv7 = health_metrics.get("hrv_avg7")
        if hrv7:
            hm_cells.append(
                '<div class="health-cell">'
                '<div class="lab">HRV <span class="hint">(7일 평균)</span></div>'
                f'<div><span class="v">{hrv7:.0f}</span><span class="u">ms</span></div>'
                '<div class="delta" style="color:var(--muted);">자율신경 회복도</div>'
                '</div>'
            )
            has_hm = True
        rhr7 = health_metrics.get("resting_hr_avg7")
        if rhr7:
            hm_cells.append(
                '<div class="health-cell">'
                '<div class="lab">안정시 심박 <span class="hint">(7일 평균)</span></div>'
                f'<div><span class="v">{rhr7:.0f}</span><span class="u">bpm</span></div>'
                '<div class="delta" style="color:var(--muted);">낮을수록 심폐 강함</div>'
                '</div>'
            )
            has_hm = True
        if has_hm:
            body += '<div class="health-grid" style="margin-top:8px;">' + "".join(hm_cells) + '</div>'

    # 코칭
    if drift is not None and drift > 5:
        body += coach_note("warn", f"형님 심박 드리프트 <b>{drift:.1f}%</b> — 후반에 심박 올라갔어요. <b>수분·페이스 조절</b> 신경 써요.")
    elif cal > 800:
        body += coach_note("ok", f"형님 <b>{cal:,}kcal</b> 태웠어요 — 고강도/장거리 세션. 단백질·탄수화물 보충 꼭 챙겨요.")
    elif has_hm and health_metrics and health_metrics.get("vo2max"):
        v_val = health_metrics["vo2max"][0]
        trend = health_metrics.get("vo2max_trend30")
        if trend is not None and trend > 0.2:
            body += coach_note("ok", f"형님 VO₂max <b>{v_val:.1f}</b> — 30일간 <b>+{trend:.1f}</b> 향상. 유산소 베이스 잘 쌓이고 있어요.")
        elif trend is not None and trend < -0.3:
            body += coach_note("warn", f"형님 VO₂max <b>{v_val:.1f}</b> — 30일간 <b>{trend:+.1f}</b> 하락. 회복일/수면 점검해요.")
        else:
            body += coach_note("tip", f"형님 VO₂max <b>{v_val:.1f}</b> — 안정 구간. 베이스 유지 페이스로 가요.")
    else:
        body += coach_note("tip", "형님 이건 러닝 기반 수치만 본 거예요. VO₂max·HRV는 측정값 누적되면 자동으로 들어와요.")
    return body


# ───────── 주간 건강 (러닝 집계) ─────────

def render_weekly_health_card(week_sessions: list[dict], prev_week_sessions: list[dict] | None = None) -> str:
    """주간 러닝 집계. FIT에 있는 필드만 사용 (HRV/VO2max/수면 제외)."""
    def agg(sessions):
        if not sessions:
            return None
        total_km = sum(s.get("distance_km") or 0 for s in sessions)
        total_kcal = sum(s.get("calories") or 0 for s in sessions)
        total_dur = sum(s.get("duration_sec") or 0 for s in sessions)
        total_strides = sum((s.get("running_details") or {}).get("total_strides") or 0 for s in sessions)
        total_trimp = sum(s.get("trimp") or 0 for s in sessions)
        hr_weighted = sum((s.get("heart_rate_avg") or 0) * (s.get("duration_sec") or 0) for s in sessions)
        dur_with_hr = sum((s.get("duration_sec") or 0) for s in sessions if s.get("heart_rate_avg"))
        avg_hr = (hr_weighted / dur_with_hr) if dur_with_hr else None
        return {
            "count": len(sessions),
            "km": total_km,
            "kcal": total_kcal,
            "dur_min": round(total_dur / 60),
            "steps": total_strides * 2,
            "trimp": total_trimp,
            "avg_hr": round(avg_hr) if avg_hr else None,
        }

    cur = agg(week_sessions)
    prev = agg(prev_week_sessions) if prev_week_sessions else None
    if not cur:
        return '<div style="color:var(--muted);font-size:12px;">이번 주 러닝 기록 없음.</div>'

    def delta_line(cur_v, prev_v, unit="", up_good=True, fmt="{:,}"):
        if prev_v is None or not cur_v:
            return '<div class="delta" style="color:var(--muted);">지난주 없음</div>'
        diff = cur_v - prev_v
        sign = "+" if diff >= 0 else ""
        is_up = diff >= 0
        cls = "delta-up" if (is_up == up_good) else "delta-down"
        arrow = "↑" if is_up else "↓"
        return f'<div class="delta {cls}">{arrow} 지난주 대비 {sign}{fmt.format(diff)}{unit}</div>'

    cells = []
    # 총 주행거리
    cells.append(
        '<div class="health-cell">'
        '<div class="lab">총 주행거리</div>'
        f'<div><span class="v">{cur["km"]:.1f}</span><span class="u">km</span></div>'
        + delta_line(round(cur["km"], 1), round(prev["km"], 1) if prev else None, "km", True, "{:+.1f}" if False else "{:,.1f}")
        + '</div>'
    )
    # 총 활동에너지
    cells.append(
        '<div class="health-cell">'
        '<div class="lab">총 활동에너지</div>'
        f'<div><span class="v">{cur["kcal"]:,}</span><span class="u">kcal</span></div>'
        + delta_line(cur["kcal"], prev["kcal"] if prev else None, "kcal", True)
        + '</div>'
    )
    # 총 운동시간
    cells.append(
        '<div class="health-cell">'
        '<div class="lab">총 운동시간</div>'
        f'<div><span class="v">{cur["dur_min"]:,}</span><span class="u">분</span></div>'
        + delta_line(cur["dur_min"], prev["dur_min"] if prev else None, "분", True)
        + '</div>'
    )
    # 총 걸음수
    if cur["steps"]:
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">총 걸음수 <span class="hint">(러닝)</span></div>'
            f'<div><span class="v">{cur["steps"]:,}</span></div>'
            + delta_line(cur["steps"], prev["steps"] if prev and prev["steps"] else None, "", True)
            + '</div>'
        )
    # 평균 심박
    if cur["avg_hr"]:
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">평균 심박 <span class="hint">(시간가중)</span></div>'
            f'<div><span class="v">{cur["avg_hr"]}</span><span class="u">bpm</span></div>'
            + delta_line(cur["avg_hr"], prev["avg_hr"] if prev and prev["avg_hr"] else None, "bpm", False)
            + '</div>'
        )
    # 총 TRIMP
    if cur["trimp"]:
        cells.append(
            '<div class="health-cell">'
            '<div class="lab">총 TRIMP <span class="hint">(심박 부하)</span></div>'
            f'<div><span class="v">{cur["trimp"]:.0f}</span></div>'
            + delta_line(round(cur["trimp"]), round(prev["trimp"]) if prev and prev["trimp"] else None, "", True)
            + '</div>'
        )

    body = '<div class="health-grid">' + "".join(cells) + '</div>'
    # 코칭
    if cur["count"] >= 4:
        body += coach_note("ok", f"형님 이번 주 <b>{cur['count']}회</b> 뛰었어요 — 루틴 제대로 박혔네요. <b>회복일</b>도 꼭 챙겨요.")
    elif cur["count"] <= 1:
        body += coach_note("warn", f"형님 이번 주 <b>{cur['count']}회</b>밖에 안 뛰었어요. <b>주 3회 이상</b>은 가요.")
    else:
        body += coach_note("tip", f"형님 이번 주 <b>{cur['count']}회 · {cur['km']:.1f}km</b>. 이건 러닝 수치만 본 거예요 — HRV·수면은 건강 앱에서 따로 확인해요.")
    return body


def render_weekly_compare_card(
    week_sessions: list[dict],
    prev_week_sessions: list[dict] | None,
    load: list[dict],
    cur_end: date,
    prev_end: date,
) -> str:
    """지난주 대비 변화 카드 — 훈련부하/거리/횟수/CTL/ATL 실데이터."""
    def agg(sessions):
        if not sessions:
            return {"count": 0, "km": 0.0, "trimp": 0.0}
        return {
            "count": len(sessions),
            "km": sum(s.get("distance_km") or 0 for s in sessions),
            "trimp": sum(s.get("trimp") or 0 for s in sessions),
        }

    cur = agg(week_sessions)
    prev = agg(prev_week_sessions or [])
    cur_load = get_load_for(cur_end, load) or {}
    prev_load = get_load_for(prev_end, load) or {}

    def pct_cls(cur_v, prev_v, up_good=True):
        """변화량·% 계산 후 (sign_str, delta_cls) 반환."""
        if prev_v in (None, 0) and cur_v in (None, 0):
            return "0", "delta-up"
        if prev_v in (None, 0):
            return "신규", "delta-flag"
        diff = cur_v - prev_v
        pct = (diff / prev_v) * 100
        sign = "+" if diff >= 0 else ""
        label = f"{sign}{pct:.0f}%"
        is_up = diff >= 0
        if abs(pct) >= 100:
            cls = "delta-flag"
        else:
            cls = "delta-up" if (is_up == up_good) else "delta-down"
        return label, cls

    def count_cls(cur_v, prev_v):
        diff = (cur_v or 0) - (prev_v or 0)
        sign = "+" if diff >= 0 else ""
        label = f"{sign}{diff}회"
        cls = "delta-up" if diff >= 0 else "delta-down"
        return label, cls

    def abs_cls(cur_v, prev_v, up_good=True):
        if cur_v is None and prev_v is None:
            return "-", "delta-up"
        if prev_v is None:
            return "신규", "delta-flag"
        if cur_v is None:
            return "-", "delta-down"
        diff = cur_v - prev_v
        sign = "+" if diff >= 0 else ""
        label = f"{sign}{diff:.0f}"
        is_up = diff >= 0
        cls = "delta-up" if (is_up == up_good) else "delta-down"
        return label, cls

    def row(label, prev_s, cur_s, delta_s, delta_cls):
        return (
            '<div class="cmp-row">'
            f'<span>{label}</span>'
            f'<span class="cmp-val">{prev_s}</span>'
            f'<span class="cmp-val">{cur_s}</span>'
            f'<span class="cmp-delta {delta_cls}">{delta_s}</span>'
            '</div>'
        )

    parts = [
        '<div class="cmp-row head">'
        '<span>항목</span><span class="cmp-val">지난주</span><span class="cmp-val">이번 주</span><span class="cmp-delta">변화</span>'
        '</div>'
    ]

    # 훈련부하 (TRIMP 합)
    d, c = pct_cls(cur["trimp"], prev["trimp"], up_good=True)
    parts.append(row("훈련부하", f"{prev['trimp']:.0f}", f"{cur['trimp']:.0f}", d, c))

    # 거리 (km)
    d, c = pct_cls(cur["km"], prev["km"], up_good=True)
    parts.append(row("거리 (km)", f"{prev['km']:.1f}", f"{cur['km']:.1f}", d, c))

    # 운동 횟수
    d, c = count_cls(cur["count"], prev["count"])
    parts.append(row("운동 횟수", f"{prev['count']}", f"{cur['count']}", d, c))

    # 체력 (CTL) — 증가는 good
    cur_ctl = cur_load.get("ctl")
    prev_ctl = prev_load.get("ctl")
    d, c = abs_cls(cur_ctl, prev_ctl, up_good=True)
    parts.append(row(
        "체력 (CTL)",
        f"{prev_ctl:.0f}" if prev_ctl is not None else "-",
        f"{cur_ctl:.0f}" if cur_ctl is not None else "-",
        d, c,
    ))

    # 피로 (ATL) — 급격한 증가는 flag (과부하)
    cur_atl = cur_load.get("atl")
    prev_atl = prev_load.get("atl")
    if cur_atl is not None and prev_atl is not None and prev_atl > 0:
        diff = cur_atl - prev_atl
        pct = (diff / prev_atl) * 100
        sign = "+" if diff >= 0 else ""
        label = f"{sign}{pct:.0f}%"
        if abs(pct) >= 100:
            cls = "delta-flag"
        elif diff >= 0:
            cls = "delta-down"  # 피로 증가는 나쁨
        else:
            cls = "delta-up"
    else:
        label, cls = abs_cls(cur_atl, prev_atl, up_good=False)
    parts.append(row(
        "피로 (ATL)",
        f"{prev_atl:.0f}" if prev_atl is not None else "-",
        f"{cur_atl:.0f}" if cur_atl is not None else "-",
        label, cls,
    ))

    body = "".join(parts)

    # 코칭
    if cur["count"] == 0:
        body += coach_note("warn", "형님 이번 주 러닝 기록이 없어요. 한 번이라도 끈 묶어요.")
    else:
        tsb = cur_load.get("tsb")
        if tsb is not None and tsb < -30:
            body += coach_note("warn", f"형님 TSB <b>{tsb:.0f}</b> — 피로 많이 쌓였어요. 이번 주 <b>회복 세션</b> 비중 늘려야 해요.")
        elif cur["trimp"] > (prev["trimp"] or 0) * 2 and prev["trimp"]:
            body += coach_note("warn", f"형님 지난주 대비 훈련부하가 <b>2배 이상</b> 뛰었어요. 다음 주는 완만히 조절해요.")
        elif cur["count"] >= 4:
            body += coach_note("ok", f"형님 주 <b>{cur['count']}회 · {cur['km']:.1f}km</b>. 꾸준히 잘 가고 있어요.")
        else:
            body += coach_note("tip", f"형님 주 <b>{cur['count']}회 · {cur['km']:.1f}km · TRIMP {cur['trimp']:.0f}</b>.")
    return body


# ───────── 신규: 랩별 비교표 ─────────

def render_lap_table_card(session: dict) -> str:
    laps = session.get("laps_detail") or session.get("splits") or []
    if not laps:
        return '<div style="color:var(--muted);font-size:12px;">랩 데이터 없음.</div>'
    rows = ['<tr style="font-size:10px;color:var(--muted);text-align:left;">'
            '<th style="padding:4px 2px">랩</th><th style="padding:4px 2px">거리</th>'
            '<th style="padding:4px 2px">페이스</th><th style="padding:4px 2px">HR</th>'
            '<th style="padding:4px 2px">파워</th><th style="padding:4px 2px">케이던스</th></tr>']
    best_pace = None
    worst_pace = None
    for i, lap in enumerate(laps, 1):
        pace = lap.get("pace_per_km") or "-"
        km = lap.get("distance_km", 0)
        hr = lap.get("heart_rate") or "-"
        p = lap.get("avg_power")
        p_str = f"{int(p)}W" if p else "-"
        cad = lap.get("cadence") or "-"
        # 최고/최악 페이스 찾기
        if lap.get("duration_sec") and km > 0:
            pace_sec = lap["duration_sec"] / km
            if best_pace is None or pace_sec < best_pace[1]:
                best_pace = (i, pace_sec)
            if worst_pace is None or pace_sec > worst_pace[1]:
                worst_pace = (i, pace_sec)
        rows.append(f'<tr style="font-size:11px;border-top:1px solid var(--line);">'
                    f'<td style="padding:5px 2px;font-weight:600">{i}</td>'
                    f'<td style="padding:5px 2px">{km:.2f}km</td>'
                    f'<td style="padding:5px 2px">{pace}</td>'
                    f'<td style="padding:5px 2px">{hr}</td>'
                    f'<td style="padding:5px 2px">{p_str}</td>'
                    f'<td style="padding:5px 2px">{cad}</td></tr>')
    table = '<table style="width:100%;border-collapse:collapse;">' + "".join(rows) + '</table>'
    note = ""
    if best_pace and worst_pace and best_pace[0] != worst_pace[0]:
        neg = "네거티브 스플릿" if worst_pace[0] < best_pace[0] else "포지티브 스플릿"
        note = coach_note("tip" if neg == "네거티브 스플릿" else "warn",
                          f"형님 최고 <b>{best_pace[0]}랩</b>, 최저 <b>{worst_pace[0]}랩</b> — <b>{neg}</b>이에요. "
                          f"{'마지막에 가속하는 건 레이스 전략상 최적이에요.' if neg == '네거티브 스플릿' else '초반 과속 주의해요.'}")
    return table + note


# ───────── 신규: GPS 경로 (Leaflet) ─────────

def render_gps_map_card(session: dict) -> str:
    import math
    gps = session.get("gps_points") or []
    if len(gps) < 2:
        return '<div style="color:var(--muted);font-size:12px;">GPS 데이터 없음 (실내 운동 또는 수신 불가).</div>'
    traced_km = 0.0
    for i in range(1, len(gps)):
        dlat = gps[i][0] - gps[i-1][0]
        dlon = gps[i][1] - gps[i-1][1]
        dd = math.sqrt((dlat*111000)**2 + (dlon*111000*math.cos(math.radians(gps[i][0])))**2)
        traced_km += dd / 1000.0
    actual_km = session.get("distance_km") or 0.0
    warning = ""
    lats = [p[0] for p in gps]
    lons = [p[1] for p in gps]
    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    coords_js = "[" + ",".join(f"[{la:.5f},{lo:.5f}]" for la, lo in gps) + "]"
    map_id = f"gps_{hash(session.get('source_file', ''))%100000}"
    return (
        warning +
        f'<div id="{map_id}" style="height:240px;border-radius:12px;overflow:hidden;margin-top:4px;"></div>'
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        f'<script>(function(){{try{{'
        f'var m=L.map("{map_id}",{{zoomControl:false,attributionControl:false}}).setView([{center_lat:.5f},{center_lon:.5f}],14);'
        'L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19}).addTo(m);'
        f'var pts={coords_js};L.polyline(pts,{{color:"#ff6b35",weight:4}}).addTo(m);'
        'm.fitBounds(pts,{padding:[20,20]});'
        '}catch(e){}})();</script>'
    )


# ───────── 신규: 고도 프로파일 ─────────

def render_elevation_card(session: dict) -> str:
    prof = session.get("altitude_profile") or []
    if len(prof) < 2:
        return '<div style="color:var(--muted);font-size:12px;">고도 데이터 없음.</div>'
    ascent = session.get("elevation_m", 0)
    descent = session.get("elevation_descent_m", 0)
    min_a = session.get("min_altitude_m")
    max_a = session.get("max_altitude_m")
    # Build SVG path
    max_km = max(p[0] for p in prof) or 1
    alts = [p[1] for p in prof]
    lo = min(alts); hi = max(alts)
    rng = (hi - lo) or 1
    W, H = 320, 100
    pts = []
    for km, a in prof:
        x = 10 + (km / max_km) * (W - 20)
        y = 10 + (1 - (a - lo) / rng) * (H - 20)
        pts.append(f"{x:.1f},{y:.1f}")
    svg = (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;">'
        f'<polyline points="{" ".join(pts)}" fill="rgba(52,199,89,0.15)" stroke="#34c759" stroke-width="2"/>'
        f'<line x1="10" y1="{H-10}" x2="{W-10}" y2="{H-10}" stroke="#e5e5ea"/>'
        f'</svg>'
    )
    info = (f'<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:4px;">'
            f'<span>↑ +{ascent}m</span><span>↓ -{descent}m</span>'
            f'<span>{min_a or "-"}~{max_a or "-"}m</span></div>')
    dist_km = max_km
    gain_per_km = (ascent / dist_km) if dist_km > 0 else 0
    if gain_per_km >= 20:
        note = coach_note("warn", f"형님 1km당 <b>+{gain_per_km:.0f}m</b> — 업힐이 좀 과해요. 내일은 평지 회복 러닝으로 하퇴 풀어줘요.")
    elif gain_per_km >= 10:
        note = coach_note("tip", f"형님 1km당 <b>+{gain_per_km:.0f}m</b> — 적당한 언덕 자극이에요. 힐 스프린트 효과 기대할 만해요.")
    elif ascent < 10 and dist_km >= 5:
        note = coach_note("tip", "형님 평지 코스였어요. 주 1회는 오르막 포함 루트로 파워 근지구력 보강해봐요.")
    else:
        note = coach_note("ok", f"누적 <b>+{ascent}m</b> — 무난한 지형 프로파일이에요 형님.")
    return svg + info + note


# ───────── 신규: 페이스 히스토그램 ─────────

def render_pace_hist_card(session: dict) -> str:
    h = session.get("pace_histogram")
    if not h:
        return '<div style="color:var(--muted);font-size:12px;">페이스 데이터 없음.</div>'
    labels = {
        "lt430": "<4:30", "430_500": "4:30~5:00", "500_530": "5:00~5:30",
        "530_600": "5:30~6:00", "600_630": "6:00~6:30", "630_700": "6:30~7:00", "gte700": "≥7:00",
    }
    colors = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#5ac8fa", "#007aff", "#af52de"]
    total = sum(h.values()) or 1
    body = ""
    for i, k in enumerate(["lt430", "430_500", "500_530", "530_600", "600_630", "630_700", "gte700"]):
        sec = h.get(k, 0)
        if sec == 0:
            continue
        pct = int(round(sec / total * 100))
        body += (f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:11px;">'
                 f'<span style="width:70px;color:{colors[i]};font-weight:700">{labels[k]}</span>'
                 f'<div style="flex:1;height:10px;background:var(--line);border-radius:5px;overflow:hidden;">'
                 f'<div style="width:{pct}%;height:100%;background:{colors[i]}"></div></div>'
                 f'<span style="width:70px;text-align:right">{fmt_mmss(sec)} · {pct}%</span></div>')
    if not body:
        return '<div style="color:var(--muted);font-size:12px;">페이스 분포 없음.</div>'
    easy_sec = h.get("600_630", 0) + h.get("630_700", 0) + h.get("gte700", 0)
    fast_sec = h.get("lt430", 0) + h.get("430_500", 0)
    easy_pct = int(round(easy_sec / total * 100))
    fast_pct = int(round(fast_sec / total * 100))
    if fast_pct >= 40:
        body += coach_note("warn", f"형님 4:30~5:00 빠른 구간이 <b>{fast_pct}%</b> — 세션이 템포런에 가까워요. 다음엔 의식적으로 <b>6:00+</b>로 유지해요.")
    elif easy_pct >= 60:
        body += coach_note("ok", f"형님 6:00+ 편안 구간 <b>{easy_pct}%</b> — 이지런 의도대로 잘 갔어요. 회복·베이스 세션으로 딱이에요.")
    elif easy_pct >= 30 and fast_pct >= 15:
        body += coach_note("tip", f"형님 중속~빠름 섞여 있어요. 의도한 파르텔렉/프로그레시브면 OK, 아니면 페이스 규율 좀 신경 써요.")
    else:
        body += coach_note("tip", "형님 중간 페이스에 몰려 있어요. 목적(이지/템포/인터벌)을 먼저 정하고 페이스 일관성 올려봐요.")
    return body


# ───────── 신규: 케이던스 존 ─────────

def render_cadence_zones_card(session: dict) -> str:
    cz = session.get("cadence_zones")
    if not cz:
        return '<div style="color:var(--muted);font-size:12px;">케이던스 데이터 없음.</div>'
    labels = {
        "C1_lt160": "<160 spm (느림)", "C2_160_170": "160-170", "C3_170_180": "170-180 (최적)",
        "C4_180_190": "180-190", "C5_gte190": "≥190 (빠름)",
    }
    colors = ["#af52de", "#5ac8fa", "#34c759", "#ff9500", "#ff3b30"]
    total = sum(cz.values()) or 1
    body = ""
    for i, k in enumerate(["C1_lt160", "C2_160_170", "C3_170_180", "C4_180_190", "C5_gte190"]):
        sec = cz.get(k, 0)
        pct = int(round(sec / total * 100))
        body += (f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:11px;">'
                 f'<span style="width:110px;color:{colors[i]};font-weight:700">{labels[k]}</span>'
                 f'<div style="flex:1;height:10px;background:var(--line);border-radius:5px;overflow:hidden;">'
                 f'<div style="width:{pct}%;height:100%;background:{colors[i]}"></div></div>'
                 f'<span style="width:55px;text-align:right">{pct}%</span></div>')
    opt_pct = int(round(cz.get("C3_170_180", 0) / total * 100))
    if opt_pct >= 40:
        body += coach_note("ok", f"형님 170-180spm 구간 <b>{opt_pct}%</b> — 부상 확률 최저존에서 오래 뛰었어요.")
    else:
        body += coach_note("tip", f"형님 170-180 최적존 <b>{opt_pct}%</b> — 의식적으로 회전수 조금만 올려봐요. 무릎 부담이 확 줄어요.")
    return body


# ───────── 신규: 환경 (습도·온도) ─────────

def render_env_card(session: dict) -> str:
    t = session.get("temperature_c")
    h = session.get("humidity_pct")
    if t is None and h is None:
        return '<div style="color:var(--muted);font-size:12px;">환경 데이터 없음.</div>'
    body = ""
    if t is not None:
        body += f'<div class="kv"><span class="k">평균 기온</span><span class="v">{t:.0f}°C</span></div>'
        if session.get("max_temperature_c") is not None:
            body += f'<div class="kv"><span class="k">최고 기온</span><span class="v">{session["max_temperature_c"]:.0f}°C</span></div>'
    if h is not None:
        body += f'<div class="kv"><span class="k">습도</span><span class="v">{h:.0f}%</span></div>'
    # 기온 코칭
    if t is not None:
        if t < 5:
            body += coach_note("tip", "형님 추운 날씨예요. 워밍업 충분히 하고, 근육 뻣뻣할 땐 스트레칭 2배로 해요.")
        elif t > 25:
            body += coach_note("warn", "형님 더워요. <b>수분 섭취</b> 더 늘리고 페이스는 <b>10~15초</b> 천천히 가요.")
        elif 10 <= t <= 20:
            body += coach_note("ok", f"형님 <b>{t:.0f}°C</b> — 러닝 최적 기온이에요. 이런 날은 PR 노려볼 만해요.")
    return body


# ───────── 주간: 폴라리즈드 80/20 검증 ─────────

def render_polarized_card(week_sessions: list[dict]) -> str:
    tot = {"low": 0, "high": 0, "anaerobic": 0}
    for s in week_sessions:
        z = s.get("hr_zones") or {}
        tot["low"] += z.get("Z0", 0) + z.get("Z1", 0) + z.get("Z2", 0)
        tot["high"] += z.get("Z3", 0) + z.get("Z4", 0)
        tot["anaerobic"] += z.get("Z5", 0)
    total = sum(tot.values())
    if total == 0:
        return '<div style="color:var(--muted);font-size:12px;">이번 주 심박존 데이터 없음.</div>'
    pct_low = int(round(tot["low"] / total * 100))
    pct_high = int(round(tot["high"] / total * 100))
    pct_ana = 100 - pct_low - pct_high
    target_low = 80
    diff = pct_low - target_low
    body = (
        f'<div style="display:flex;justify-content:space-around;text-align:center;margin:10px 0;">'
        f'<div><div style="font-size:28px;font-weight:800;color:#5ac8fa">{pct_low}%</div>'
        f'<div style="font-size:11px;color:var(--muted)">저강도<br>Z1-Z2</div></div>'
        f'<div><div style="font-size:28px;font-weight:800;color:#ff9500">{pct_high}%</div>'
        f'<div style="font-size:11px;color:var(--muted)">중강도<br>Z3-Z4</div></div>'
        f'<div><div style="font-size:28px;font-weight:800;color:#ff3b30">{pct_ana}%</div>'
        f'<div style="font-size:11px;color:var(--muted)">고강도<br>Z5</div></div></div>'
        f'<div style="font-size:12px;text-align:center;color:var(--muted);margin-bottom:10px;">목표: 저강도 80% · 중 10% · 고 10%</div>'
    )
    if diff >= -10:
        body += coach_note("ok", f"형님 저강도 <b>{pct_low}%</b> — 폴라리즈드 구조 훌륭해요. 마라톤 훈련 황금비에요.")
    elif diff >= -30:
        body += coach_note("warn", f"형님 저강도 <b>{pct_low}%</b>예요. 목표 80%랑 <b>{abs(diff)}%p</b> 차이라 이지런 좀 더 늘려야 해요.")
    else:
        body += coach_note("warn", f"형님 저강도 <b>{pct_low}%</b>밖에 안 돼요. 이대로 가면 부상·정체 와요. 다음 주는 <b>절반 이상</b>을 편한 속도로 가요.")
    return body


# ───────── 주간: CTL/ATL 그래프 실데이터 ─────────

def render_weekly_ctl_chart(today: date, load: list[dict]) -> str:
    """지난 7일 CTL/ATL/TSB SVG polyline + 범례."""
    start = today - timedelta(days=6)
    days = []
    d = start
    while d <= today:
        r = get_load_for(d, load)
        if r:
            days.append((d, r["ctl"], r["atl"], r["ctl"] - r["atl"]))
        else:
            days.append((d, 0, 0, 0))
        d += timedelta(days=1)
    if not days:
        return "(데이터 부족)"
    max_v = max(max(r[1], r[2]) for r in days) or 1
    min_tsb = min(r[3] for r in days)
    max_tsb = max(r[3] for r in days)
    tsb_range = max(max_tsb - min_tsb, 1)
    W, H = 340, 170
    x_step = (W - 40) / max(len(days) - 1, 1)

    def yv(v, vmin=0, vmax=max_v):
        return 10 + (1 - (v - vmin) / max(vmax - vmin, 1)) * (H - 40)

    ctl_pts = " ".join(f"{20 + i*x_step:.1f},{yv(r[1]):.1f}" for i, r in enumerate(days))
    atl_pts = " ".join(f"{20 + i*x_step:.1f},{yv(r[2]):.1f}" for i, r in enumerate(days))
    tsb_pts = " ".join(f"{20 + i*x_step:.1f},{yv(r[3], min_tsb, max_tsb):.1f}" for i, r in enumerate(days))

    day_labels = "".join(
        f'<text x="{20 + i*x_step:.1f}" y="{H-8}" font-size="9" fill="#6e6e73" text-anchor="middle">'
        f'{["월","화","수","목","금","토","일"][r[0].weekday()]}</text>'
        for i, r in enumerate(days)
    )
    latest = days[-1]
    ctl_now, atl_now, tsb_now = latest[1], latest[2], latest[3]
    ctl_start = days[0][1]
    ctl_delta = ctl_now - ctl_start
    if tsb_now <= -15:
        note = coach_note("warn", f"형님 TSB <b>{tsb_now:+.0f}</b> — 피로 위험대예요. 이번 주 1회는 <b>완전 휴식</b>이나 크로스 트레이닝으로 풀어요.")
    elif tsb_now >= 15:
        note = coach_note("tip", f"형님 TSB <b>{tsb_now:+.0f}</b> — 회복은 충분한데 자극이 좀 부족해요. <b>강도 있는 세션 1회</b> 더 넣어봐요.")
    elif ctl_delta >= 3:
        note = coach_note("ok", f"형님 CTL <b>+{ctl_delta:.0f}</b> — 체력 확실히 올라오고 있어요. 지금 볼륨 그대로 가요.")
    elif ctl_delta <= -3:
        note = coach_note("warn", f"형님 CTL <b>{ctl_delta:.0f}</b> — 체력 하락 중이에요. 주간 거리·시간 점진 복구 계획 세워요.")
    else:
        note = coach_note("ok", f"형님 CTL <b>{ctl_now:.0f}</b> / TSB <b>{tsb_now:+.0f}</b> — 밸런스 안정적이에요.")
    return (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;">'
        f'<polyline points="{ctl_pts}" stroke="#007aff" stroke-width="2.5" fill="none"/>'
        f'<polyline points="{atl_pts}" stroke="#ff3b30" stroke-width="2.5" fill="none"/>'
        f'<polyline points="{tsb_pts}" stroke="#34c759" stroke-width="2.5" fill="none" stroke-dasharray="3,3"/>'
        f'{day_labels}</svg>'
        f'<div class="legend">'
        f'<span><span class="dot" style="background:#007aff"></span>체력 CTL {ctl_now:.0f}</span>'
        f'<span><span class="dot" style="background:#ff3b30"></span>피로 ATL {atl_now:.0f}</span>'
        f'<span><span class="dot" style="background:#34c759"></span>컨디션 TSB {tsb_now:+.0f}</span></div>'
        + note
    )


# ───────── 주간: 거리별 PR ─────────

def render_pr_board(all_sessions: list[dict], until: date) -> str:
    """전체 히스토리에서 1K/5K/10K 베스트 찾기 (lap 기반 근사)."""
    prs = {"1K": None, "5K": None, "10K": None, "21.1K": None}
    for s in all_sessions:
        if s["_date"] > until:
            continue
        if s.get("workout_type") != "러닝":
            continue
        dist = s.get("distance_km") or 0
        dur = s.get("duration_sec") or 0
        if dist >= 21.0 and dur:
            pace = dur / dist
            if prs["21.1K"] is None or pace < prs["21.1K"][0]:
                prs["21.1K"] = (pace, s)
        if dist >= 10.0 and dur:
            pace = dur / dist
            if prs["10K"] is None or pace < prs["10K"][0]:
                prs["10K"] = (pace, s)
        if dist >= 5.0 and dur:
            pace = dur / dist
            if prs["5K"] is None or pace < prs["5K"][0]:
                prs["5K"] = (pace, s)
        if dist >= 1.0 and dur:
            pace = dur / dist
            if prs["1K"] is None or pace < prs["1K"][0]:
                prs["1K"] = (pace, s)
    body = ""
    for label, entry in prs.items():
        if entry is None:
            body += f'<div class="kv"><span class="k">{label}</span><span class="v" style="color:var(--muted)">기록 없음</span></div>'
        else:
            pace, s = entry
            time_str = fmt_mmss(pace * {"1K": 1, "5K": 5, "10K": 10, "21.1K": 21.0975}[label])
            body += f'<div class="kv"><span class="k">{label} 평균 페이스</span><span class="v">{fmt_pace(pace)} <span class="hint">({s["date"]} · {time_str})</span></span></div>'
    if prs["21.1K"] is None:
        body += coach_note("warn", "형님 하프 PR이 없어요. <b>6/7 하프 전까지 최소 1회 풀 21km 시뮬레이션</b> 세션은 꼭 가요.")
    elif prs["10K"] is None:
        body += coach_note("tip", "형님 10K PR 없어요. 기준 속도 측정하려면 <b>월 1회 10km 테스트</b> 넣어봐요.")
    else:
        body += coach_note("ok", f"형님 거리별 PR 차곡차곡 쌓이는 중이에요. 5K/10K 페이스 비율로 하프 목표 역산해볼 만해요.")
    return body


# ───────── 월간: 12주 롤링 마일리지 ─────────

def render_12w_rolling(all_sessions: list[dict], today: date) -> str:
    weeks: list[tuple[date, float]] = []
    for i in range(11, -1, -1):
        wk_start = today - timedelta(days=today.weekday() + i * 7)
        wk_end = wk_start + timedelta(days=6)
        km = sum(s.get("distance_km") or 0 for s in all_sessions
                 if wk_start <= s["_date"] <= wk_end and s.get("workout_type") == "러닝")
        weeks.append((wk_start, km))
    max_km = max(k for _, k in weeks) or 1
    W, H = 340, 120
    bar_w = (W - 20) / len(weeks)
    bars = ""
    for i, (ws, km) in enumerate(weeks):
        h = (km / max_km) * (H - 30) if km > 0 else 1
        x = 10 + i * bar_w
        y = H - 20 - h
        color = "#ff6b35" if i == len(weeks) - 1 else "#007aff"
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w*0.7:.1f}" height="{h:.1f}" fill="{color}" rx="2"/>'
        if km > 0:
            bars += f'<text x="{x + bar_w*0.35:.1f}" y="{y-3:.1f}" font-size="9" fill="#1d1d1f" text-anchor="middle">{km:.0f}</text>'
    svg = f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;">{bars}</svg>'
    avg = sum(k for _, k in weeks) / len(weeks)
    recent4 = sum(k for _, k in weeks[-4:]) / 4
    trend = "📈 상승" if recent4 > avg * 1.1 else "📉 하락" if recent4 < avg * 0.9 else "→ 유지"
    caption = f'<div style="font-size:11px;color:var(--muted);text-align:center;margin-top:4px;">12주 평균 {avg:.1f}km · 최근 4주 {recent4:.1f}km · {trend}</div>'
    if recent4 >= avg * 1.3:
        note = coach_note("warn", f"형님 최근 4주 평균 <b>{recent4:.0f}km</b> — 12주 평균 대비 <b>+30% 이상</b>이에요. 다음 주는 <b>디로드(−20%)</b> 가요.")
    elif recent4 > avg * 1.1:
        note = coach_note("ok", f"형님 최근 4주 <b>{recent4:.0f}km</b> — 건강한 증가 추세예요. 앞으로도 <b>10% 이내</b>로만 늘려요.")
    elif recent4 < avg * 0.7:
        note = coach_note("warn", f"형님 최근 4주 <b>{recent4:.0f}km</b> — 체력 하락 구간이에요. 다음 주부터 <b>주 +3~5km</b> 복귀 계획 세워요.")
    elif recent4 < avg * 0.9:
        note = coach_note("tip", f"형님 최근 4주 <b>{recent4:.0f}km</b> — 살짝 줄었어요. 컨디션 이상 없으면 원래 볼륨으로 복귀해요.")
    else:
        note = coach_note("ok", f"형님 12주 평균 <b>{avg:.0f}km</b> 유지 — 안정적 베이스에요.")
    return svg + caption + note


# ───────── 월간: LSD (90분+) 빈도 ─────────

def render_lsd_card(sessions: list[dict]) -> str:
    lsd = [s for s in sessions if (s.get("duration_sec") or 0) >= 90 * 60 and s.get("workout_type") == "러닝"]
    count = len(lsd)
    total_km = sum(s.get("distance_km") or 0 for s in lsd)
    body = f'<div class="kv"><span class="k">LSD 세션 (90분+)</span><span class="v">{count}회</span></div>'
    body += f'<div class="kv"><span class="k">LSD 총 거리</span><span class="v">{total_km:.1f}km</span></div>'
    if lsd:
        longest = max(lsd, key=lambda s: s.get("duration_sec", 0))
        body += f'<div class="kv"><span class="k">최장</span><span class="v">{longest["distance_km"]}km ({fmt_mmss(longest["duration_sec"])})</span></div>'
    if count == 0:
        body += coach_note("warn", "형님 LSD <b>0회</b>예요. 마라톤 기반 체력은 <b>90분 이상 장거리</b>에서 만들어져요. 주 1회는 꼭 가요.")
    elif count < 2:
        body += coach_note("tip", f"형님 LSD <b>{count}회</b> — 격주 정도예요. 레이스 <b>4주 전부터</b>는 주 1회 권장이에요.")
    else:
        body += coach_note("ok", f"형님 LSD <b>{count}회</b> — 마라톤 기초 훌륭해요.")
    return body


# ───────── 월간: 기온-페이스 상관 ─────────

def render_temp_corr_card(sessions: list[dict]) -> str:
    pts = []
    for s in sessions:
        t = s.get("temperature_c")
        d = s.get("distance_km") or 0
        dur = s.get("duration_sec") or 0
        if t is None or d < 1 or dur < 60:
            continue
        pace = dur / d  # sec/km
        pts.append((t, pace))
    if len(pts) < 3:
        return '<div style="color:var(--muted);font-size:12px;">기온 vs 페이스 샘플 부족 (3세션+).</div>'
    t_min = min(p[0] for p in pts); t_max = max(p[0] for p in pts)
    p_min = min(p[1] for p in pts); p_max = max(p[1] for p in pts)
    t_range = max(t_max - t_min, 1); p_range = max(p_max - p_min, 1)
    W, H = 320, 140
    dots = ""
    for t, pace in pts:
        x = 20 + (t - t_min) / t_range * (W - 40)
        y = 10 + (pace - p_min) / p_range * (H - 40)
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#ff6b35" opacity="0.7"/>'
    svg = (f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;">'
           f'<text x="10" y="15" font-size="9" fill="#6e6e73">느림</text>'
           f'<text x="10" y="{H-5}" font-size="9" fill="#6e6e73">빠름</text>'
           f'<text x="20" y="{H-5}" font-size="9" fill="#6e6e73">{t_min:.0f}°C</text>'
           f'<text x="{W-30}" y="{H-5}" font-size="9" fill="#6e6e73">{t_max:.0f}°C</text>'
           f'{dots}</svg>')
    caption = f'<div style="font-size:11px;color:var(--muted);text-align:center;margin-top:4px;">{len(pts)}세션 · 기온 {t_min:.0f}~{t_max:.0f}°C · 페이스 {fmt_pace(p_min)}~{fmt_pace(p_max)}</div>'
    n = len(pts)
    mean_t = sum(p[0] for p in pts) / n
    mean_p = sum(p[1] for p in pts) / n
    num = sum((p[0] - mean_t) * (p[1] - mean_p) for p in pts)
    den_t = sum((p[0] - mean_t) ** 2 for p in pts)
    den_p = sum((p[1] - mean_p) ** 2 for p in pts)
    r = num / ((den_t * den_p) ** 0.5) if den_t * den_p > 0 else 0
    if r >= 0.4:
        note = coach_note("tip", f"형님 상관 <b>r={r:.2f}</b> — 기온 오를수록 페이스 느려지는 경향이에요. 여름엔 새벽·저녁 러닝으로 돌려요.")
    elif r <= -0.4:
        note = coach_note("tip", f"형님 상관 <b>r={r:.2f}</b> — 추운 날이 오히려 느린 패턴이에요. 동계엔 <b>워밍업 10분+</b> 충분히 해요.")
    else:
        note = coach_note("ok", f"형님 상관 <b>r={r:.2f}</b> — 기온 영향 미미해요. 환경보다 컨디션이 더 큰 변수예요.")
    return svg + caption + note


# ═══════════ HealthFit 스타일 신규 카드 (v3) ═══════════

import math

ALPHA_CTL = 1 - math.exp(-1 / 42)
ALPHA_ATL = 1 - math.exp(-1 / 7)


def render_fitness_hero_chart(today: date, load: list[dict], history_days: int = 45, forecast_days: int = 14) -> str:
    """HealthFit 메인 Fitness 차트 스타일.

    - CTL(파 실선), ATL(빨 실선), TSB(녹 영역채움)
    - 오늘 이후 점선으로 forecast (무운동 가정 EWMA 감쇠)
    - CTL 신뢰밴드 (연한 파랑 영역)
    - 상단에 3개 숫자 (CTL/ATL/TSB)
    """
    if not load:
        return '<div style="color:var(--muted);font-size:12px;">훈련부하 데이터 없음.</div>'
    # history_days 범위 추출
    start = today - timedelta(days=history_days - 1)
    series = []
    for r in load:
        d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        if start <= d <= today:
            series.append((d, r["ctl"], r["atl"], r["ctl"] - r["atl"]))
    if not series:
        return '<div style="color:var(--muted);font-size:12px;">최근 데이터 없음.</div>'
    series.sort()
    last_d, last_ctl, last_atl, last_tsb = series[-1]

    # Forecast (TRIMP=0 가정 감쇠)
    forecast = []
    ctl, atl = last_ctl, last_atl
    for i in range(1, forecast_days + 1):
        ctl = ctl + (0 - ctl) * ALPHA_CTL
        atl = atl + (0 - atl) * ALPHA_ATL
        forecast.append((last_d + timedelta(days=i), ctl, atl, ctl - atl))

    all_days = series + forecast
    n_hist = len(series)

    # 좌표 스케일
    all_vals = [v for _, c, a, t in all_days for v in (c, a, t)]
    v_max = max(all_vals)
    v_min = min(all_vals)
    v_range = max(v_max - v_min, 1)

    W, H = 340, 180
    pad_l, pad_r, pad_t, pad_b = 22, 12, 14, 22
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b
    x_step = plot_w / max(len(all_days) - 1, 1)

    def x_at(i): return pad_l + i * x_step
    def y_at(v): return pad_t + (1 - (v - v_min) / v_range) * plot_h

    # 0선
    y_zero = y_at(0) if v_min <= 0 <= v_max else None

    # CTL 신뢰밴드 (±stddev 최근 30일)
    recent_ctl = [c for _, c, _, _ in series[-30:]]
    if len(recent_ctl) >= 5:
        mean = sum(recent_ctl) / len(recent_ctl)
        variance = sum((c - mean) ** 2 for c in recent_ctl) / len(recent_ctl)
        sd = math.sqrt(variance)
    else:
        sd = 3.0
    band_pts_upper = [(x_at(i), y_at(c + sd)) for i, (_, c, _, _) in enumerate(all_days)]
    band_pts_lower = [(x_at(i), y_at(c - sd)) for i, (_, c, _, _) in enumerate(all_days)]
    band_path = (
        "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in band_pts_upper)
        + " L " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(band_pts_lower))
        + " Z"
    )

    # CTL/ATL/TSB polyline (history vs forecast 분리)
    def pts_str(key_idx, rng):
        return " ".join(f"{x_at(i):.1f},{y_at(all_days[i][key_idx]):.1f}" for i in rng)

    hist_rng = range(0, n_hist)
    fut_rng = range(n_hist - 1, len(all_days))  # 연결선

    ctl_hist = pts_str(1, hist_rng)
    ctl_fut = pts_str(1, fut_rng)
    atl_hist = pts_str(2, hist_rng)
    atl_fut = pts_str(2, fut_rng)
    tsb_hist = pts_str(3, hist_rng)
    tsb_fut = pts_str(3, fut_rng)

    # TSB 영역 채움 (y_zero 기준)
    tsb_fill = ""
    if y_zero is not None:
        tsb_fill_pts = [(x_at(i), y_at(all_days[i][3])) for i in hist_rng]
        tsb_fill_path = (
            f"M {tsb_fill_pts[0][0]:.1f},{y_zero:.1f} "
            + " L ".join(f"{x:.1f},{y:.1f}" for x, y in tsb_fill_pts)
            + f" L {tsb_fill_pts[-1][0]:.1f},{y_zero:.1f} Z"
        )
        tsb_fill = f'<path d="{tsb_fill_path}" fill="#34c759" opacity="0.12"/>'

    # x축 라벨 (처음/중간/오늘/끝)
    lbl_idx = [0, n_hist - 1, len(all_days) - 1]
    x_labels = "".join(
        f'<text x="{x_at(i):.1f}" y="{H - 6}" font-size="9" fill="#6e6e73" text-anchor="middle">'
        f'{all_days[i][0].strftime("%m/%d")}</text>'
        for i in lbl_idx
    )

    # 오늘 수직 마커
    today_x = x_at(n_hist - 1)
    today_marker = (
        f'<line x1="{today_x:.1f}" y1="{pad_t}" x2="{today_x:.1f}" y2="{H - pad_b}" '
        f'stroke="#999" stroke-width="1" stroke-dasharray="2,2" opacity="0.5"/>'
        f'<circle cx="{today_x:.1f}" cy="{y_at(last_atl):.1f}" r="5" fill="#ff3b30"/>'
        f'<circle cx="{today_x:.1f}" cy="{y_at(last_atl):.1f}" r="10" fill="#ff3b30" opacity="0.25"/>'
    )

    # 0선
    zero_line = ""
    if y_zero is not None:
        zero_line = f'<line x1="{pad_l}" y1="{y_zero:.1f}" x2="{W - pad_r}" y2="{y_zero:.1f}" stroke="#ddd" stroke-width="1" stroke-dasharray="3,3"/>'

    tsb_color = "#34c759" if last_tsb >= 0 else "#ff3b30"

    header = (
        f'<div style="display:flex;justify-content:space-around;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid #f0f0f0;">'
        f'<div style="text-align:center;"><div style="font-size:11px;color:#6e6e73;"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#007aff;margin-right:4px;"></span>Fitness (CTL)</div>'
        f'<div style="font-size:22px;font-weight:700;color:#007aff;">{int(round(last_ctl))}</div></div>'
        f'<div style="text-align:center;"><div style="font-size:11px;color:#6e6e73;"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#ff3b30;margin-right:4px;"></span>Fatigue (ATL)</div>'
        f'<div style="font-size:22px;font-weight:700;color:#ff3b30;">{int(round(last_atl))}</div></div>'
        f'<div style="text-align:center;"><div style="font-size:11px;color:#6e6e73;"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{tsb_color};margin-right:4px;"></span>Form (TSB)</div>'
        f'<div style="font-size:22px;font-weight:700;color:{tsb_color};">{int(round(last_tsb)):+d}</div></div>'
        f'</div>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;">'
        f'<path d="{band_path}" fill="#007aff" opacity="0.10"/>'
        f'{zero_line}'
        f'{tsb_fill}'
        f'<polyline points="{tsb_hist}" stroke="#34c759" stroke-width="2" fill="none"/>'
        f'<polyline points="{ctl_hist}" stroke="#007aff" stroke-width="2.5" fill="none"/>'
        f'<polyline points="{atl_hist}" stroke="#ff3b30" stroke-width="2.5" fill="none"/>'
        f'<polyline points="{ctl_fut}" stroke="#007aff" stroke-width="2" fill="none" stroke-dasharray="4,3" opacity="0.6"/>'
        f'<polyline points="{atl_fut}" stroke="#ff3b30" stroke-width="2" fill="none" stroke-dasharray="4,3" opacity="0.6"/>'
        f'<polyline points="{tsb_fut}" stroke="#34c759" stroke-width="1.5" fill="none" stroke-dasharray="4,3" opacity="0.6"/>'
        f'{today_marker}'
        f'{x_labels}'
        f'</svg>'
    )

    # 예측 요약
    fut_14 = forecast[-1]
    caption = (
        f'<div style="font-size:11px;color:var(--muted);text-align:center;margin-top:6px;line-height:1.5;">'
        f'점선 = 14일 무운동 시 예측 · 예상 Form {int(round(fut_14[3])):+d} ({fut_14[0].strftime("%m/%d")})'
        f'</div>'
    )
    ctl_30d_ago = series[-30][1] if len(series) >= 30 else series[0][1]
    ctl_delta = last_ctl - ctl_30d_ago
    if last_tsb <= -20:
        note = coach_note("warn", f"형님 Form <b>{int(round(last_tsb)):+d}</b>예요 — 오버리칭 경계선이에요. 이번 주는 <b>디로드 필수</b>, 고강도 세션은 쉬어가요.")
    elif last_tsb >= 20 and ctl_delta < 0:
        note = coach_note("warn", f"형님 Form <b>+{int(round(last_tsb))}</b>인데 CTL이 떨어지는 중이에요 — 디트레이닝 신호예요. 주간 거리부터 다시 올려가요.")
    elif ctl_delta >= 5:
        note = coach_note("ok", f"형님 30일간 CTL <b>+{ctl_delta:.0f}</b> — 체력 확실히 쌓이는 중이에요! 지금 리듬 그대로 가요.")
    elif -5 <= last_tsb <= 5 and abs(ctl_delta) < 3:
        note = coach_note("tip", "형님 Form·CTL 모두 정체 중이에요. 주 1회 <b>인터벌이나 템포런</b> 하나 넣어서 자극 바꿔봐요.")
    elif ctl_delta <= -5:
        note = coach_note("warn", f"형님 30일간 CTL <b>{ctl_delta:.0f}</b> — 체력이 빠지고 있어요. 주간 볼륨 다시 짜야 해요.")
    else:
        note = coach_note("ok", f"형님 CTL <b>{int(round(last_ctl))}</b> / Form <b>{int(round(last_tsb)):+d}</b> — 밸런스 좋아요.")
    return header + svg + caption + note


def render_acwr_gauge_big(today: date, load: list[dict]) -> str:
    """HealthFit Training Load Ratio 스타일 — 4색 수평 게이지."""
    r = get_load_for(today, load)
    if not r:
        return '<div style="color:var(--muted);font-size:12px;">ACWR 데이터 없음.</div>'
    acwr = r["acwr"]
    # 구간: 0-0.8 파랑(Low) / 0.8-1.3 녹(Optimal) / 1.3-1.5 주황(High) / 1.5-2.5 빨강(Very High)
    # 게이지 전체 0~2.5 스케일
    max_scale = 2.5
    marker_pct = min(99, max(1, acwr / max_scale * 100))
    if acwr < 0.8:
        state, color = "Low", "#5ac8fa"
    elif acwr < 1.3:
        state, color = "Optimal", "#34c759"
    elif acwr < 1.5:
        state, color = "High", "#ff9500"
    else:
        state, color = "Very High", "#ff3b30"
    msg = (
        "단기부하(ATL)가 장기부하(CTL)보다 크게 높음." if acwr >= 1.5 else
        "상승 구간 — 다음 주 증가폭 제한." if acwr >= 1.3 else
        "이상적인 훈련 부하." if acwr >= 0.8 else
        "부하 낮음 — 점진 증가 여지."
    )
    body = (
        f'<div style="display:flex;align-items:center;gap:16px;margin-bottom:12px;">'
        f'<div style="font-size:34px;font-weight:800;color:{color};">{acwr:.2f}</div>'
        f'<div style="flex:1;">'
        f'<div style="font-size:14px;font-weight:700;color:{color};text-align:center;margin-bottom:6px;">{state}</div>'
        f'<div style="position:relative;height:10px;border-radius:5px;overflow:hidden;'
        f'background:linear-gradient(to right,#5ac8fa 0%,#5ac8fa 32%,#34c759 32%,#34c759 52%,#ff9500 52%,#ff9500 60%,#ff3b30 60%,#ff3b30 100%);">'
        f'<div style="position:absolute;left:{marker_pct}%;top:-3px;width:16px;height:16px;border-radius:50%;'
        f'background:#fff;border:3px solid {color};transform:translateX(-50%);box-shadow:0 1px 3px rgba(0,0,0,0.2);"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;font-size:9px;color:#6e6e73;margin-top:4px;">'
        f'<span>0.8</span><span>1.3</span><span>1.5</span><span>2.0+</span></div>'
        f'</div>'
        f'</div>'
        f'<div style="font-size:12px;color:#1d1d1f;line-height:1.55;">{msg}</div>'
    )
    if acwr >= 1.5:
        body += coach_note("warn", f"형님 지금 부상위험이 커요. ACWR <b>{acwr:.2f}</b>예요. 다음 주는 <b>거리·강도 30% 줄이고</b> 회복 조깅 2번 이상으로 가요.")
    elif acwr >= 1.3:
        body += coach_note("tip", f"형님 부하 상승 끝물이에요. ACWR <b>{acwr:.2f}</b> — 다음 주 증가폭은 <b>10% 안쪽</b>으로만 잡아요.")
    elif acwr >= 0.8:
        body += coach_note("ok", f"형님 ACWR <b>{acwr:.2f}</b> — 딱 Sweet spot이에요. 지금 페이스 유지하면서 천천히 늘려도 돼요.")
    else:
        body += coach_note("tip", f"형님 부하 여유 있어요. ACWR <b>{acwr:.2f}</b> — 이번 주에 <b>거리 +10%</b> 늘려볼 타이밍이에요.")
    return body


def render_heatmap_26w(all_sessions: list[dict], today: date, weeks: int = 26) -> str:
    """GitHub contribution 스타일 7×N 히트맵.

    - 세로: 월~일 (7행)
    - 가로: 주 (N주)
    - 색: TRIMP 또는 거리 기반 opacity
    """
    # N주 전 월요일부터 시작
    today_monday = today - timedelta(days=today.weekday())
    start = today_monday - timedelta(days=(weeks - 1) * 7)
    # 날짜별 거리
    daily = {}
    for s in all_sessions:
        if s.get("workout_type") != "러닝":
            continue
        d = s["_date"]
        if start <= d <= today:
            daily[d] = daily.get(d, 0) + (s.get("distance_km") or 0)
    # 강도 스케일 (최대 거리 기반)
    max_km = max(daily.values()) if daily else 1
    # 7×weeks 그리드
    cell = 12
    gap = 2
    W = weeks * (cell + gap) + 30
    H = 7 * (cell + gap) + 30
    day_labels = ["월", "화", "수", "목", "금", "토", "일"]
    rects = []
    month_labels = []
    last_month = None
    for w in range(weeks):
        wk_start = start + timedelta(days=w * 7)
        x = 26 + w * (cell + gap)
        # 월 라벨
        for day_in_week in range(7):
            d = wk_start + timedelta(days=day_in_week)
            if d > today:
                continue
            if d.day <= 7 and d.month != last_month:
                month_labels.append(f'<text x="{x}" y="10" font-size="9" fill="#6e6e73">{d.month}월</text>')
                last_month = d.month
            y = 16 + day_in_week * (cell + gap)
            km = daily.get(d, 0)
            if km == 0:
                fill = "#ebedf0"
            else:
                intensity = min(1.0, km / max_km)
                # 5단계
                if intensity < 0.25:
                    fill = "#ffd4b8"
                elif intensity < 0.5:
                    fill = "#ff9e66"
                elif intensity < 0.75:
                    fill = "#ff6b35"
                else:
                    fill = "#d84315"
            rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{fill}"><title>{d.strftime("%Y-%m-%d")}: {km:.1f}km</title></rect>')
    # 요일 라벨
    dow_labels = "".join(
        f'<text x="2" y="{16 + i * (cell + gap) + cell - 2}" font-size="9" fill="#6e6e73">{lbl}</text>'
        for i, lbl in enumerate(day_labels)
    )
    svg = (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;max-height:{H}px;">'
        f'{"".join(month_labels)}{dow_labels}{"".join(rects)}'
        f'</svg>'
    )
    # 요일 통계
    dow_km = {i: 0 for i in range(7)}
    for d, km in daily.items():
        dow_km[d.weekday()] += km
    top_dow = max(dow_km, key=dow_km.get)
    rest_dow = min(dow_km, key=dow_km.get)
    total_runs = len(daily)
    legend = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:11px;color:var(--muted);">'
        f'<span>{weeks}주 · {total_runs}회 러닝</span>'
        f'<span style="display:flex;gap:3px;align-items:center;">'
        f'적음 <span style="width:10px;height:10px;background:#ebedf0;border-radius:2px;"></span>'
        f'<span style="width:10px;height:10px;background:#ffd4b8;border-radius:2px;"></span>'
        f'<span style="width:10px;height:10px;background:#ff9e66;border-radius:2px;"></span>'
        f'<span style="width:10px;height:10px;background:#ff6b35;border-radius:2px;"></span>'
        f'<span style="width:10px;height:10px;background:#d84315;border-radius:2px;"></span> 많음</span></div>'
        f'<div style="font-size:11px;color:var(--muted);margin-top:4px;">주 최다 {day_labels[top_dow]}요일 · 최소 {day_labels[rest_dow]}요일</div>'
    )
    run_days = set(daily.keys())
    total_days = (today - start).days + 1
    run_pct = int(round(len(run_days) / total_days * 100)) if total_days > 0 else 0
    # 연속 휴식 최장
    max_gap = 0; cur_gap = 0
    d = start
    while d <= today:
        if d in run_days:
            cur_gap = 0
        else:
            cur_gap += 1
            if cur_gap > max_gap: max_gap = cur_gap
        d += timedelta(days=1)
    if run_pct >= 50:
        note = coach_note("ok", f"형님 주 <b>{run_pct}%</b> 러닝 — 꾸준함 진짜 좋아요! 최대 연속 휴식도 <b>{max_gap}일</b>밖에 안 돼요.")
    elif max_gap >= 10:
        note = coach_note("warn", f"형님 중간에 <b>{max_gap}일 연속 쉰</b> 구간이 있어요. 루틴 회복이 먼저예요 — 짧게라도 <b>주 3회</b>부터 다시 시작해요.")
    elif run_pct >= 30:
        note = coach_note("tip", f"형님 주 <b>{run_pct}%</b> 러닝 — 주 3~4회 패턴이에요. 레이스 8주 전부턴 <b>주 4~5회</b>로 늘려야 해요.")
    else:
        note = coach_note("warn", f"형님 주 <b>{run_pct}%</b>는 빈도가 좀 부족해요. 마라톤 준비엔 <b>주 최소 3회</b>는 꼭 뛰어야 해요.")
    return svg + legend + note


def render_weekly_trimp_dotplot(all_sessions: list[dict], today: date, load: list[dict]) -> str:
    """이번 주 TRIMP 요일별 막대 + 지난 180일 일일 TRIMP dot plot."""
    monday = today - timedelta(days=today.weekday())
    # 이번 주 일별 TRIMP (load 기준)
    week_trimp = []
    d = monday
    while d <= monday + timedelta(days=6):
        r = None
        for row in load:
            if row["date"] == d.strftime("%Y-%m-%d"):
                r = row
                break
        week_trimp.append((d, r["trimp"] if r else 0))
        d += timedelta(days=1)
    week_total = sum(t for _, t in week_trimp)
    max_w = max((t for _, t in week_trimp), default=1) or 1

    # 180일 dot plot
    start_180 = today - timedelta(days=179)
    dots_data = []
    for row in load:
        d = datetime.strptime(row["date"], "%Y-%m-%d").date()
        if start_180 <= d <= today and row["trimp"] > 0:
            dots_data.append((d, row["trimp"]))
    max_d = max((t for _, t in dots_data), default=1) or 1

    # 렌더링
    labels = ["M", "T", "W", "T", "F", "S", "S"]
    W, H1 = 340, 90
    bar_w = (W - 40) / 7
    bars = ""
    for i, (d, t) in enumerate(week_trimp):
        x = 20 + i * bar_w
        h = (t / max_w) * (H1 - 30) if t > 0 else 0
        y = H1 - 20 - h
        color = "#ff6b35" if d == today else "#8e8e93"
        bars += f'<rect x="{x + bar_w*0.15:.1f}" y="{y:.1f}" width="{bar_w*0.55:.1f}" height="{max(h,1):.1f}" fill="{color}" rx="3"/>'
        if t > 0:
            bars += f'<text x="{x + bar_w*0.425:.1f}" y="{y-3:.1f}" font-size="9" fill="#1d1d1f" text-anchor="middle">{int(t)}</text>'
        bars += f'<text x="{x + bar_w*0.425:.1f}" y="{H1 - 6}" font-size="9" fill="#6e6e73" text-anchor="middle">{labels[i]}</text>'
    week_svg = f'<svg viewBox="0 0 {W} {H1}" style="width:100%;height:{H1}px;">{bars}</svg>'

    # Dot plot
    H2 = 100
    dots = ""
    total_days = 180
    for d, t in dots_data:
        days_ago = (today - d).days
        x = 20 + (1 - days_ago / total_days) * (W - 40)
        y = 10 + (1 - t / max_d) * (H2 - 30)
        opacity = 0.7
        color = "#ff6b35" if d == today else "#ffab85"
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}" opacity="{opacity}"/>'
    # 오늘 마커
    dots += f'<line x1="{W - 20}" y1="5" x2="{W - 20}" y2="{H2 - 15}" stroke="#ff3b30" stroke-width="1.5"/>'
    dots += f'<polygon points="{W-24},5 {W-16},5 {W-20},11" fill="#ff3b30"/>'
    # 월 라벨
    month_labels = ""
    for months_ago in [5, 3, 1, 0]:
        ref = today - timedelta(days=months_ago * 30)
        days_ago_ref = (today - ref).days
        x = 20 + (1 - days_ago_ref / total_days) * (W - 40)
        month_labels += f'<text x="{x:.1f}" y="{H2 - 2}" font-size="9" fill="#6e6e73" text-anchor="middle">{ref.strftime("%m월")}</text>'
    dot_svg = f'<svg viewBox="0 0 {W} {H2}" style="width:100%;height:{H2}px;">{dots}{month_labels}</svg>'

    caption = (
        f'<div style="font-size:18px;font-weight:700;color:#ff6b35;margin-bottom:6px;">{int(week_total)} '
        f'<span style="font-size:11px;color:var(--muted);font-weight:500;">이번 주 TRIMP</span></div>'
    )
    subtitle = f'<div style="font-size:11px;color:var(--muted);margin:10px 0 2px;">지난 6개월 일일 TRIMP 분포</div>'
    # 6개월 평균 주간 TRIMP
    if dots_data:
        avg_daily = sum(t for _, t in dots_data) / 180
        avg_weekly = avg_daily * 7
    else:
        avg_weekly = 0
    if avg_weekly == 0:
        note = coach_note("warn", "형님 아직 6개월 TRIMP 데이터가 부족해요. 꾸준히 기록부터 쌓아봐요.")
    elif week_total >= avg_weekly * 1.5:
        note = coach_note("warn", f"형님 이번 주 TRIMP <b>{int(week_total)}</b> — 평균보다 <b>+50% 이상</b>이에요. 주말엔 완전 휴식 들어가요.")
    elif week_total >= avg_weekly * 1.1:
        note = coach_note("ok", f"형님 이번 주 <b>{int(week_total)}</b> vs 평균 <b>{int(avg_weekly)}</b> — 건강한 상승이에요!")
    elif week_total <= avg_weekly * 0.5:
        note = coach_note("tip", f"형님 이번 주 <b>{int(week_total)}</b>은 평균 절반 이하예요. 컨디션 괜찮으면 <b>한 세션 더</b> 넣어봐요.")
    else:
        note = coach_note("ok", f"형님 이번 주 <b>{int(week_total)}</b> — 평소 패턴 잘 유지하고 있어요.")
    return caption + week_svg + subtitle + dot_svg + note


def render_focus_7d_card(today: date, sessions: list[dict]) -> str:
    """Daily용 7일 TL Focus (focus_28d의 7일 버전)."""
    start = today - timedelta(days=6)
    window = [s for s in sessions if start <= s["_date"] <= today and s.get("hr_zones")]
    totals = {"low": 0, "high": 0, "anaerobic": 0}
    for s in window:
        z = s["hr_zones"]
        totals["low"] += (z.get("Z0", 0) + z.get("Z1", 0) + z.get("Z2", 0)) / 60
        totals["high"] += z.get("Z3", 0) / 60 + z.get("Z4", 0) / 60
        totals["anaerobic"] += z.get("Z5", 0) / 60
    total = sum(totals.values())
    if total == 0:
        return '<div style="color:var(--muted);font-size:12px;">최근 7일 심박존 데이터 없음.</div>'
    pct_low = int(round(totals["low"] / total * 100))
    pct_high = int(round(totals["high"] / total * 100))
    pct_ana = 100 - pct_low - pct_high
    # HealthFit 스타일: 좌측 분 수치 + 색막대
    rows = [
        ("무산소", pct_ana, int(totals["anaerobic"]), "#af52de"),
        ("고유산소", pct_high, int(totals["high"]), "#ff9500"),
        ("저유산소", pct_low, int(totals["low"]), "#5ac8fa"),
    ]
    body = ""
    for label, pct, mins, color in rows:
        body += (
            f'<div style="display:flex;align-items:center;gap:8px;margin:8px 0;">'
            f'<div style="width:30px;font-size:11px;color:#6e6e73;text-align:right;font-weight:600;">{mins}</div>'
            f'<div style="flex:1;">'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px;">'
            f'<b>{label}</b><span><b>{pct}%</b></span></div>'
            f'<div style="height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">'
            f'<div style="height:100%;width:{pct}%;background:{color};border-radius:4px;"></div></div>'
            f'</div></div>'
        )
    body += f'<div style="font-size:10px;color:var(--muted);margin-top:8px;">훈련법: 최대 심박수 % 기준 · 최근 7일</div>'
    if pct_low >= 75:
        body += coach_note("ok", f"형님 저유산소 <b>{pct_low}%</b> — 폴라리즈드 구조 훌륭해요! 장거리 베이스 잘 쌓이는 중이에요.")
    elif pct_ana >= 20:
        body += coach_note("warn", f"형님 무산소가 <b>{pct_ana}%</b>나 돼요 — 고강도 과다예요. 내일은 <b>회복 조깅 30분, Z2만</b>으로 가요.")
    elif pct_low >= 60:
        body += coach_note("tip", f"형님 저유산소 <b>{pct_low}%</b> — 권장 80%까진 살짝 부족해요. 다음 1~2회는 <b>심박 145 이하</b>로 편하게 가요.")
    else:
        body += coach_note("warn", f"형님 저유산소 <b>{pct_low}%</b> — 기초 체력 구간이 부족해요. 주 2회는 <b>대화 가능한 페이스</b>로만 뛰어요.")
    return body
