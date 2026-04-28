#!/usr/bin/env python3
"""agent_registry — 에이전트 레지스트리 + 검색.

`agents/` 디렉토리의 모든 `*.py`와 `*.md` 에이전트를 스캔해서
docstring·클래스·CLI 여부를 뽑아 REGISTRY.json으로 저장한다.

존재 목적:
    - 60+ 에이전트 중 "뭘 재사용할지" 매번 ls+Grep 수동 탐색 → 레지스트리 한 방 조회로
    - CLAUDE.md "새 작업 전 체크 순서" 규칙의 자동화

CLI:
    python3 agent_registry.py build                  # REGISTRY.json 재생성
    python3 agent_registry.py list                   # 전체 목록
    python3 agent_registry.py find <keyword>         # docstring/이름 검색
    python3 agent_registry.py show <agent_name>      # 특정 에이전트 상세
    python3 agent_registry.py selftest
"""
from __future__ import annotations

import ast
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

AGENTS_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = AGENTS_DIR / "REGISTRY.json"

# 스캔 제외
EXCLUDE_FILES = {"__init__.py", "agent_registry.py", "base_agent.py",
                  "examples.py", "AGENT_TEMPLATE.md", "AGENT_TEMPLATE_V2.md",
                  "README.md", "PRD_news_scraper.md"}


def _extract_py_info(path: Path) -> dict[str, Any]:
    """Python 파일에서 docstring / classes / CLI 여부 추출."""
    info: dict[str, Any] = {
        "name": path.stem,
        "path": str(path.relative_to(AGENTS_DIR.parent)),
        "type": "python",
        "docstring": None,
        "summary": None,
        "classes": [],
        "functions": [],
        "has_cli": False,
        "importable": True,
        "size_bytes": path.stat().st_size,
    }
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        info["importable"] = False
        info["error"] = str(e)
        return info
    try:
        tree = ast.parse(src)
    except Exception as e:
        info["importable"] = False
        info["error"] = f"parse_error: {e}"
        return info

    info["docstring"] = ast.get_docstring(tree)
    if info["docstring"]:
        # 첫 줄만 summary로
        first_line = info["docstring"].strip().split("\n", 1)[0]
        info["summary"] = first_line[:200]

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            cls = {
                "name": node.name,
                "docstring": ast.get_docstring(node),
                "bases": [ast.unparse(b) for b in node.bases] if node.bases else [],
            }
            info["classes"].append(cls)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            info["functions"].append({
                "name": node.name,
                "doc": (doc.split("\n", 1)[0][:120] if doc else None),
            })

    # CLI: __main__ 블록 or argparse/sys.argv
    info["has_cli"] = bool(
        re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", src)
        or "argparse" in src
        or "sys.argv" in src
    )
    return info


def _extract_md_info(path: Path) -> dict[str, Any]:
    """Markdown(서브에이전트) 파일에서 frontmatter / 첫 설명 추출."""
    info: dict[str, Any] = {
        "name": path.stem,
        "path": str(path.relative_to(AGENTS_DIR.parent)),
        "type": "markdown_subagent",
        "description": None,
        "summary": None,
        "model": None,
        "color": None,
        "size_bytes": path.stat().st_size,
    }
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        info["error"] = str(e)
        return info

    # YAML frontmatter (--- ... ---)
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", src, flags=re.DOTALL)
    if m:
        fm = m.group(1)
        for line in fm.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                if k in ("description", "model", "color", "name"):
                    info[k] = v
        body_start = m.end()
    else:
        body_start = 0

    # 본문 첫 의미있는 줄 → summary
    body = src[body_start:].strip()
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        info["summary"] = line[:200]
        break
    return info


def _scan_paths() -> list[Path]:
    """인덱싱 대상 경로 전부 나열 (stale 감지·빌드 공용)."""
    paths: list[Path] = []
    for p in sorted(AGENTS_DIR.glob("*.py")):
        if p.name not in EXCLUDE_FILES:
            paths.append(p)
    for p in sorted(AGENTS_DIR.glob("*.md")):
        if p.name not in EXCLUDE_FILES:
            paths.append(p)
    orch_dir = AGENTS_DIR / "orchestrators"
    if orch_dir.is_dir():
        for p in sorted(orch_dir.glob("*.py")):
            if not p.name.startswith("_") and p.name not in EXCLUDE_FILES:
                paths.append(p)
    return paths


def compute_signature() -> str:
    """현재 agents/ 디렉토리의 파일 집합 시그니처 (mtime+size 기반 해시).

    새 파일 추가 / 기존 파일 수정 / 파일 삭제 시 값이 바뀜.
    """
    h = hashlib.sha256()
    for p in _scan_paths():
        try:
            st = p.stat()
            h.update(f"{p.name}|{int(st.st_mtime)}|{st.st_size}\n".encode("utf-8"))
        except OSError:
            continue
    return h.hexdigest()[:16]


def build_registry() -> dict:
    entries = []
    # Python
    for p in sorted(AGENTS_DIR.glob("*.py")):
        if p.name in EXCLUDE_FILES:
            continue
        entries.append(_extract_py_info(p))
    # Markdown subagents
    for p in sorted(AGENTS_DIR.glob("*.md")):
        if p.name in EXCLUDE_FILES:
            continue
        entries.append(_extract_md_info(p))
    # Orchestrators subdir
    orch_dir = AGENTS_DIR / "orchestrators"
    if orch_dir.is_dir():
        for p in sorted(orch_dir.glob("*.py")):
            if p.name.startswith("_") or p.name in EXCLUDE_FILES:
                continue
            info = _extract_py_info(p)
            info["type"] = "python_orchestrator"
            entries.append(info)

    registry = {
        "generated_at": datetime.now().isoformat(),
        "agents_dir": str(AGENTS_DIR),
        "signature": compute_signature(),
        "count": len(entries),
        "counts_by_type": {},
        "entries": entries,
    }
    for e in entries:
        t = e["type"]
        registry["counts_by_type"][t] = registry["counts_by_type"].get(t, 0) + 1
    return registry


def save_registry(reg: dict) -> Path:
    REGISTRY_PATH.write_text(
        json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return REGISTRY_PATH


def load_registry(auto_rebuild: bool = True) -> dict:
    """REGISTRY.json 로드. auto_rebuild=True면 stale 감지 시 자동 rebuild.

    Stale 조건:
      (1) REGISTRY.json 없음
      (2) 저장된 signature ≠ 현재 디렉토리 signature (새 파일/수정/삭제 발생)

    환경변수 `AGENT_REGISTRY_NO_AUTO=1` 이면 auto_rebuild 비활성.
    """
    if os.environ.get("AGENT_REGISTRY_NO_AUTO") == "1":
        auto_rebuild = False

    if not REGISTRY_PATH.exists():
        if auto_rebuild:
            sys.stderr.write("🔄 REGISTRY.json 없음 — 자동 build\n")
            reg = build_registry()
            save_registry(reg)
            return reg
        return build_registry()

    try:
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        if auto_rebuild:
            sys.stderr.write("🔄 REGISTRY.json 손상 — 자동 rebuild\n")
            reg = build_registry()
            save_registry(reg)
            return reg
        raise

    if auto_rebuild:
        stored_sig = reg.get("signature", "")
        current_sig = compute_signature()
        if stored_sig != current_sig:
            old_count = reg.get("count", 0)
            reg = build_registry()
            save_registry(reg)
            delta = reg["count"] - old_count
            sign = "+" if delta >= 0 else ""
            sys.stderr.write(
                f"🔄 agents/ 변경 감지 — auto-rebuild 완료 "
                f"({old_count} → {reg['count']}, {sign}{delta})\n"
            )
    return reg


def find_agents(query: str, reg: dict | None = None) -> list[dict]:
    reg = reg or load_registry()
    q = query.lower()
    hits = []
    for e in reg["entries"]:
        hay = " ".join([
            e.get("name", ""), e.get("summary") or "",
            e.get("docstring") or "", e.get("description") or "",
            " ".join(c["name"] for c in e.get("classes", [])),
            " ".join(f["name"] for f in e.get("functions", [])),
        ]).lower()
        if q in hay:
            hits.append(e)
    return hits


# ------------- CLI -------------

def cmd_build(argv):
    reg = build_registry()
    p = save_registry(reg)
    print(f"✅ {reg['count']}개 에이전트 → {p}")
    for t, n in reg["counts_by_type"].items():
        print(f"  - {t}: {n}")


def cmd_list(argv):
    reg = load_registry()
    print(f"{'name':40} {'type':22} summary")
    print("-" * 100)
    for e in reg["entries"]:
        summary = (e.get("summary") or e.get("description") or "")[:50]
        print(f"{e['name'][:40]:40} {e['type']:22} {summary}")


def cmd_find(argv):
    if not argv:
        print("사용: agent_registry.py find <keyword>", file=sys.stderr)
        sys.exit(2)
    q = " ".join(argv)
    hits = find_agents(q)
    if not hits:
        print(f"(매치 없음: {q})")
        return
    print(f"=== '{q}' 매칭 {len(hits)}개 ===\n")
    for e in hits:
        print(f"🔹 {e['name']} [{e['type']}]")
        print(f"   path: {e['path']}")
        if e.get("summary"):
            print(f"   ▶ {e['summary']}")
        if e.get("description"):
            print(f"   ▶ {e['description']}")
        if e.get("classes"):
            cls_names = ", ".join(c["name"] for c in e["classes"][:5])
            print(f"   classes: {cls_names}")
        print()


def cmd_show(argv):
    if not argv:
        print("사용: agent_registry.py show <agent_name>", file=sys.stderr)
        sys.exit(2)
    name = argv[0]
    reg = load_registry()
    for e in reg["entries"]:
        if e["name"] == name or e["name"].lower() == name.lower():
            print(json.dumps(e, ensure_ascii=False, indent=2))
            return
    print(f"(없음: {name}). 가까운 이름:")
    hits = find_agents(name, reg)
    for h in hits[:5]:
        print(f"  - {h['name']}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="list")
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    if a.cmd == "build":
        cmd_build(a.args)
    elif a.cmd == "list":
        cmd_list(a.args)
    elif a.cmd == "find":
        cmd_find(a.args)
    elif a.cmd == "show":
        cmd_show(a.args)
    elif a.cmd == "selftest":
        _selftest()
    else:
        print(f"unknown: {a.cmd}")
        sys.exit(1)


def _selftest():
    # 1. build 성공 + count > 30 (형님 환경 60+)
    reg = build_registry()
    assert reg["count"] > 30, f"count too low: {reg['count']}"
    assert "python" in reg["counts_by_type"], "python agents missing"
    assert "markdown_subagent" in reg["counts_by_type"], "md agents missing"
    print(f"  ✓ build: {reg['count']} entries, types={list(reg['counts_by_type'])}")

    # 2. save + load round-trip
    save_registry(reg)
    reg2 = load_registry()
    assert reg2["count"] == reg["count"]
    print(f"  ✓ save/load round-trip (count={reg2['count']})")

    # 3. find: known keyword "telegram" → telegram_sender 있어야
    hits = find_agents("telegram")
    names = [h["name"] for h in hits]
    assert "telegram_sender" in names, f"telegram_sender missing from: {names}"
    print(f"  ✓ find 'telegram' → {len(hits)} hits")

    # 4. find: korean keyword
    hits_kr = find_agents("블로그")
    assert len(hits_kr) > 0, "블로그 검색 0건"
    print(f"  ✓ find '블로그' → {len(hits_kr)} hits")

    # 5. show: pipeline_observer (방금 만든 것)
    found = [e for e in reg["entries"] if e["name"] == "pipeline_observer"]
    assert found, "pipeline_observer not indexed — build missed new file"
    assert found[0]["has_cli"], "pipeline_observer.py should have CLI"
    print(f"  ✓ show pipeline_observer: has_cli={found[0]['has_cli']}")

    # 6. signature 기반 stale 감지 → auto-rebuild
    import tempfile
    sig1 = compute_signature()
    # 가짜 새 파일 추가해서 signature 변화 확인
    fake = AGENTS_DIR / "__selftest_tmp_agent__.py"
    fake.write_text('"""selftest temp."""\n', encoding="utf-8")
    try:
        sig2 = compute_signature()
        assert sig1 != sig2, "signature 안 바뀜 — stale 감지 불가"

        # load_registry가 자동 rebuild 하는지 확인
        # 먼저 구 signature로 저장된 상태 시뮬레이션
        stored = load_registry(auto_rebuild=False)
        stored["signature"] = "DEADBEEF_FAKE"
        save_registry(stored)

        # auto_rebuild=True로 호출 → signature 달라서 rebuild 트리거
        reg_new = load_registry(auto_rebuild=True)
        assert reg_new["signature"] == sig2, \
            f"auto-rebuild 후에도 signature 불일치 ({reg_new['signature']} vs {sig2})"
        names = [e["name"] for e in reg_new["entries"]]
        assert "__selftest_tmp_agent__" in names, "새 파일이 인덱스에 안 들어감"
        print("  ✓ stale 감지 + auto-rebuild 정확")
    finally:
        fake.unlink(missing_ok=True)
        # 정리된 상태로 최종 rebuild
        save_registry(build_registry())

    print(f"✅ selftest passed: 6 checks")


if __name__ == "__main__":
    main()
