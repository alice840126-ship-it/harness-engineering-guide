#!/usr/bin/env python3
"""
subagent_linter.py — Claude 서브에이전트 .md 파일 구조/품질 자동 검증.

Usage:
    python3 subagent_linter.py lint <path.md>
    python3 subagent_linter.py lint-all <dir>
    python3 subagent_linter.py selftest

검사 항목:
  1. YAML frontmatter 존재 (첫 줄 ---)
  2. 필수 필드: name, description
  3. 선택 필드: model(sonnet/opus/haiku), color 형식
  4. 금지어(본문): AI 말투 패턴
  5. 토큰 길이(> 8000자 경고)
  6. Examples/예시 섹션 권장
  7. Tools 사용 지시 선명도 (info)
  8. 본문 절대경로 존재 여부

Returns dict:
    {"ok": bool, "errors": [...], "warnings": [...], "stats": {...}}
"""
import argparse
import os
import re
import sys
import tempfile

# AI 말투 / 블로그 금지어 — 서브에이전트 프롬프트에도 스며들면 안 됨
FORBIDDEN_PHRASES = [
    "다양한 측면에서",
    "종합적으로",
    "이처럼",
    "이에 따라",
    "도움이 되셨으면",
    "뿐만 아니라",
    "제시합니다",
    "본 글에서는",
    "활용",
]

VALID_MODELS = {"sonnet", "opus", "haiku"}
VALID_COLORS = {
    "red", "green", "blue", "yellow", "orange", "purple",
    "pink", "cyan", "magenta", "white", "black", "gray", "grey",
}

MAX_BODY_CHARS = 8000


def _parse_frontmatter(text: str):
    """첫 --- 와 다음 --- 사이 YAML 블록을 key:value dict로 단순 파싱.

    Returns (frontmatter_dict_or_None, body_str, frontmatter_end_line).
    PyYAML 미사용, key: value 형태만 지원 (리스트/중첩 스킵).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, 0

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None, text, 0

    fm = {}
    fm_line_map = {}  # field name -> 1-based line number
    for j in range(1, end_idx):
        raw = lines[j]
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.*)$", raw)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            # strip surrounding quotes
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            fm[k] = v
            fm_line_map[k] = j + 1
    fm["__line_map__"] = fm_line_map
    body = "\n".join(lines[end_idx + 1 :])
    return fm, body, end_idx + 1


def _estimate_tokens(text: str) -> int:
    """한국어/영어 혼합 대략 추정: 2자 ≈ 1토큰."""
    return max(1, len(text) // 2)


def lint(md_path: str) -> dict:
    errors = []
    warnings = []
    stats = {
        "chars": 0,
        "est_tokens": 0,
        "h2_count": 0,
        "has_frontmatter": False,
    }

    if not os.path.isfile(md_path):
        errors.append({"code": "file_not_found", "line": 0, "msg": f"파일 없음: {md_path}"})
        return {"ok": False, "errors": errors, "warnings": warnings, "stats": stats}

    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()

    stats["chars"] = len(text)
    stats["est_tokens"] = _estimate_tokens(text)

    # 1. frontmatter 존재
    fm, body, fm_end_line = _parse_frontmatter(text)
    if fm is None:
        errors.append({
            "code": "missing_frontmatter",
            "line": 1,
            "msg": "YAML frontmatter가 없음 (첫 줄 --- 필요)",
        })
        # frontmatter 없으면 본문은 전체로 간주
        body = text
    else:
        stats["has_frontmatter"] = True

        line_map = fm.get("__line_map__", {})

        # 2. 필수 필드
        for required in ("name", "description"):
            if required not in fm or not fm.get(required):
                errors.append({
                    "code": "missing_field",
                    "line": line_map.get(required, 1),
                    "msg": f"필수 필드 누락: {required}",
                })

        # 3. 선택 필드 형식 검증
        if "model" in fm and fm["model"]:
            model_val = fm["model"].lower()
            if model_val not in VALID_MODELS:
                errors.append({
                    "code": "invalid_model",
                    "line": line_map.get("model", 1),
                    "msg": f"model 값 부적절 ({fm['model']}). sonnet/opus/haiku 중 하나여야",
                })
        if "color" in fm and fm["color"]:
            color_val = fm["color"].lower()
            if color_val not in VALID_COLORS:
                warnings.append({
                    "code": "invalid_color",
                    "line": line_map.get("color", 1),
                    "msg": f"color 값 비표준 ({fm['color']})",
                })

    # body 기반 통계
    body_lines = body.splitlines()
    stats["h2_count"] = sum(1 for ln in body_lines if ln.startswith("## "))

    # 4. 금지어
    for phrase in FORBIDDEN_PHRASES:
        for i, ln in enumerate(body_lines):
            if phrase in ln:
                warnings.append({
                    "code": "forbidden_phrase",
                    "line": fm_end_line + i + 1,
                    "msg": f"금지어 감지: '{phrase}'",
                })
                break  # 같은 금지어는 1회만 경고

    # 5. 본문 길이
    body_chars = len(body)
    if body_chars > MAX_BODY_CHARS:
        warnings.append({
            "code": "too_long",
            "line": fm_end_line + 1,
            "msg": f"본문 길이 {body_chars}자 > {MAX_BODY_CHARS}자 (토큰 예산 초과 우려)",
        })

    # 6. Examples 섹션
    has_example = (
        "<example>" in body
        or re.search(r"(?im)^\s*#+\s*(예시|examples?)\b", body) is not None
    )
    if not has_example:
        warnings.append({
            "code": "no_examples",
            "line": fm_end_line + 1,
            "msg": "예시(<example> 또는 '예시'/'Examples' 섹션) 권장",
        })

    # 7. Tools 사용 지시 선명도 (info only — warnings로 분류)
    tool_hints = ["Task tool", "Bash", "Read", "Write", "Edit", "Grep", "Glob", "WebSearch"]
    if not any(h in body for h in tool_hints):
        warnings.append({
            "code": "no_tool_hint",
            "line": fm_end_line + 1,
            "msg": "사용 도구 명시 권장 (Task tool/Bash/Read 등)",
        })

    # 8. 절대경로 존재 확인
    abs_paths = re.findall(r"/Users/oungsooryu/[^\s`'\"\)\]]+", body)
    seen_paths = set()
    for p in abs_paths:
        # 끝에 붙은 구두점 제거
        p_clean = p.rstrip(".,:;!?")
        if p_clean in seen_paths:
            continue
        seen_paths.add(p_clean)
        # 파일/디렉토리 모두 확인
        if not os.path.exists(p_clean):
            warnings.append({
                "code": "missing_path",
                "line": fm_end_line + 1,
                "msg": f"본문 경로 존재 안 함: {p_clean}",
            })

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings, "stats": stats}


# ---------------- Python SPoE 우회 감지 ----------------

# (pattern, SPoE 안내) — 새 파일·수정된 파일이 SPoE를 우회해 CLI를 직접 부르는지 정적 검증.
PY_FORBIDDEN_PATTERNS = [
    (
        r"""subprocess\.(?:run|Popen|call|check_output|check_call)\(\s*\[\s*['"]vercel['"]""",
        "Vercel CLI 직접 호출 금지 — agents/vercel_adapter.py (deploy_dir/shorten_url) 경유",
    ),
    (
        r"""subprocess\.(?:run|Popen|call|check_output|check_call)\(\s*\[\s*['"]netlify['"]""",
        "Netlify CLI 사용 폐기됨 (2026-04-18 Vercel 이관) — vercel_adapter 사용",
    ),
    (
        r"""os\.system\(\s*['"]vercel\s""",
        "Vercel CLI 직접 호출 금지 — agents/vercel_adapter.py 경유",
    ),
]

# 자기 자신(adapter/허용 파일)은 제외 — 이 파일들 안에서는 CLI 직접 호출이 정당함
PY_LINT_WHITELIST = {
    "vercel_adapter.py",
    "vercel_cleanup.py",   # adapter 경유하지만 `projects ls/rm`은 _run_vercel 내부에서 CLI 호출
}


def lint_py_file(py_path: str) -> dict:
    """Python 파일에서 SPoE 우회 패턴 정적 감지.

    Returns {"ok": bool, "violations": [{"line", "code", "msg"}]}.
    """
    violations: list[dict] = []
    if not os.path.isfile(py_path):
        return {"ok": False, "violations": [{"line": 0, "code": "file_not_found", "msg": py_path}]}

    fname = os.path.basename(py_path)
    if fname in PY_LINT_WHITELIST:
        return {"ok": True, "violations": []}

    with open(py_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for i, ln in enumerate(lines, start=1):
        stripped = ln.lstrip()
        if stripped.startswith("#"):
            continue
        for pattern, hint in PY_FORBIDDEN_PATTERNS:
            if re.search(pattern, ln):
                violations.append({
                    "line": i,
                    "code": "spoe_bypass",
                    "msg": hint,
                    "snippet": ln.rstrip()[:120],
                })

    return {"ok": len(violations) == 0, "violations": violations}


def lint_py_dir(directory: str) -> dict:
    """디렉토리 재귀 스캔 (.py만)."""
    results = {}
    for root, _, files in os.walk(directory):
        # 흔한 노이즈 제외
        if any(seg in root for seg in ("/.git", "/__pycache__", "/.venv", "/node_modules")):
            continue
        for fname in files:
            if fname.endswith(".py"):
                full = os.path.join(root, fname)
                r = lint_py_file(full)
                if r["violations"]:
                    results[full] = r
    return results


def lint_all(directory: str) -> dict:
    results = {}
    if not os.path.isdir(directory):
        print(f"ERROR: 디렉토리 없음: {directory}")
        return results
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".md"):
            full = os.path.join(directory, fname)
            results[fname] = lint(full)
    return results


def _format_report(path: str, res: dict) -> str:
    out = []
    tag = "OK" if res["ok"] else "FAIL"
    out.append(f"[{tag}] {path}")
    st = res["stats"]
    out.append(
        f"  stats: chars={st['chars']} est_tokens={st['est_tokens']} "
        f"h2={st['h2_count']} frontmatter={st['has_frontmatter']}"
    )
    for e in res["errors"]:
        out.append(f"  ERROR  [{e['code']}] line {e['line']}: {e['msg']}")
    for w in res["warnings"]:
        out.append(f"  WARN   [{w['code']}] line {w['line']}: {w['msg']}")
    return "\n".join(out)


# ---------------- selftest ----------------

def _selftest() -> int:
    passed = 0
    total = 5
    with tempfile.TemporaryDirectory() as td:
        # case 1: 정상
        p1 = os.path.join(td, "case1.md")
        with open(p1, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "name: test-agent\n"
                "description: 테스트용 에이전트입니다.\n"
                "model: sonnet\n"
                "color: blue\n"
                "---\n\n"
                "# 역할\n\n"
                "이 에이전트는 테스트 목적으로 만들어졌다. Bash와 Read 도구를 사용한다.\n\n"
                "## 예시\n\n"
                "<example>입력: foo → 출력: bar</example>\n"
            )
        r1 = lint(p1)
        if len(r1["errors"]) == 0:
            passed += 1
            print("case1 PASS: 정상 .md, errors=0")
        else:
            print(f"case1 FAIL: errors={r1['errors']}")

        # case 2: frontmatter 누락
        p2 = os.path.join(td, "case2.md")
        with open(p2, "w", encoding="utf-8") as f:
            f.write("# 제목\n\n내용만 있고 frontmatter가 없음. Bash 사용.\n\n## 예시\n<example>x</example>\n")
        r2 = lint(p2)
        if any(e["code"] == "missing_frontmatter" for e in r2["errors"]):
            passed += 1
            print("case2 PASS: missing_frontmatter 감지")
        else:
            print(f"case2 FAIL: errors={r2['errors']}")

        # case 3: name 필드 누락
        p3 = os.path.join(td, "case3.md")
        with open(p3, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "description: name 필드가 없는 케이스\n"
                "---\n\n"
                "본문. Bash 사용.\n\n## 예시\n<example>x</example>\n"
            )
        r3 = lint(p3)
        missing_name = [e for e in r3["errors"] if e["code"] == "missing_field" and "name" in e["msg"]]
        if missing_name and missing_name[0]["line"] > 0:
            passed += 1
            print(f"case3 PASS: missing_field(name) line={missing_name[0]['line']}")
        else:
            print(f"case3 FAIL: errors={r3['errors']}")

        # case 4: 금지어 포함
        p4 = os.path.join(td, "case4.md")
        with open(p4, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "name: case4\n"
                "description: 금지어 테스트\n"
                "---\n\n"
                "이 에이전트는 다양한 측면에서 접근한다. Bash 사용.\n\n"
                "## 예시\n<example>x</example>\n"
            )
        r4 = lint(p4)
        if any(w["code"] == "forbidden_phrase" for w in r4["warnings"]):
            passed += 1
            print("case4 PASS: forbidden_phrase 감지")
        else:
            print(f"case4 FAIL: warnings={r4['warnings']}")

        # case 5: 너무 긴 본문
        p5 = os.path.join(td, "case5.md")
        long_body = "가나다라마바사아자차카타파하 " * 800  # 약 16000자
        with open(p5, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "name: case5\n"
                "description: 긴 본문 테스트\n"
                "---\n\n"
                "Bash 사용.\n\n## 예시\n<example>x</example>\n\n"
                + long_body
            )
        r5 = lint(p5)
        if any(w["code"] == "too_long" for w in r5["warnings"]):
            passed += 1
            print("case5 PASS: too_long 감지")
        else:
            print(f"case5 FAIL: warnings={r5['warnings']}")

    # case 6: Python SPoE 우회 감지 — subprocess(["vercel", ...])
        p6 = os.path.join(td, "case6_bypass.py")
        with open(p6, "w", encoding="utf-8") as f:
            f.write(
                "import subprocess\n"
                "def deploy():\n"
                "    subprocess.run(['vercel', '--prod'], check=True)\n"
            )
        r6 = lint_py_file(p6)
        if (not r6["ok"]) and any(v["code"] == "spoe_bypass" for v in r6["violations"]):
            passed += 1
            total += 1
            print("case6 PASS: Vercel CLI 직접 호출 감지")
        else:
            total += 1
            print(f"case6 FAIL: violations={r6['violations']}")

        # case 7: adapter 자체는 화이트리스트 — 통과해야 함
        p7 = os.path.join(td, "vercel_adapter.py")
        with open(p7, "w", encoding="utf-8") as f:
            f.write(
                "import subprocess\n"
                "def deploy():\n"
                "    subprocess.run(['vercel', '--prod'], check=True)\n"
            )
        r7 = lint_py_file(p7)
        if r7["ok"]:
            passed += 1
            total += 1
            print("case7 PASS: vercel_adapter 화이트리스트")
        else:
            total += 1
            print(f"case7 FAIL: adapter가 잘못 걸림 {r7['violations']}")

    print(f"\n{'✅' if passed == total else '❌'} selftest passed: {passed}/{total}")
    return 0 if passed == total else 1


# ---------------- CLI ----------------

def main():
    ap = argparse.ArgumentParser(description="Claude 서브에이전트 .md linter")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_lint = sub.add_parser("lint", help="단일 .md 검사")
    p_lint.add_argument("path")

    p_all = sub.add_parser("lint-all", help="디렉토리 내 모든 .md 검사")
    p_all.add_argument("dir")

    sub.add_parser("selftest", help="자체 테스트 5케이스 실행")

    args = ap.parse_args()

    if args.cmd == "lint":
        res = lint(args.path)
        print(_format_report(args.path, res))
        sys.exit(0 if res["ok"] else 1)
    elif args.cmd == "lint-all":
        results = lint_all(args.dir)
        fail = 0
        for fname, res in results.items():
            full = os.path.join(args.dir, fname)
            print(_format_report(full, res))
            if not res["ok"]:
                fail += 1
        print(f"\n총 {len(results)}개 중 실패 {fail}개")
        sys.exit(0 if fail == 0 else 1)
    elif args.cmd == "selftest":
        sys.exit(_selftest())


if __name__ == "__main__":
    main()
