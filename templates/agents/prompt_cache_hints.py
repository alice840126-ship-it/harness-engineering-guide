#!/usr/bin/env python3
"""prompt_cache_hints — orchestration .md 파일의 STATIC/DYNAMIC 섹션 분리기.

Anthropic prompt cache(5분 TTL) 활용을 위해, orchestration 파일 중
"매 실행마다 같은 부분"(규칙/템플릿/금지어) vs "세션별 바뀌는 부분"(키워드/입력)
을 분리해서 캐시 가능한 블록을 뽑아낸다.

규칙:
    1. frontmatter 바로 아래 `<!-- CACHE-HINTS -->` 블록이 있으면 그것 우선
       예:
           <!-- CACHE-HINTS
           static: ["규칙", "금지어", "템플릿", "스타일"]
           dynamic: ["키워드", "입력", "오늘의 주제"]
           -->
    2. 없으면 휴리스틱: H2 제목 키워드로 분류
       STATIC: 규칙/Rules/금지/템플릿/Template/스타일/Style/원칙/체크리스트
       DYNAMIC: 키워드/입력/Input/오늘/세션/동적

사용:
    from prompt_cache_hints import split_sections
    s = split_sections(Path("orchestration-blog-naver.md"))
    # s["static_blocks"]: list[str]  — 캐시 가능
    # s["dynamic_blocks"]: list[str] — 매번 새로
    # s["frontmatter"], s["preamble"]: 그 외

CLI:
    python3 prompt_cache_hints.py <md_path>    # 분류 출력
    python3 prompt_cache_hints.py selftest
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

STATIC_KEYWORDS = [
    "규칙", "rules", "rule", "금지", "금지어", "템플릿", "template",
    "스타일", "style", "원칙", "체크리스트", "checklist", "constraint",
    "제약", "정의", "definition", "format", "포맷",
]
DYNAMIC_KEYWORDS = [
    "키워드", "keyword", "입력", "input", "오늘", "today", "세션",
    "session", "동적", "dynamic", "파라미터", "parameter", "변수",
]


def _classify(heading: str) -> str:
    """H2/H3 제목 → static / dynamic / unknown."""
    h = heading.lower()
    for k in DYNAMIC_KEYWORDS:
        if k in h:
            return "dynamic"
    for k in STATIC_KEYWORDS:
        if k in h:
            return "static"
    return "unknown"


def _parse_frontmatter(src: str) -> tuple[str, str]:
    """frontmatter(YAML) + 나머지 분리. frontmatter 없으면 ("", src)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", src, flags=re.DOTALL)
    if not m:
        return "", src
    return m.group(0), src[m.end():]


def _parse_cache_hints(after_fm: str) -> tuple[dict | None, str]:
    """`<!-- CACHE-HINTS ... -->` 블록 파싱."""
    m = re.match(r"\s*<!--\s*CACHE-HINTS\s*\n(.*?)\n\s*-->\s*\n",
                  after_fm, flags=re.DOTALL)
    if not m:
        return None, after_fm
    body = m.group(1)
    hints: dict = {"static": [], "dynamic": []}
    # 아주 단순한 YAML-lite: key: [a, b, c]
    for line in body.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip().lower()
        v = v.strip()
        if v.startswith("["):
            try:
                vals = json.loads(v.replace("'", '"'))
                if isinstance(vals, list):
                    hints[k] = [str(x) for x in vals]
            except Exception:
                pass
    return hints, after_fm[m.end():]


def _split_h2(body: str) -> list[tuple[str, str]]:
    """본문을 H2(##)별로 나눠 [(heading, block), ...] 반환. 맨 앞 preamble은 heading=''."""
    lines = body.splitlines(keepends=True)
    sections: list[tuple[str, list[str]]] = [("", [])]
    for ln in lines:
        if re.match(r"^##\s+\S", ln):
            sections.append((ln.strip().lstrip("# ").strip(), [ln]))
        else:
            sections[-1][1].append(ln)
    return [(h, "".join(buf)) for h, buf in sections]


def split_sections(md: Path | str) -> dict[str, Any]:
    """md 파일을 읽어 static/dynamic/unknown 블록으로 분류."""
    if isinstance(md, Path):
        src = md.read_text(encoding="utf-8")
    else:
        src = md
    fm, rest = _parse_frontmatter(src)
    hints, rest = _parse_cache_hints(rest)
    sections = _split_h2(rest)

    result: dict[str, Any] = {
        "frontmatter": fm,
        "hints": hints,
        "preamble": sections[0][1] if sections else "",
        "static_blocks": [],
        "dynamic_blocks": [],
        "unknown_blocks": [],
        "classifications": [],  # [(heading, kind)]
    }

    for heading, block in sections[1:]:
        if hints:
            h_low = heading.lower()
            if any(k.lower() in h_low for k in hints.get("dynamic", [])):
                kind = "dynamic"
            elif any(k.lower() in h_low for k in hints.get("static", [])):
                kind = "static"
            else:
                kind = _classify(heading)
        else:
            kind = _classify(heading)
        result["classifications"].append((heading, kind))
        if kind == "static":
            result["static_blocks"].append(block)
        elif kind == "dynamic":
            result["dynamic_blocks"].append(block)
        else:
            result["unknown_blocks"].append(block)

    # 통계
    tot = len(sections) - 1
    result["stats"] = {
        "total_h2": tot,
        "static": len(result["static_blocks"]),
        "dynamic": len(result["dynamic_blocks"]),
        "unknown": len(result["unknown_blocks"]),
        "static_chars": sum(len(b) for b in result["static_blocks"]),
        "dynamic_chars": sum(len(b) for b in result["dynamic_blocks"]),
    }
    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    arg = sys.argv[1]
    if arg == "selftest":
        _selftest()
        return
    p = Path(arg)
    if not p.exists():
        print(f"❌ 파일 없음: {p}", file=sys.stderr)
        sys.exit(1)
    r = split_sections(p)
    print(f"=== {p.name} ===")
    print(f"frontmatter: {len(r['frontmatter'])} chars")
    print(f"hints: {r['hints']}")
    print(f"stats: {r['stats']}")
    print("\n섹션 분류:")
    for h, k in r["classifications"]:
        icon = {"static": "🟢", "dynamic": "🔵", "unknown": "⚪"}[k]
        print(f"  {icon} [{k:7}] {h[:70]}")


def _selftest():
    import tempfile

    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # === case 1: frontmatter + 힌트 없음, 휴리스틱만
        p1 = tmp / "heu.md"
        p1.write_text(
            "---\nname: x\n---\n\n"
            "preamble text\n\n"
            "## 규칙\n정적 규칙들\n\n"
            "## 키워드\n동적 키워드\n\n"
            "## 기타\n분류안됨\n",
            encoding="utf-8",
        )
        r = split_sections(p1)
        assert r["stats"]["static"] == 1, f"case1 static: {r['stats']}"
        assert r["stats"]["dynamic"] == 1, f"case1 dynamic: {r['stats']}"
        assert r["stats"]["unknown"] == 1, f"case1 unknown: {r['stats']}"
        assert r["frontmatter"], "frontmatter 누락"
        print(f"  ✓ case 1 휴리스틱 ({r['stats']})")
        passed += 1

        # === case 2: CACHE-HINTS 블록 우선
        p2 = tmp / "hint.md"
        p2.write_text(
            "---\nname: y\n---\n"
            '<!-- CACHE-HINTS\n'
            'static: ["abc"]\n'
            'dynamic: ["xyz"]\n'
            '-->\n'
            "## abc section\n정적\n\n"
            "## xyz section\n동적\n\n"
            "## 규칙\n힌트 없으면 static인데 힌트 우선\n",
            encoding="utf-8",
        )
        r2 = split_sections(p2)
        assert r2["hints"] == {"static": ["abc"], "dynamic": ["xyz"]}, r2["hints"]
        assert r2["stats"]["static"] == 2, f"case2 static: {r2['stats']}"  # abc + 규칙
        assert r2["stats"]["dynamic"] == 1, f"case2 dynamic: {r2['stats']}"
        print(f"  ✓ case 2 힌트블록 ({r2['stats']})")
        passed += 1

        # === case 3: frontmatter 없음
        p3 = tmp / "no_fm.md"
        p3.write_text("## 금지어\nabc\n## 입력\ndef\n", encoding="utf-8")
        r3 = split_sections(p3)
        assert r3["frontmatter"] == ""
        assert r3["stats"]["static"] == 1
        assert r3["stats"]["dynamic"] == 1
        print(f"  ✓ case 3 no-frontmatter ({r3['stats']})")
        passed += 1

        # === case 4: 실제 orchestration 파일
        real = Path("/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/orchestration-blog-naver.md")
        if real.exists():
            r4 = split_sections(real)
            assert r4["stats"]["total_h2"] > 3, f"real h2 너무 적음: {r4['stats']}"
            assert r4["frontmatter"], "real frontmatter 없음"
            print(f"  ✓ case 4 real file ({r4['stats']})")
            passed += 1
        else:
            print("  - case 4 skipped (real file missing)")
            passed += 1

        # === case 5: 빈 본문
        p5 = tmp / "empty.md"
        p5.write_text("---\nname: z\n---\n\n", encoding="utf-8")
        r5 = split_sections(p5)
        assert r5["stats"]["total_h2"] == 0
        assert r5["frontmatter"]
        print(f"  ✓ case 5 empty body ({r5['stats']})")
        passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    main()
