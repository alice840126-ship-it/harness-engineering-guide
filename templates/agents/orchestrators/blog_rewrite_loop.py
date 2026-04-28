#!/usr/bin/env python3
"""blog_rewrite_loop — 블로그 재작성 루프 오케스트레이터.

원리 (Part VI — 연구→합성→구현→검증 4단계, Part VII — 3회 실패 회로차단기):
    1. blog-writer-naver가 생성한 MD를 받아 blog_verdict_agent로 검증
    2. PASS → exit 0 (파이프라인 계속)
    3. FAIL/PARTIAL → rewrite_instructions.json 생성 + exit 2 (Claude가 재호출)
    4. 3회 실패 시 회로차단 + 텔레봇 알림 + exit 3

이 스크립트 자체는 blog-writer-naver(.md 서브에이전트)를 직접 실행하지 않는다.
Claude Code 파이프라인에서 이 스크립트와 blog-writer-naver 호출이 번갈아 돈다:

    loop:
        write  blog-writer-naver  → blog.md
        check  blog_rewrite_loop.py blog.md --attempt N
            PASS → exit 0 (break)
            FAIL → exit 2, instructions.json 읽고 다음 회차
            CIRCUIT → exit 3, 중단

상태 파일:
    <md_path>.rewrite_state.json — attempt 카운터 + 이력

CLI:
    python3 blog_rewrite_loop.py <blog.md> [--keyword "..."] [--max-attempts 3]
        [--min-chars 2700] [--min-h2 6] [--no-llm] [--reset]
    python3 blog_rewrite_loop.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).parent
_AGENTS = _HERE.parent
sys.path.insert(0, str(_AGENTS))

from blog_verdict_agent import verdict as run_verdict  # type: ignore

# 종료 코드
EXIT_PASS = 0
EXIT_REWRITE = 2
EXIT_CIRCUIT = 3


def _state_path(md_path: Path) -> Path:
    return md_path.with_suffix(md_path.suffix + ".rewrite_state.json")


def _instructions_path(md_path: Path) -> Path:
    return md_path.with_suffix(md_path.suffix + ".rewrite_instructions.json")


def _load_state(md_path: Path) -> dict:
    sp = _state_path(md_path)
    if sp.exists():
        try:
            return json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"attempts": 0, "history": []}


def _save_state(md_path: Path, state: dict) -> None:
    _state_path(md_path).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _notify_telegram(msg: str) -> None:
    """telegram_sender 재사용 — 실패해도 조용히 통과."""
    try:
        from telegram_sender import TelegramSender  # type: ignore
        TelegramSender().send(msg)
    except Exception:
        # 최소한 stderr로
        sys.stderr.write(f"[circuit-break] {msg}\n")


def run_loop(
    md_path: Path,
    keyword: str = "",
    max_attempts: int = 3,
    min_chars: int = 2700,
    min_h2: int = 6,
    use_llm: bool = True,
    reset: bool = False,
) -> int:
    """재작성 루프 1회 — verdict만 돌리고 다음 지시를 만들어 exit 코드로 신호."""
    md_path = Path(md_path)
    if reset:
        for p in (_state_path(md_path), _instructions_path(md_path)):
            if p.exists():
                p.unlink()
    state = _load_state(md_path)
    state["attempts"] = state.get("attempts", 0) + 1
    attempt = state["attempts"]

    v = run_verdict(md_path, keyword=keyword, use_llm=use_llm,
                    min_chars=min_chars, min_h2=min_h2)
    state["history"].append({
        "attempt": attempt,
        "at": datetime.now().isoformat(),
        "verdict": v["verdict"],
        "failed_checks": v["failed_checks"][:10],
        "llm_used": v["llm_used"],
    })

    if v["verdict"] == "PASS":
        _save_state(md_path, state)
        # 성공하면 지시 파일 제거
        ip = _instructions_path(md_path)
        if ip.exists():
            ip.unlink()
        print(f"✅ PASS (attempt {attempt}/{max_attempts})")
        return EXIT_PASS

    # FAIL or PARTIAL — 재시도 가능 여부 판단
    if attempt >= max_attempts:
        _save_state(md_path, state)
        _notify_telegram(
            f"🚨 블로그 재작성 회로차단\n"
            f"파일: {md_path.name}\n"
            f"키워드: {keyword}\n"
            f"{max_attempts}회 시도 후 {v['verdict']}\n"
            f"이슈 {len(v['failed_checks'])}개:\n" +
            "\n".join(f"  - {c}" for c in v["failed_checks"][:5])
        )
        print(f"🚨 CIRCUIT BREAK (attempt {attempt}/{max_attempts}) verdict={v['verdict']}")
        for c in v["failed_checks"][:10]:
            print(f"  - {c}")
        return EXIT_CIRCUIT

    # 다음 회차 지시 생성
    instructions = {
        "attempt": attempt,
        "next_attempt": attempt + 1,
        "max_attempts": max_attempts,
        "verdict": v["verdict"],
        "failed_checks": v["failed_checks"],
        "rewrite_hints": v["rewrite_hints"],
        "keyword": keyword,
        "md_path": str(md_path),
        "message_for_writer": (
            f"[재작성 요청 {attempt + 1}/{max_attempts}회차]\n"
            f"직전 시도 verdict: {v['verdict']}\n"
            f"다음 이슈를 수정하여 다시 써주세요:\n"
            + "\n".join(f"  - {c}" for c in v["failed_checks"][:10])
            + "\n\n수정 지시:\n"
            + "\n".join(f"  → {h}" for h in v["rewrite_hints"][:10])
        ),
    }
    _instructions_path(md_path).write_text(
        json.dumps(instructions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _save_state(md_path, state)

    print(f"⚠️  REWRITE REQUESTED (attempt {attempt}/{max_attempts}) verdict={v['verdict']}")
    print(f"지시 파일: {_instructions_path(md_path)}")
    print("다음 단계: blog-writer-naver에 이 지시를 전달해서 재작성하고, 이 스크립트 재실행")
    return EXIT_REWRITE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?")
    ap.add_argument("--keyword", default="")
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--min-chars", type=int, default=2700)
    ap.add_argument("--min-h2", type=int, default=6)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if not args.target or args.target == "selftest":
        _selftest()
        return

    md_path = Path(args.target)
    if not md_path.exists():
        print(f"❌ 파일 없음: {md_path}", file=sys.stderr)
        sys.exit(1)

    rc = run_loop(
        md_path, keyword=args.keyword, max_attempts=args.max_attempts,
        min_chars=args.min_chars, min_h2=args.min_h2,
        use_llm=not args.no_llm, reset=args.reset,
    )
    sys.exit(rc)


def _selftest():
    """5회 검증 시나리오."""
    import tempfile

    passed = 0

    # 충분한 해시태그(10개+)를 포함하는 fixture 공통 꼬리표
    HASHTAGS = "\n\n#tag1 #tag2 #tag3 #tag4 #tag5 #tag6 #tag7 #tag8 #tag9 #tag10 #tag11\n"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # === case 1: PASS — 깨끗한 글
        p1 = tmp / "clean.md"
        p1.write_text(
            "# 테스트\n\n## 섹션 1\n정상 문장입니다.\n## 섹션 2\n두번째 섹션입니다.\n"
            + HASHTAGS,
            encoding="utf-8",
        )
        rc = run_loop(p1, keyword="테스트", max_attempts=3, use_llm=False,
                      min_chars=10, min_h2=2, reset=True)
        assert rc == EXIT_PASS, f"case 1: expected PASS, got {rc}"
        assert not _instructions_path(p1).exists(), "PASS 시 instructions 남으면 안 됨"
        assert _state_path(p1).exists()
        print(f"  ✓ case 1 PASS (rc={rc})")
        passed += 1

        # === case 2: REWRITE — hedge phrase 있어서 PARTIAL
        p2 = tmp / "hedge.md"
        p2.write_text(
            "# 테스트\n\n## 섹션\n관계자에 따르면 좋다고 전해졌습니다.\n"
            + HASHTAGS,
            encoding="utf-8",
        )
        rc = run_loop(p2, keyword="테스트", max_attempts=3, use_llm=False,
                      min_chars=10, min_h2=1, reset=True)
        assert rc == EXIT_REWRITE, f"case 2: expected REWRITE, got {rc}"
        ip = _instructions_path(p2)
        assert ip.exists(), "REWRITE 시 instructions 생성 필요"
        inst = json.loads(ip.read_text(encoding="utf-8"))
        assert inst["attempt"] == 1 and inst["next_attempt"] == 2
        assert inst["rewrite_hints"], "hints 비어있음"
        print(f"  ✓ case 2 REWRITE (rc={rc}, hints={len(inst['rewrite_hints'])})")
        passed += 1

        # === case 3: 회로차단 — 3회 재시도 소진
        p3 = tmp / "always_fail.md"
        p3.write_text(
            "# 테스트\n\n## 섹션\n관계자에 따르면 전해졌습니다.\n"
            + HASHTAGS,
            encoding="utf-8",
        )
        codes = []
        for _ in range(4):  # 1,2,3 REWRITE → 4 CIRCUIT
            rc = run_loop(p3, keyword="테스트", max_attempts=3, use_llm=False,
                          min_chars=10, min_h2=1)
            codes.append(rc)
        assert codes == [EXIT_REWRITE, EXIT_REWRITE, EXIT_CIRCUIT, EXIT_CIRCUIT], \
            f"case 3 progression wrong: {codes}"
        print(f"  ✓ case 3 CIRCUIT (codes={codes})")
        passed += 1

        # === case 4: reset 동작 확인
        rc = run_loop(p3, keyword="테스트", max_attempts=3, use_llm=False,
                      min_chars=10, min_h2=1, reset=True)
        assert rc == EXIT_REWRITE, "reset 후 1회차는 REWRITE여야"
        state = _load_state(p3)
        assert state["attempts"] == 1, f"reset 후 attempt=1 expected, got {state['attempts']}"
        print(f"  ✓ case 4 RESET (attempts={state['attempts']})")
        passed += 1

        # === case 5: min_chars 미달 (blog_validator 통해)
        p5 = tmp / "too_short.md"
        p5.write_text("# 짧음\n\n## 섹션\n짧습니다.\n" + HASHTAGS, encoding="utf-8")
        rc = run_loop(p5, keyword="테스트", max_attempts=3, use_llm=False,
                      min_chars=5000, min_h2=1, reset=True)
        assert rc == EXIT_REWRITE, f"case 5: expected REWRITE, got {rc}"
        inst5 = json.loads(_instructions_path(p5).read_text(encoding="utf-8"))
        assert inst5["verdict"] in ("FAIL", "PARTIAL")
        print(f"  ✓ case 5 SHORT (rc={rc}, verdict={inst5['verdict']})")
        passed += 1

    print(f"✅ selftest passed: {passed}/5 cases")


if __name__ == "__main__":
    main()
