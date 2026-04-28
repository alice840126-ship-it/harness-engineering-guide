#!/usr/bin/env python3
"""
다중 위치 기록 에이전트 단위 테스트
"""

import sys
import os
import tempfile
from pathlib import Path

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'agents'))

from multi_location_recorder import MultiLocationRecorder


def test_record_to_work_log():
    """work_log.json 기록 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        recorder = MultiLocationRecorder(
            work_log_path=temp_path / "work_log.json",
            session_log_path=temp_path / "session_log.md",
            shared_context_path=temp_path / "shared_context.md",
            obsidian_vault_path=temp_path / "vault"
        )

        # 기록
        content = "테스트 작업 내용"
        success = recorder.record_to_work_log(content)

        assert success, "기록 실패"

        # 확인
        assert recorder.work_log_path.exists(), "파일 생성 안 됨"

        import json
        with open(recorder.work_log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert "current_session" in data, "current_session 없음"
        assert len(data["current_session"]) > 0, "항목 없음"
        assert data["current_session"][-1]["description"] == content, "내용 불일치"

        print("✅ test_record_to_work_log: 테스트 통과")


def test_record_to_session_log():
    """session_log.md 기록 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        recorder = MultiLocationRecorder(
            work_log_path=temp_path / "work_log.json",
            session_log_path=temp_path / "session_log.md",
            shared_context_path=temp_path / "shared_context.md",
            obsidian_vault_path=temp_path / "vault"
        )

        # 기록
        content = "세션 로그 테스트"
        success = recorder.record_to_session_log(content)

        assert success, "기록 실패"

        # 확인
        assert recorder.session_log_path.exists(), "파일 생성 안 됨"

        with open(recorder.session_log_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        assert content in file_content, "내용 없음"
        assert "## [" in file_content, "포맷 오류"

        print("✅ test_record_to_session_log: 테스트 통과")


def test_record_to_shared_context():
    """shared_context.md 기록 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        recorder = MultiLocationRecorder(
            work_log_path=temp_path / "work_log.json",
            session_log_path=temp_path / "session_log.md",
            shared_context_path=temp_path / "shared_context.md",
            obsidian_vault_path=temp_path / "vault"
        )

        # 기록 (터미널)
        content = "터미널 테스트"
        success1 = recorder.record_to_shared_context(content, source="terminal")

        assert success1, "터미널 기록 실패"

        # 기록 (텔레그램)
        content2 = "텔레그램 테스트"
        success2 = recorder.record_to_shared_context(content2, source="telegram")

        assert success2, "텔레그램 기록 실패"

        # 확인
        with open(recorder.shared_context_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        assert "### 터미널 (Claude Code)" in file_content, "터미널 섹션 없음"
        assert "### 텔레그램 봇" in file_content, "텔레그램 섹션 없음"
        assert content in file_content, "터미널 내용 없음"
        assert content2 in file_content, "텔레그램 내용 없음"

        print("✅ test_record_to_shared_context: 테스트 통과")


def test_record_to_4_locations():
    """4곳 동시 기록 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 옵시디언 볼트 설정
        vault_path = temp_path / "vault"
        daily_note_dir = vault_path / "30. 자원 상자" / "01. 데일리 노트"
        daily_note_dir.mkdir(parents=True)

        # 데일리 노트 생성
        today = "2026-03-19"
        daily_note_path = daily_note_dir / f"{today}.md"
        with open(daily_note_path, 'w', encoding='utf-8') as f:
            f.write(f"# {today}\n\n## 작업 로그\n\n---\n")

        recorder = MultiLocationRecorder(
            work_log_path=temp_path / "work_log.json",
            session_log_path=temp_path / "session_log.md",
            shared_context_path=temp_path / "shared_context.md",
            obsidian_vault_path=vault_path
        )

        # 4곳 동시 기록
        content = "4곳 테스트 내용"
        results = recorder.record_to_4_locations(content, date=today, source="terminal")

        # 확인
        assert results["work_log"], "work_log 실패"
        assert results["session_log"], "session_log 실패"
        assert results["shared_context"], "shared_context 실패"
        assert results["obsidian"], "obsidian 실패"

        # 파일 존재 확인
        assert recorder.work_log_path.exists(), "work_log 파일 없음"
        assert recorder.session_log_path.exists(), "session_log 파일 없음"
        assert recorder.shared_context_path.exists(), "shared_context 파일 없음"

        print("✅ test_record_to_4_locations: 테스트 통과")


def test_get_stats():
    """통계 정보 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        recorder = MultiLocationRecorder(
            work_log_path=temp_path / "work_log.json",
            session_log_path=temp_path / "session_log.md",
            shared_context_path=temp_path / "shared_context.md",
            obsidian_vault_path=temp_path / "vault"
        )

        # 기록 (모든 파일 생성)
        recorder.record_to_work_log("테스트1")
        recorder.record_to_work_log("테스트2")
        recorder.record_to_session_log("세션 테스트")
        recorder.record_to_shared_context("공유 컨텍스트 테스트")

        # 통계
        stats = recorder.get_stats()

        # 확인
        assert stats["work_log"]["exists"], "work_log exists False"
        assert stats["session_log"]["exists"], "session_log exists False"
        assert stats["shared_context"]["exists"], "shared_context exists False"
        assert stats["work_log"]["entries"] == 2, f"entries 수 불일치: {stats['work_log']['entries']}"

        print("✅ test_get_stats: 테스트 통과")


def test_obsidian_no_daily_note():
    """데일리 노트 없을 때 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 옵시디언 볼트 설정 (데일리 노트 없음)
        vault_path = temp_path / "vault"
        daily_note_dir = vault_path / "30. 자원 상자" / "01. 데일리 노트"
        daily_note_dir.mkdir(parents=True)

        recorder = MultiLocationRecorder(
            work_log_path=temp_path / "work_log.json",
            session_log_path=temp_path / "session_log.md",
            shared_context_path=temp_path / "shared_context.md",
            obsidian_vault_path=vault_path
        )

        # 기록 (데일리 노트 없음)
        success = recorder.record_to_obsidian_daily("테스트")

        # 실패해야 함
        assert not success, "데일리 노트 없으면 실패해야 함"

        print("✅ test_obsidian_no_daily_note: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 다중 위치 기록 에이전트 테스트 시작")
    print("=" * 50)

    test_record_to_work_log()
    test_record_to_session_log()
    test_record_to_shared_context()
    test_record_to_4_locations()
    test_get_stats()
    test_obsidian_no_daily_note()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
