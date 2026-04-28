#!/usr/bin/env python3
"""scaffold — 새 자동화/에이전트의 하네스 준수 뼈대 자동 생성.

목적: Pre-Write Protocol + run_as_automation + selftest 패턴을 첫 줄부터 강제.
보일러플레이트 때문에 빠뜨리는 일이 없도록.

사용:
    python3 scaffold.py automation <name>          # ~/.claude/scripts/<name>.py 생성
    python3 scaffold.py agent <name>               # agents/<name>.py 생성
    python3 scaffold.py selftest                   # 자체 테스트

생성 후 agent_registry는 다음 쿼리 시 자동 rebuild (signature 변화 감지).
"""
from __future__ import annotations

import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).parent
SCRIPTS_DIR = Path.home() / ".claude" / "scripts"

AUTOMATION_TEMPLATE = '''#!/usr/bin/env python3
"""{name} — TODO: 한 줄 설명.

자동 생성됨(scaffold.py): run_as_automation으로 ⑤⑥ 자동 적용.
"""
import sys
from pathlib import Path

sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from harness_integration import run_as_automation


def main() -> int:
    """실제 자동화 로직. 실패 시 예외 던지면 run_as_automation이 잡아서 텔레그램 알림."""
    # TODO: 실제 로직
    print("{name} running...")
    return 0


if __name__ == "__main__":
    sys.exit(run_as_automation("{name}", main, keyword="{keyword}"))
'''

AGENT_TEMPLATE = '''#!/usr/bin/env python3
"""{name} — TODO: 한 줄 설명.

자동 생성됨(scaffold.py): selftest 엔트리 포함.
SPoE 확인 후 도메인 레지스트리에 행 추가할 것: HARNESS_DOMAIN_REGISTRY.md
"""
from __future__ import annotations

import sys


def core_fn(x):
    """실제 에이전트 핵심 함수. TODO: 구현."""
    return x


def _selftest() -> int:
    """selftest: 각 케이스별로 assert → 모두 통과하면 '✅ selftest passed: N/N'."""
    passed = 0
    total = 1

    # case 1
    assert core_fn(1) == 1, "기본 항등"
    print("  ✓ case 1 기본 항등")
    passed += 1

    print(f"✅ selftest passed: {{passed}}/{{total}}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        sys.exit(_selftest())
    else:
        print(__doc__)
'''


def create_automation(name: str, target_dir: Path = SCRIPTS_DIR) -> Path:
    target = target_dir / f"{name}.py"
    if target.exists():
        raise FileExistsError(f"이미 존재: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    keyword = name.split("_")[0]
    target.write_text(AUTOMATION_TEMPLATE.format(name=name, keyword=keyword), encoding="utf-8")
    target.chmod(0o755)
    return target


def create_agent(name: str, target_dir: Path = AGENTS_DIR) -> Path:
    target = target_dir / f"{name}.py"
    if target.exists():
        raise FileExistsError(f"이미 존재: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(AGENT_TEMPLATE.format(name=name), encoding="utf-8")
    target.chmod(0o755)
    return target


def _selftest() -> int:
    import tempfile

    passed = 0
    total = 5

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # === case 1: automation 템플릿 생성
        p = create_automation("test_auto", target_dir=tmp_path)
        assert p.exists(), "파일 생성 실패"
        body = p.read_text()
        assert "run_as_automation" in body, "run_as_automation 누락"
        assert 'sys.exit(run_as_automation("test_auto"' in body, "엔트리 wrap 누락"
        print("  ✓ case 1 automation 템플릿 — run_as_automation 포함")
        passed += 1

        # === case 2: agent 템플릿 생성
        p2 = create_agent("test_agent", target_dir=tmp_path)
        body2 = p2.read_text()
        assert "_selftest" in body2, "selftest 엔트리 누락"
        assert 'sys.argv[1] == "selftest"' in body2, "CLI 분기 누락"
        assert "✅ selftest passed" in body2, "결과 출력 누락"
        print("  ✓ case 2 agent 템플릿 — selftest 엔트리 포함")
        passed += 1

        # === case 3: 중복 생성 거부
        try:
            create_automation("test_auto", target_dir=tmp_path)
            assert False, "중복 생성을 막아야 함"
        except FileExistsError:
            pass
        print("  ✓ case 3 중복 생성 거부")
        passed += 1

        # === case 4: 생성된 automation 스크립트 compile 가능
        import py_compile
        py_compile.compile(str(p), doraise=True)
        print("  ✓ case 4 생성물 compile OK")
        passed += 1

        # === case 5: 생성된 agent selftest 실행 → passed 반환
        import subprocess
        r = subprocess.run(
            [sys.executable, str(p2), "selftest"],
            capture_output=True, text=True, timeout=10,
        )
        assert r.returncode == 0, f"selftest 실패: {r.stdout}\n{r.stderr}"
        assert "passed: 1/1" in r.stdout, f"passed 패턴 누락: {r.stdout}"
        print("  ✓ case 5 생성된 agent selftest 실제 통과")
        passed += 1

    print(f"✅ selftest passed: {passed}/{total}")
    return 0 if passed == total else 1


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "selftest":
        return _selftest()
    if cmd not in ("automation", "agent"):
        print(f"알 수 없는 타입: {cmd} (automation|agent|selftest)")
        return 1
    if len(sys.argv) < 3:
        print("이름 필요")
        return 1
    name = sys.argv[2]
    try:
        if cmd == "automation":
            p = create_automation(name)
        else:
            p = create_agent(name)
        print(f"✅ 생성: {p}")
        print("다음 단계:")
        print(f"  - Pre-Write Protocol 흔적을 응답에 남긴다")
        print(f"  - TODO를 채운다")
        if cmd == "agent":
            print(f"  - HARNESS_DOMAIN_REGISTRY.md에 행 추가")
        return 0
    except FileExistsError as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
