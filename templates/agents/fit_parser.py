#!/usr/bin/env python3
"""
FIT 파일 파서 — HealthFit/Garmin FIT 파일 한 개를 running_log.jsonl 스키마에 맞는
dict로 변환한다.

사용법:
    from fit_parser import parse_fit
    data = parse_fit("/path/to/workout.fit")
    # data["source_app"] = "healthfit_fit"
    # data["workout_type"] = "러닝" / "사이클링"

확장(2026-04-18):
    - 1Hz record 스트림 기반 HRZ(Z0-Z5), TRIMP(Banister), METs 계산
    - 파워 존, 러닝 폼(GCT/VO/VR), 보폭·스트라이드, GPS 경로, 고도 프로파일
    - 습도, 랩별 상세, 케이던스 최적존
    - 프로필 오버라이드: ~/.claude/config/running_profile.json
        { "hr_max": 185, "hr_rest": 55, "ftp_power": 250 }

iCloud placeholder 파일 처리:
    - 읽기 실패 시 brctl download로 다운로드 트리거 후 최대 90초 polling
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))

SPORT_TO_WORKOUT = {
    "running": "러닝",
    "cycling": "사이클링",
    "walking": "걷기",
    "hiking": "등산",
    "swimming": "수영",
}

# 기본 프로필 (형님 2026-04 기준 추정치 — running_profile.json이 있으면 덮어씀)
DEFAULT_PROFILE = {
    "hr_max": 185,      # 최대 심박
    "hr_rest": 55,      # 안정 심박
    "ftp_power": 250,   # Functional Threshold Power (러닝 파워, 추후 측정)
    "sex": "M",         # Banister 계수용 (M=1.92, F=1.67)
}

PROFILE_PATH = Path.home() / ".claude/config/running_profile.json"


def load_profile() -> dict:
    """사용자 프로필 로드 (MHR/HRrest/FTP 등)."""
    p = dict(DEFAULT_PROFILE)
    if PROFILE_PATH.exists():
        try:
            p.update(json.loads(PROFILE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return p


def _materialize_icloud(path: str, timeout_sec: int = 90) -> bytes:
    """iCloud placeholder 파일을 실제로 읽을 수 있을 때까지 기다린 뒤 bytes 반환"""
    try:
        return open(path, "rb").read()
    except OSError:
        pass

    subprocess.run(["brctl", "download", path], capture_output=True, timeout=10)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            return open(path, "rb").read()
        except OSError:
            time.sleep(2)
    raise TimeoutError(f"iCloud 파일 다운로드 실패 (timeout {timeout_sec}s): {path}")


def _fmt_pace(duration_sec: float, distance_km: float) -> str | None:
    if not distance_km or distance_km <= 0:
        return None
    pace = duration_sec / distance_km
    m = int(pace // 60)
    s = int(round(pace - m * 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}'{s:02d}\""


def _semicircles_to_deg(v: int | None) -> float | None:
    if v is None:
        return None
    return v * (180.0 / 2**31)


# ───────── 계산 함수 ─────────

def calc_hr_zones(hr_stream: list[tuple[float, int]], hr_max: int) -> dict:
    """1Hz HR 스트림 → Z0-Z5 시간 분포 (초 단위).

    Args:
        hr_stream: [(dt_sec, hr_bpm), ...] — 인접 timestamp 간격 + hr
        hr_max: 최대 심박
    Returns:
        {"Z0": sec, "Z1": sec, ..., "Z5": sec, "total": sec}
    """
    zones = {"Z0": 0.0, "Z1": 0.0, "Z2": 0.0, "Z3": 0.0, "Z4": 0.0, "Z5": 0.0}
    bounds = [0.50, 0.60, 0.70, 0.80, 0.90]  # % of HRmax
    thresholds = [hr_max * b for b in bounds]
    for dt, hr in hr_stream:
        if hr is None or hr <= 0:
            continue
        if hr < thresholds[0]:
            zones["Z0"] += dt
        elif hr < thresholds[1]:
            zones["Z1"] += dt
        elif hr < thresholds[2]:
            zones["Z2"] += dt
        elif hr < thresholds[3]:
            zones["Z3"] += dt
        elif hr < thresholds[4]:
            zones["Z4"] += dt
        else:
            zones["Z5"] += dt
    total = sum(zones.values())
    result = {k: int(round(v)) for k, v in zones.items()}
    result["total"] = int(round(total))
    return result


def calc_trimp_banister(hr_stream: list[tuple[float, int]], hr_max: int, hr_rest: int, sex: str = "M") -> float:
    """Banister TRIMP: Σ (Δt_min × HRratio × 0.64 × e^(1.92 × HRratio)).
    남성 계수 1.92, 여성 1.67.
    """
    k = 1.92 if sex == "M" else 1.67
    total = 0.0
    denom = max(hr_max - hr_rest, 1)
    for dt, hr in hr_stream:
        if hr is None or hr <= 0:
            continue
        ratio = max(0.0, min(1.0, (hr - hr_rest) / denom))
        dt_min = dt / 60.0
        total += dt_min * ratio * 0.64 * math.exp(k * ratio)
    return round(total, 1)


def calc_mets(avg_speed_ms: float | None) -> float | None:
    """ACSM 러닝 METs = (0.2 × velocity_m/min + 3.5) / 3.5."""
    if not avg_speed_ms or avg_speed_ms <= 0:
        return None
    v_m_min = avg_speed_ms * 60.0
    return round((0.2 * v_m_min + 3.5) / 3.5, 2)


def calc_power_zones(power_stream: list[tuple[float, int]], ftp: int) -> dict:
    """러닝 파워 존 (Z1<55%, Z2 55-75, Z3 75-90, Z4 90-105, Z5 105-120, Z6 120-150, Z7>150)."""
    zones = {f"Z{i}": 0.0 for i in range(1, 8)}
    bounds = [0.55, 0.75, 0.90, 1.05, 1.20, 1.50]
    ths = [ftp * b for b in bounds]
    for dt, p in power_stream:
        if p is None or p <= 0:
            continue
        if p < ths[0]:
            zones["Z1"] += dt
        elif p < ths[1]:
            zones["Z2"] += dt
        elif p < ths[2]:
            zones["Z3"] += dt
        elif p < ths[3]:
            zones["Z4"] += dt
        elif p < ths[4]:
            zones["Z5"] += dt
        elif p < ths[5]:
            zones["Z6"] += dt
        else:
            zones["Z7"] += dt
    total = sum(zones.values())
    result = {k: int(round(v)) for k, v in zones.items()}
    result["total"] = int(round(total))
    return result


def calc_cadence_zones(cad_stream: list[tuple[float, float]]) -> dict:
    """케이던스 5구간: <160 / 160-170 / 170-180 / 180-190 / ≥190 spm."""
    zones = {"C1_lt160": 0.0, "C2_160_170": 0.0, "C3_170_180": 0.0, "C4_180_190": 0.0, "C5_gte190": 0.0}
    for dt, c in cad_stream:
        if c is None or c <= 0:
            continue
        if c < 160:
            zones["C1_lt160"] += dt
        elif c < 170:
            zones["C2_160_170"] += dt
        elif c < 180:
            zones["C3_170_180"] += dt
        elif c < 190:
            zones["C4_180_190"] += dt
        else:
            zones["C5_gte190"] += dt
    return {k: int(round(v)) for k, v in zones.items()}


def calc_pace_histogram(speed_stream: list[tuple[float, float]]) -> dict:
    """페이스 구간별 시간 분포 (sec/km 기준).
    <4:30 / 4:30-5:00 / 5:00-5:30 / 5:30-6:00 / 6:00-6:30 / 6:30-7:00 / ≥7:00
    """
    buckets = ["lt430", "430_500", "500_530", "530_600", "600_630", "630_700", "gte700"]
    dist = {k: 0.0 for k in buckets}
    bounds_sec = [270, 300, 330, 360, 390, 420]  # 4:30, 5:00, ...
    for dt, s_ms in speed_stream:
        if s_ms is None or s_ms <= 0.1:
            continue
        pace_sec_km = 1000.0 / s_ms
        if pace_sec_km < bounds_sec[0]:
            dist["lt430"] += dt
        elif pace_sec_km < bounds_sec[1]:
            dist["430_500"] += dt
        elif pace_sec_km < bounds_sec[2]:
            dist["500_530"] += dt
        elif pace_sec_km < bounds_sec[3]:
            dist["530_600"] += dt
        elif pace_sec_km < bounds_sec[4]:
            dist["600_630"] += dt
        elif pace_sec_km < bounds_sec[5]:
            dist["630_700"] += dt
        else:
            dist["gte700"] += dt
    return {k: int(round(v)) for k, v in dist.items()}


def calc_hr_drift(hr_stream: list[tuple[float, int]]) -> float | None:
    """심박 드리프트: 전반 HR 평균 vs 후반 HR 평균 (% 증가)."""
    hrs = [hr for _, hr in hr_stream if hr and hr > 0]
    if len(hrs) < 10:
        return None
    half = len(hrs) // 2
    first = sum(hrs[:half]) / half
    second = sum(hrs[half:]) / (len(hrs) - half)
    if first <= 0:
        return None
    return round((second - first) / first * 100, 1)


# ───────── 메인 파서 ─────────

def parse_fit(fit_path: str) -> dict[str, Any]:
    """FIT 파일 → JSONL-호환 dict (확장 필드 포함)"""
    from fitparse import FitFile

    fit_path = os.fspath(fit_path)
    raw = _materialize_icloud(fit_path)

    import io
    ff = FitFile(io.BytesIO(raw))

    sport_msg = None
    session = None
    laps: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for msg in ff.get_messages():
        if msg.name == "session":
            session = {f.name: f.value for f in msg if f.value is not None}
        elif msg.name == "sport" and sport_msg is None:
            sport_msg = {f.name: f.value for f in msg if f.value is not None}
        elif msg.name == "lap":
            laps.append({f.name: f.value for f in msg if f.value is not None})
        elif msg.name == "record":
            records.append({f.name: f.value for f in msg if f.value is not None})

    if not session:
        raise ValueError(f"FIT에 session 메시지 없음: {fit_path}")

    sport = session.get("sport") or (sport_msg.get("sport") if sport_msg else "unknown")
    sport = str(sport).lower()
    workout_type = SPORT_TO_WORKOUT.get(sport, sport)

    start_utc = session.get("start_time")
    if start_utc is None:
        raise ValueError("session.start_time 없음")
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    start_kst = start_utc.astimezone(KST)

    total_distance_m = session.get("total_distance", 0) or 0
    distance_km = round(total_distance_m / 1000, 2)
    duration_sec = int(round(session.get("total_timer_time", session.get("total_elapsed_time", 0)) or 0))
    elapsed_sec = int(round(session.get("total_elapsed_time", duration_sec) or duration_sec))

    avg_hr = session.get("avg_heart_rate")
    avg_speed_ms = session.get("avg_speed") or session.get("enhanced_avg_speed")
    avg_speed_kmh = round(avg_speed_ms * 3.6, 2) if avg_speed_ms else None
    max_speed_ms = session.get("max_speed") or session.get("enhanced_max_speed")

    if sport == "running":
        avg_run_cadence = session.get("avg_running_cadence")
        cadence = int(round(avg_run_cadence * 2)) if avg_run_cadence else None
    else:
        cadence = session.get("avg_cadence")
        cadence = int(round(cadence)) if cadence else None

    pace_per_km = _fmt_pace(duration_sec, distance_km) if sport == "running" and distance_km > 0 else None

    # ─── 1Hz 스트림 추출 ───
    profile = load_profile()
    hr_stream: list[tuple[float, int]] = []
    power_stream: list[tuple[float, int]] = []
    cad_stream: list[tuple[float, float]] = []  # spm (fractional 포함)
    speed_stream: list[tuple[float, float]] = []  # m/s
    gps_points: list[tuple[float, float]] = []  # (lat, lon) deg
    altitude_profile: list[tuple[float, float]] = []  # (distance_km, altitude_m)
    form_samples = {"stance_time": [], "vertical_oscillation": [], "vertical_ratio": [], "step_length": []}

    prev_ts = None
    for rec in records:
        ts = rec.get("timestamp")
        if ts is None:
            continue
        if prev_ts is None:
            dt = 1.0
        else:
            dt = (ts - prev_ts).total_seconds()
            if dt <= 0 or dt > 10:
                dt = 1.0
        prev_ts = ts

        if (hr := rec.get("heart_rate")) is not None:
            hr_stream.append((dt, int(hr)))
        if (pw := rec.get("power")) is not None:
            power_stream.append((dt, int(pw)))
        if (cd := rec.get("cadence")) is not None:
            frac = rec.get("fractional_cadence") or 0
            spm = (cd + frac) * 2  # 러닝: strides/min × 2
            cad_stream.append((dt, spm))
        if (sp := rec.get("enhanced_speed") or rec.get("speed")) is not None:
            speed_stream.append((dt, sp))
        lat = _semicircles_to_deg(rec.get("position_lat"))
        lon = _semicircles_to_deg(rec.get("position_long"))
        if lat is not None and lon is not None:
            gps_points.append((lat, lon))
        alt = rec.get("enhanced_altitude") or rec.get("altitude")
        dist = rec.get("distance")
        if alt is not None and dist is not None:
            altitude_profile.append((dist / 1000.0, float(alt)))
        for k in form_samples:
            if (v := rec.get(k)) is not None:
                form_samples[k].append(v)

    # ─── 계산 ───
    hr_max = profile["hr_max"]
    hr_rest = profile["hr_rest"]
    ftp = profile["ftp_power"]
    sex = profile["sex"]

    zones = calc_hr_zones(hr_stream, hr_max) if hr_stream else None
    trimp = calc_trimp_banister(hr_stream, hr_max, hr_rest, sex) if hr_stream else None
    mets = calc_mets(avg_speed_ms)
    power_zones = calc_power_zones(power_stream, ftp) if power_stream else None
    cadence_zones = calc_cadence_zones(cad_stream) if cad_stream else None
    pace_hist = calc_pace_histogram(speed_stream) if speed_stream else None
    hr_drift = calc_hr_drift(hr_stream) if hr_stream else None

    # ─── Lap 상세 ───
    splits: list[dict[str, Any]] = []
    laps_detail: list[dict[str, Any]] = []
    for lap in laps:
        lap_dist_km = round((lap.get("total_distance") or 0) / 1000, 3)
        lap_dur_sec = int(round(lap.get("total_timer_time") or lap.get("total_elapsed_time") or 0))
        lap_entry: dict[str, Any] = {
            "distance_km": lap_dist_km,
            "duration_sec": lap_dur_sec,
            "heart_rate": lap.get("avg_heart_rate"),
        }
        if sport == "running" and lap_dist_km > 0:
            lap_entry["pace_per_km"] = _fmt_pace(lap_dur_sec, lap_dist_km)
        if (lap_speed := lap.get("avg_speed") or lap.get("enhanced_avg_speed")):
            lap_entry["avg_speed_kmh"] = round(lap_speed * 3.6, 2)
        if (lap_cad := lap.get("avg_running_cadence")):
            lap_entry["cadence"] = int(round(lap_cad * 2))
        elif (lap_cad := lap.get("avg_cadence")):
            lap_entry["cadence"] = int(round(lap_cad))
        splits.append(lap_entry)

        detail = dict(lap_entry)
        for key in ("avg_power", "max_power", "avg_stance_time", "avg_vertical_oscillation",
                    "avg_vertical_ratio", "avg_step_length", "total_strides",
                    "max_heart_rate", "total_ascent", "total_descent",
                    "avg_temperature", "total_calories"):
            if (v := lap.get(key)) is not None:
                detail[key] = v
        laps_detail.append(detail)

    # ─── 러닝 폼 / 파워 / 환경 요약 ───
    running_details = {}
    if sport == "running":
        for key in ("avg_power", "max_power", "avg_stance_time", "avg_vertical_oscillation",
                    "avg_step_length", "avg_vertical_ratio", "total_strides"):
            if key in session:
                running_details[key] = session[key]

    # 습도 (FIT 확장 필드: session.humidity 또는 unknown_xx)
    humidity = None
    for key in ("total_humidity", "humidity", "avg_humidity", "WEATHER_HUMIDITY"):
        if key in session:
            humidity = session[key]
            # 일부 FIT은 ×100 저장
            if isinstance(humidity, (int, float)) and humidity > 100:
                humidity = humidity / 100
            break

    fit_file = Path(fit_path)
    result = {
        "date": start_kst.strftime("%Y-%m-%d"),
        "time": start_kst.strftime("%H:%M"),
        "weekday": ["월", "화", "수", "목", "금", "토", "일"][start_kst.weekday()] + "요일",
        "workout_type": workout_type,
        "distance_km": distance_km,
        "duration_sec": duration_sec,
        "elapsed_sec": elapsed_sec,
        "pace_per_km": pace_per_km,
        "avg_speed_kmh": avg_speed_kmh,
        "max_speed_kmh": round(max_speed_ms * 3.6, 2) if max_speed_ms else None,
        "elevation_m": int(round(session.get("total_ascent") or 0)),
        "elevation_descent_m": int(round(session.get("total_descent") or 0)),
        "min_altitude_m": round(session["min_altitude"], 1) if session.get("min_altitude") is not None else None,
        "max_altitude_m": round(session["max_altitude"], 1) if session.get("max_altitude") is not None else None,
        "heart_rate_avg": int(round(avg_hr)) if avg_hr else None,
        "heart_rate_max": int(round(session["max_heart_rate"])) if session.get("max_heart_rate") else None,
        "heart_rate_min": int(round(session["min_heart_rate"])) if session.get("min_heart_rate") else None,
        "calories": int(round(session.get("total_calories") or 0)) or None,
        "cadence": cadence,
        "max_cadence": int(round(session["max_running_cadence"] * 2)) if session.get("max_running_cadence") else None,
        "temperature_c": session.get("avg_temperature"),
        "max_temperature_c": session.get("max_temperature"),
        "humidity_pct": humidity,
        "start_lat": _semicircles_to_deg(session.get("nec_lat") or session.get("start_position_lat")),
        "start_lon": _semicircles_to_deg(session.get("nec_long") or session.get("start_position_long")),
        "splits": splits,
        "laps_detail": laps_detail,
        # 계산 결과
        "trimp": trimp,
        "mets": mets,
        "hr_zones": zones,
        "power_zones": power_zones,
        "cadence_zones": cadence_zones,
        "pace_histogram": pace_hist,
        "hr_drift_pct": hr_drift,
        # 경량 스트림 (GPS·고도·폼 샘플링)
        "gps_points": gps_points[::max(1, len(gps_points) // 300)] if gps_points else [],  # 최대 ~300개
        "altitude_profile": altitude_profile[::max(1, len(altitude_profile) // 200)] if altitude_profile else [],
        "form_summary": {
            k: (round(sum(v) / len(v), 2) if v else None) for k, v in form_samples.items()
        } if any(form_samples.values()) else None,
        # 프로필 snapshot (재계산 재현용)
        "profile_used": {"hr_max": hr_max, "hr_rest": hr_rest, "ftp_power": ftp, "sex": sex},
        "source_app": "healthfit_fit",
        "source_file": fit_file.name,
        "screenshot_uuids": [f"fit:{fit_file.name}"],
        "logged_at": datetime.now(KST).isoformat(timespec="seconds"),
    }
    if running_details:
        result["running_details"] = running_details
    return result


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 fit_parser.py <FIT_PATH> [--json]", file=sys.stderr)
        sys.exit(1)

    fit_path = sys.argv[1]
    as_json = "--json" in sys.argv[2:]

    try:
        data = parse_fit(fit_path)
    except Exception as e:
        print(f"❌ 파싱 실패: {e}", file=sys.stderr)
        sys.exit(2)

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"✅ {data['workout_type']} {data['date']} {data['time']} ({data['weekday']})")
        print(f"   거리: {data['distance_km']} km · 고도 +{data['elevation_m']}m")
        print(f"   시간: {data['duration_sec']}초 ({data.get('pace_per_km') or data.get('avg_speed_kmh','-')}/km)")
        if data.get("heart_rate_avg"):
            print(f"   심박: {data['heart_rate_avg']}/{data.get('heart_rate_max')} bpm · 드리프트 {data.get('hr_drift_pct','-')}%")
        if data.get("trimp") is not None:
            print(f"   TRIMP: {data['trimp']} · METs: {data.get('mets','-')}")
        if data.get("hr_zones"):
            z = data["hr_zones"]
            print(f"   HRZ: Z0={z['Z0']}s Z1={z['Z1']}s Z2={z['Z2']}s Z3={z['Z3']}s Z4={z['Z4']}s Z5={z['Z5']}s")
        if data.get("power_zones"):
            print(f"   Power zones: {data['power_zones']}")
        if data.get("running_details"):
            rd = data["running_details"]
            print(f"   폼: GCT {rd.get('avg_stance_time','-')}ms · VO {rd.get('avg_vertical_oscillation','-')}mm · VR {rd.get('avg_vertical_ratio','-')}%")
        print(f"   Lap: {len(data['splits'])}개 · GPS pts: {len(data.get('gps_points', []))} · Alt pts: {len(data.get('altitude_profile', []))}")


if __name__ == "__main__":
    main()
