#!/usr/bin/env python3
"""blog_verdict_agent — LLM 기반 블로그 사실 검증 에이전트.

blog_validator.py가 "규칙 린터"(금지어/글자수/중복)이라면, 이 에이전트는
"의미 검증자"다. 출처 없는 수치, 검증 안 된 고유명사, 추측성 표현,
AI 말투 잔재를 Gemini에게 읽기 전용으로 넘겨 VERDICT를 받는다.

설계 원칙 (Part VI — VERDICT 패턴):
    - 읽기 전용: 블로그 내용만 평가, 절대 수정 제안만 생성
    - 엄격 JSON 출력: {"verdict": "PASS|FAIL|PARTIAL", ...}
    - Fallback: LLM 실패/미설정 시 규칙 검증만으로 PARTIAL 반환
    - Fail-close: 모호하면 FAIL로 편향

입력:
    - md_path_or_text: 블로그 마크다운 경로 또는 텍스트
    - keyword: 원 키워드 (컨텍스트로 사용)
    - facts: 사전 검증된 사실 dict (optional) — LLM에 "이건 맞다"고 알려줌

출력:
    {
        "verdict": "PASS" | "FAIL" | "PARTIAL",
        "rule_checks": [...],          # blog_validator 규칙 결과
        "llm_checks": [...],           # LLM 의미 검증 결과
        "failed_checks": [...],        # 사람이 읽을 요약
        "rewrite_hints": [...],        # blog-writer에게 줄 수정 지시
        "llm_used": bool,
        "model": str | None,
    }

CLI:
    python3 blog_verdict_agent.py <블로그.md> [--keyword "..."] [--no-llm]
    python3 blog_verdict_agent.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# 재사용: 기존 blog_validator
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

try:
    from blog_validator import validate as rule_validate  # type: ignore
except Exception:
    rule_validate = None  # 없어도 돌아가도록

ENV_FILE = Path.home() / ".claude/.env"


def _load_env() -> dict[str, str]:
    """~/.claude/.env 에서 GEMINI_API_KEY 등 로드."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------- 규칙 검증 ----------

_SUSPICIOUS_NUM = re.compile(
    r"(약\s*)?[\d,]+(?:\.\d+)?\s*(억원|만원|천만원|원|%|퍼센트|세대|평|㎡)"
)
_SUSPICIOUS_PHRASES = [
    "전문가 의견이 지배적",
    "관계자에 따르면",
    "업계 관계자",
    "알려졌습니다",
    "전해졌습니다",
    "것으로 보입니다",
    "예상됩니다",
]


def rule_check(md: str) -> list[dict]:
    """규칙 기반 체크 — 출처 없는 수치·추측성 문구 찾기."""
    findings: list[dict] = []
    lines = md.splitlines()
    for i, line in enumerate(lines, 1):
        # 출처 URL/출처 명시가 라인에 없으면 수치는 의심
        for m in _SUSPICIOUS_NUM.finditer(line):
            has_src = any(
                tag in line
                for tag in ["출처", "http", "국토부", "한국부동산원", "통계청", "KOSIS"]
            )
            if not has_src:
                findings.append({
                    "type": "unsourced_number",
                    "line": i,
                    "text": line.strip()[:120],
                    "match": m.group(0),
                })
                break  # 한 줄당 하나만
        for phrase in _SUSPICIOUS_PHRASES:
            if phrase in line:
                findings.append({
                    "type": "hedge_phrase",
                    "line": i,
                    "text": line.strip()[:120],
                    "match": phrase,
                })
                break
    return findings


def _run_blog_validator(md_path: Path, min_chars: int, min_h2: int) -> dict:
    """blog_validator.py를 subprocess로 호출해 종료코드+stdout 수집."""
    try:
        r = subprocess.run(
            [sys.executable, str(_HERE / "blog_validator.py"), str(md_path),
             "--min-chars", str(min_chars), "--min-h2", str(min_h2)],
            capture_output=True, text=True, timeout=30,
        )
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


# ---------- LLM 검증 (Gemini) ----------

_LLM_PROMPT = """당신은 한국어 블로그 사실 검증자입니다.
아래 블로그 본문을 읽고, 다음 체크를 수행하세요. 수정은 하지 말고 판정만 하세요.

체크 항목:
1. 출처 없는 구체적 수치 (예: "약 6,104만원", "60% 이상") — 본문에 출처 URL이나 기관명이 없으면 FAIL 사유
2. 검증 안 된 고유명사 (단지명, 인물, 상품명의 오타·오기)
3. 추측성 표현 ("전문가에 따르면", "예상됩니다" 등) — 근거 없는 권위 참조
4. AI 말투 잔재 (단조로운 종결, "다양한 측면에서", "종합적으로", "이처럼" 등)
5. 키워드 부합도 — 블로그 내용이 주어진 keyword와 실제로 관련 있는가

출력은 반드시 JSON 형식으로만, 다른 설명 없이:
{{
    "verdict": "PASS" | "FAIL" | "PARTIAL",
    "issues": [
        {{"type": "unsourced_number|typo|hedge|ai_tone|off_topic", "quote": "본문에서 뽑은 문장", "reason": "왜 문제인지"}},
        ...
    ],
    "rewrite_hints": ["작성자에게 줄 구체적 수정 지시", ...]
}}

규칙:
- 의심 1개 이상이면 PARTIAL, 치명적(사실 오류 1개 이상)이면 FAIL, 전부 깨끗하면 PASS
- issues의 quote는 본문에서 그대로 복사
- 추측 금지: 본문에 명시 안 된 건 문제 삼지 말 것

keyword: {keyword}

=== 블로그 본문 시작 ===
{md}
=== 블로그 본문 끝 ===

JSON만 출력:"""


def llm_check(md: str, keyword: str, model: str = "gemini-2.5-flash") -> dict | None:
    """Gemini로 의미 검증. 실패 시 None 반환."""
    env = _load_env()
    api_key = env.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        # 블로그가 너무 길면 앞 12000자만
        md_trimmed = md if len(md) <= 12000 else md[:12000] + "\n...(truncated)"
        prompt = _LLM_PROMPT.format(keyword=keyword or "(미지정)", md=md_trimmed)
        resp = client.models.generate_content(model=model, contents=prompt)
        text = (resp.text or "").strip()
        # JSON만 추출
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return {"error": "no_json_in_response", "raw": text[:500]}
        parsed = json.loads(text[start:end + 1])
        parsed["_model"] = model
        return parsed
    except Exception as e:
        return {"error": str(e), "_model": model}


# ---------- 메인 엔트리 ----------

def verdict(
    md_path_or_text: str | Path,
    keyword: str = "",
    use_llm: bool = True,
    min_chars: int = 2700,
    min_h2: int = 6,
    model: str = "gemini-2.5-flash",
) -> dict:
    """블로그 검증 실행."""
    # 입력 해석
    md_path: Path | None = None
    s = str(md_path_or_text)
    # 경로로 취급: 개행 없고, 확장자 .md 이거나 존재하는 파일
    looks_like_path = (
        "\n" not in s and len(s) < 512
        and (s.endswith(".md") or (s and Path(s).is_file()))
    )
    if looks_like_path and Path(s).is_file():
        md_path = Path(s)
        md = md_path.read_text(encoding="utf-8")
    else:
        md = s

    out: dict[str, Any] = {
        "verdict": "PASS",
        "rule_checks": [],
        "llm_checks": None,
        "failed_checks": [],
        "rewrite_hints": [],
        "llm_used": False,
        "model": None,
    }

    # 1. blog_validator (외부 프로세스) — md_path 있을 때만
    if md_path is not None:
        bv = _run_blog_validator(md_path, min_chars, min_h2)
        if bv["returncode"] != 0:
            out["verdict"] = "FAIL"
            out["rule_checks"].append({"source": "blog_validator", "ok": False,
                                        "detail": bv["stdout"] or bv["stderr"]})
            out["failed_checks"].append("blog_validator 규칙 실패")
            out["rewrite_hints"].append(bv["stdout"].strip().split("\n")[-3:])
        else:
            out["rule_checks"].append({"source": "blog_validator", "ok": True})

    # 2. 추가 규칙 (출처 없는 수치, 추측 문구)
    rule_findings = rule_check(md)
    if rule_findings:
        out["rule_checks"].append({"source": "verdict_rule", "ok": False,
                                    "findings": rule_findings})
        for f in rule_findings[:5]:
            out["failed_checks"].append(f"{f['type']}: '{f['match']}' (line {f['line']})")
            out["rewrite_hints"].append(
                f"line {f['line']} '{f['match']}' — 출처 URL 추가하거나 '확인 필요'로 대체"
                if f["type"] == "unsourced_number"
                else f"line {f['line']} '{f['match']}' — 근거 출처 명시 또는 문장 제거"
            )
        if out["verdict"] == "PASS":
            out["verdict"] = "PARTIAL"
    else:
        out["rule_checks"].append({"source": "verdict_rule", "ok": True})

    # 3. LLM 검증
    if use_llm:
        llm = llm_check(md, keyword, model=model)
        if llm is None:
            out["llm_used"] = False
            out["rewrite_hints"].append("(LLM 미설정 — GEMINI_API_KEY 필요)")
            if out["verdict"] == "PASS":
                out["verdict"] = "PARTIAL"
        elif llm.get("error"):
            out["llm_used"] = True
            out["model"] = llm.get("_model")
            out["llm_checks"] = llm
            out["failed_checks"].append(f"LLM 호출 실패: {llm['error']}")
            if out["verdict"] == "PASS":
                out["verdict"] = "PARTIAL"
        else:
            out["llm_used"] = True
            out["model"] = llm.get("_model")
            out["llm_checks"] = llm
            llm_v = llm.get("verdict", "PARTIAL").upper()
            # 엄격 합산: 둘 중 낮은 쪽으로
            rank = {"PASS": 2, "PARTIAL": 1, "FAIL": 0}
            out["verdict"] = min(out["verdict"], llm_v, key=lambda v: rank.get(v, 0))
            for issue in llm.get("issues", []) or []:
                out["failed_checks"].append(
                    f"{issue.get('type', '?')}: {issue.get('quote', '')[:80]}"
                )
            for hint in llm.get("rewrite_hints", []) or []:
                out["rewrite_hints"].append(hint)

    return out


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="블로그 MD 경로 또는 'selftest'")
    ap.add_argument("--keyword", default="")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--min-chars", type=int, default=2700)
    ap.add_argument("--min-h2", type=int, default=6)
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    if not args.target or args.target == "selftest":
        _selftest()
        return

    r = verdict(args.target, keyword=args.keyword, use_llm=not args.no_llm,
                min_chars=args.min_chars, min_h2=args.min_h2, model=args.model)

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        badge = {"PASS": "✅", "PARTIAL": "⚠️", "FAIL": "❌"}[r["verdict"]]
        print(f"{badge} VERDICT: {r['verdict']}")
        print(f"LLM used: {r['llm_used']} ({r.get('model')})")
        if r["failed_checks"]:
            print("\n=== Failed Checks ===")
            for c in r["failed_checks"][:10]:
                print(f"  - {c}")
        if r["rewrite_hints"]:
            print("\n=== Rewrite Hints ===")
            for h in r["rewrite_hints"][:10]:
                print(f"  → {h}")

    sys.exit(0 if r["verdict"] == "PASS" else 1)


def _selftest():
    """5회 검증 루프용 self-test (LLM 호출 없이 규칙만)."""
    import tempfile

    samples = [
        # 1. 완전 깨끗한 글
        ("""# 테스트 블로그

## 섹션 1
이것은 정상적인 문장입니다. 어떠한 추측성 표현도 없습니다.

## 섹션 2
또 다른 깨끗한 섹션입니다.
""", "PASS_or_PARTIAL"),  # LLM 없어서 PARTIAL 나올 수도

        # 2. 출처 없는 수치
        ("""# 테스트

## 섹션
이 아파트는 약 16억원에 거래되었습니다. 상승률은 60% 이상입니다.
""", "PARTIAL_or_FAIL"),

        # 3. 추측성 문구
        ("""# 테스트

## 섹션
전문가 의견이 지배적입니다. 관계자에 따르면 그렇다고 알려졌습니다.
""", "PARTIAL_or_FAIL"),

        # 4. 출처 명시된 수치는 통과
        ("""# 테스트

## 섹션
국토부 자료에 따르면 이 단지는 15억원에 거래되었습니다.
(출처: https://rt.molit.go.kr)
""", "PASS_or_PARTIAL"),

        # 5. 빈 문서 (텍스트만 — blog_validator 미실행이므로 규칙상 PASS)
        ("", "PASS_or_PARTIAL"),
        # 6. 금지어 섞인 글 (blog_validator는 path 없을 때 미실행이나 추가 규칙은 hedge 잡음)
        ("# 테스트\n\n## 섹션\n이 상품은 관계자에 따르면 좋다고 전해졌습니다.\n",
         "PARTIAL_or_FAIL"),
    ]

    results = []
    for i, (text, expected) in enumerate(samples, 1):
        r = verdict(text, keyword="테스트", use_llm=False)
        # use_llm=False 이므로 LLM-related PARTIAL 영향 없음
        v = r["verdict"]
        results.append((i, v, expected, r))
        ok = (expected == "PASS_or_PARTIAL" and v in ("PASS", "PARTIAL")) or \
             (expected == "PARTIAL_or_FAIL" and v in ("PARTIAL", "FAIL"))
        badge = "✓" if ok else "✗"
        print(f"  {badge} case {i}: verdict={v} (expected {expected}) "
              f"failed={len(r['failed_checks'])} hints={len(r['rewrite_hints'])}")
        assert ok, f"case {i} failed: got {v}, expected {expected}"

    # 추가: 실제 파일 테스트
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False,
                                       encoding="utf-8") as f:
        f.write("# 테스트 블로그\n\n## 섹션\n정상 문장입니다.\n")
        path = f.name
    r = verdict(path, keyword="테스트", use_llm=False)
    assert isinstance(r, dict) and "verdict" in r
    Path(path).unlink()

    print(f"✅ selftest passed: {len(results)} cases")


if __name__ == "__main__":
    main()
