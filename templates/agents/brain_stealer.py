#!/usr/bin/env python3
"""
뇌 훔치기 파이프라인 — 블로그 전체 크롤링 + 구조 추출 + 사고 지도 자동 생성.

사용법:
    python3 brain_stealer.py [blogId] [작가명]   — 새 작가 등록 + 시작
    python3 brain_stealer.py --continue           — 미완료 작업 이어서
    python3 brain_stealer.py --status              — 전체 상태 확인

조건:
    - 밤 21:00~새벽 06:00만 작업 (Phase 0, 1)
    - Phase 2, 3은 시간 무관 (Opus 1회씩, 빠름)
    - 중단 시 진행 상태 저장 → 다음 날 이어서
    - launchd로 매일 21:00 자동 시작 (미완료 작업 있을 때만)
"""

import sys
import os
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# ======== 경로 ========
HOME = Path.home()
VAULT = HOME / "Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"
TARGETS_FILE = HOME / ".claude/brain_targets.json"
AGENTS_DIR = HOME / "alice-github/harness-engineering-guide/templates/agents"
SCRIPTS_DIR = HOME / ".claude/scripts"
LOG_DIR = HOME / ".claude/logs"

sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

# 텔레그램 토큰은 ~/.claude/.env에서 자동 로드 (telegram_sender.send_telegram 사용)


# ======== 유틸리티 ========

def is_work_hours(settings: dict = None):
    """작업 시간 체크 — settings의 work_hours_start/end 사용 (기본 21~6)"""
    h = datetime.now().hour
    start = (settings or {}).get("work_hours_start", 21)
    end = (settings or {}).get("work_hours_end", 6)
    if start > end:
        return h >= start or h < end
    return start <= h < end


def log(msg, log_file=None):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if log_file:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + "\n")


def load_targets():
    if not TARGETS_FILE.exists():
        default = {
            "targets": [],
            "settings": {
                "work_hours_start": 21,
                "work_hours_end": 6,
                "phase1_batch_size": 5,
                "phase1_parallel": 2,
                "phase1_model": "sonnet",
                "daily_analysis_model": "sonnet",
                "synthesis_model": "opus",
                "map_model": "opus",
                "monthly_delta_model": "opus",
                "insight_model": "sonnet",
                "vault_base": "해상도 프로젝트",
            },
        }
        save_targets(default)
        return default
    return json.loads(TARGETS_FILE.read_text(encoding='utf-8'))


def save_targets(data):
    TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def get_target(data, blog_id):
    for t in data["targets"]:
        if t["blogId"] == blog_id:
            return t
    return None


def get_dirs(target):
    base = VAULT / target["base_dir"]
    map_dir = VAULT / "해상도 프로젝트" / "00_사고 지도"
    name = target["name"]
    return {
        "base": base,
        "original": base / "원본",
        "extracted": base / "extracted_notes.json",
        "patterns": base / "aggregated_patterns.json",
        "map_dir": map_dir,
        "map": map_dir / f"{name}.md",
    }


def send_telegram(msg):
    try:
        from telegram_sender import send_telegram as _send
        _send(msg)
    except Exception:
        pass


# ======== Phase 0: 전체 크롤링 (토큰 0) ========

def phase0(target, data, lf):
    dirs = get_dirs(target)
    settings = data.get("settings", {})
    dirs["original"].mkdir(parents=True, exist_ok=True)

    source_type = target.get("source_type", "blog")
    log(f"Phase 0: {target['name']} 자료 수집 (source_type={source_type})", lf)

    # source_type 분기: blog = 네이버 블로그 스크래퍼, curated = 작가 사고 자료 수집기
    if source_type == "curated":
        cmd = [
            "python3", str(SCRIPTS_DIR / "thinker_collector.py"),
            target["blogId"],
        ]
    else:
        # 기본: 네이버 블로그
        cmd = [
            "python3", str(AGENTS_DIR / "naver_blog_scraper.py"),
            target["blogId"], str(dirs["original"]),
            "--author", target["name"],
        ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    while process.poll() is None:
        if not is_work_hours(settings):
            process.terminate()
            process.wait(timeout=10)
            log(f"  작업 시간 종료. 내일 이어서.", lf)
            save_targets(data)
            return False
        time.sleep(30)

    # 결과
    saved = len(list(dirs["original"].glob("*.md")))
    target["total_posts"] = saved
    log(f"  크롤링 완료: {saved}개", lf)

    target["phase"] = "phase1"
    save_targets(data)
    return True


# ======== Phase 1: 구조 추출 (Haiku 배치) ========

def phase1(target, data, lf):
    dirs = get_dirs(target)
    settings = data.get("settings", {})

    log(f"Phase 1: {target['name']} 구조 추출 (Sonnet 배치)", lf)

    cmd = [
        "python3", str(AGENTS_DIR / "deep_archive_extractor_batch.py"),
        str(dirs["original"]),
        str(dirs["extracted"]),
        "--parallel", str(settings.get("phase1_parallel", 2)),
        "--batch", str(settings.get("phase1_batch_size", 5)),
        "--model", settings.get("phase1_model", "haiku"),
    ]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    while process.poll() is None:
        if not is_work_hours(settings):
            process.terminate()
            process.wait(timeout=10)
            log(f"  작업 시간 종료. 내일 이어서.", lf)
            save_targets(data)
            return False
        time.sleep(60)

    # 결과 확인
    rc = process.returncode
    if dirs["extracted"].exists():
        extracted = json.loads(dirs["extracted"].read_text(encoding='utf-8'))
        target["extracted_count"] = len(extracted)
        log(f"  추출 결과: {len(extracted)}개 / 총 {target.get('total_posts', 0)}개", lf)

    # exit code 1 = 토큰 만료 등 조기 중단
    if rc != 0:
        log(f"  ✖ Phase 1 중단 (returncode={rc}). phase1 유지. 다음 재개에서 이어서.", lf)
        send_telegram(f"⚠️ Phase 1 중단 ({target['name']})\n추출: {target.get('extracted_count', 0)}/{target.get('total_posts', 0)}\n토큰 만료 가능성. 재개 필요.")
        save_targets(data)
        return False

    # 추출 수가 전체의 95% 미만이면 완료로 간주 안 함
    total = target.get("total_posts", 0)
    done = target.get("extracted_count", 0)
    if total > 0 and done < total * 0.95:
        log(f"  ⚠ 추출 부족 ({done}/{total}, {done*100//max(total,1)}%). phase1 유지.", lf)
        save_targets(data)
        return False

    log(f"  추출 완료: {done}개", lf)
    target["phase"] = "phase2"
    save_targets(data)
    return True


# ======== Phase 2: 합성 (Opus 1회) ========

def phase2(target, data, lf):
    dirs = get_dirs(target)
    settings = data.get("settings", {})
    model = settings.get("synthesis_model", "opus")
    log(f"Phase 2: {target['name']} 합성 ({model})", lf)

    cmd = [
        "python3", str(AGENTS_DIR / "phase2_aggregator.py"),
        str(dirs["extracted"]),
        str(dirs["patterns"]),
        "--author", target["name"],
        "--model", model,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

    if result.returncode != 0:
        log(f"  Phase 2 실패: {result.stderr[:300]}", lf)
        send_telegram(f"⚠️ Phase 2 실패 ({target['name']})\n{result.stderr[:200]}")
        return False

    log(f"  합성 완료", lf)
    target["phase"] = "phase3"
    save_targets(data)
    return True


# ======== Phase 3: 사고 지도 (Opus 1회) ========

def phase3(target, data, lf):
    dirs = get_dirs(target)
    settings = data.get("settings", {})
    model = settings.get("map_model", "opus")
    dirs["map_dir"].mkdir(parents=True, exist_ok=True)
    log(f"Phase 3: {target['name']} 사고 지도 ({model})", lf)

    cmd = [
        "python3", str(AGENTS_DIR / "phase3_map_builder.py"),
        str(dirs["patterns"]),
        str(dirs["map"]),
        target["blogId"],
        "--model", model,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)

    if result.returncode != 0:
        log(f"  Phase 3 실패: {result.stderr[:300]}", lf)
        send_telegram(f"⚠️ Phase 3 실패 ({target['name']})\n{result.stderr[:200]}")
        return False

    log(f"  사고 지도 완료: {dirs['map'].name}", lf)
    target["phase"] = "완료"
    target["status"] = "완료"
    save_targets(data)
    return True


# ======== 파이프라인 실행 ========

def _sync_phase_from_disk(target, lf):
    """extracted_notes.json 실제 상태로 target 보정 — extractor가 외부에서 돌았을 때 phase1→phase2 승격"""
    dirs = get_dirs(target)
    if not dirs["extracted"].exists():
        return
    try:
        extracted = json.loads(dirs["extracted"].read_text(encoding='utf-8'))
        count = len(extracted)
        old_count = target.get("extracted_count", 0)
        if count != old_count:
            target["extracted_count"] = count
            log(f"  [sync] extracted_count 동기화: {old_count} → {count}", lf)
        total = target.get("total_posts", 0)
        if total > 0 and count >= total * 0.95 and target.get("phase") in ("phase0", "phase1"):
            log(f"  [sync] 95% 도달 ({count}/{total}) → phase=phase2 승격", lf)
            target["phase"] = "phase2"
    except Exception as e:
        log(f"  [sync] 실패: {e}", lf)


def run_pipeline(blog_id, lf):
    data = load_targets()
    target = get_target(data, blog_id)
    if not target:
        log(f"대상 없음: {blog_id}", lf)
        return

    # 실제 디스크 상태로 target 보정 (외부 실행 결과 반영)
    _sync_phase_from_disk(target, lf)
    save_targets(data)

    current = target.get("phase", "phase0")

    phases = [
        ("phase0", phase0, True),   # (이름, 함수, 시간 제한?)
        ("phase1", phase1, True),
        ("phase2", phase2, False),  # Opus 1회라서 시간 무관
        ("phase3", phase3, False),
    ]

    for name, func, time_limited in phases:
        # 이미 완료된 단계 스킵
        phase_order = ["phase0", "phase1", "phase2", "phase3", "완료"]
        if phase_order.index(name) < phase_order.index(current):
            continue

        # 시간 제한 단계는 작업 시간 체크
        settings = data.get("settings", {})
        if time_limited and not is_work_hours(settings):
            start = settings.get("work_hours_start", 21)
            end = settings.get("work_hours_end", 6)
            log(f"작업 시간 아님 ({start:02d}:00~{end:02d}:00). 다음 실행에 이어서.", lf)
            return

        log(f"{'='*50}", lf)
        success = func(target, data, lf)
        if not success:
            return  # 시간 부족 또는 실패

    # 완료
    log(f"{'='*50}", lf)
    log(f"🎉 {target['name']} 뇌 훔치기 완료!", lf)
    send_telegram(
        f"🧠 뇌 훔치기 완료!\n\n"
        f"작가: {target['name']}\n"
        f"블로그: {target['blogId']}\n"
        f"총 글: {target.get('total_posts', '?')}개\n"
        f"추출: {target.get('extracted_count', '?')}개\n\n"
        f"📁 해상도 프로젝트/00_사고 지도/{target['name']}.md"
    )


# ======== 메인 ========

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lf = LOG_DIR / f"brain_stealer_{datetime.now().strftime('%Y-%m-%d')}.log"

    if len(sys.argv) < 2:
        print("사용법:")
        print("  python3 brain_stealer.py [blogId] [작가명]  — 새 작가 등록 + 시작")
        print("  python3 brain_stealer.py --continue          — 미완료 작업 이어서")
        print("  python3 brain_stealer.py --status             — 전체 상태")
        sys.exit(1)

    if sys.argv[1] == "--status":
        data = load_targets()
        print(f"총 {len(data['targets'])}명 등록")
        for t in data["targets"]:
            emoji = "✅" if t["status"] == "완료" else "🔄"
            print(f"  {emoji} {t['name']} ({t['blogId']}): {t['status']} | phase={t.get('phase')} | 글={t.get('total_posts', '?')} | 추출={t.get('extracted_count', '?')}")
        return

    if sys.argv[1] == "--continue":
        data = load_targets()
        pending = [t for t in data["targets"] if t["status"] != "완료"]
        if not pending:
            log("미완료 작업 없음.", lf)
            return
        log(f"미완료 블로거 {len(pending)}명 순차 처리", lf)
        for target in pending:
            log(f"▶ {target['name']} (phase={target.get('phase')}) 시작", lf)
            try:
                run_pipeline(target["blogId"], lf)
            except Exception as e:
                log(f"✖ {target['name']} 실패: {e} — 다음 블로거로 계속", lf)
        log("--continue 전체 처리 종료", lf)
        return

    # 새 작가 등록
    blog_id = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) >= 3 else blog_id

    data = load_targets()
    existing = get_target(data, blog_id)
    if existing:
        log(f"이미 등록됨: {existing['name']} (status={existing['status']})", lf)
        if existing["status"] != "완료":
            run_pipeline(blog_id, lf)
        return

    # 새 등록
    target = {
        "blogId": blog_id,
        "name": name,
        "base_dir": f"{data['settings']['vault_base']}/{name}",
        "status": "진행 중",
        "phase": "phase0",
        "added": datetime.now().strftime("%Y-%m-%d"),
        "total_posts": 0,
        "extracted_count": 0,
    }
    data["targets"].append(target)
    save_targets(data)

    log(f"=== {name} ({blog_id}) 뇌 훔치기 시작 ===", lf)
    send_telegram(f"🧠 뇌 훔치기 시작: {name} ({blog_id})")
    run_pipeline(blog_id, lf)


if __name__ == "__main__":
    from harness_integration import run_as_automation
    sys.exit(run_as_automation("brain_stealer", main, keyword="brain"))
