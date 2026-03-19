#!/usr/bin/env python3
"""
옵시디언 노트 작성 에이전트 단위 테스트
"""

import sys
import os
import tempfile
import shutil

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agents'))

from obsidian_writer import ObsidianWriter


def test_writer_initialization():
    """작성자 초기화 테스트"""
    # 임시 디렉토리로 초기화
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        assert writer.vault_path == temp_dir
        assert os.path.exists(temp_dir)

    print("✅ test_writer_initialization: 테스트 통과")


def test_write_note():
    """노트 작성 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 노트 작성
        content = "# 테스트 노트\n\n내용입니다."
        file_path = writer.write_note(content, "test_note")

        # 파일 존재 확인
        assert os.path.exists(file_path)
        assert file_path.endswith('.md')

        # 내용 확인
        with open(file_path, 'r', encoding='utf-8') as f:
            written_content = f.read()
            assert written_content == content

    print("✅ test_write_note: 테스트 통과")


def test_write_note_with_folder():
    """폴더 지정 노트 작성 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 폴더와 함께 노트 작성
        content = "# 폴더 테스트"
        file_path = writer.write_note(
            content,
            "folder_note",
            folder="TestFolder",
            subfolder="SubFolder"
        )

        # 폴더 구조 확인
        assert os.path.exists(file_path)
        assert "TestFolder" in file_path
        assert "SubFolder" in file_path

    print("✅ test_write_note_with_folder: 테스트 통과")


def test_create_daily_note():
    """데일리 노트 작성 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 오늘 날짜의 데일리 노트
        content = "## 오늘의 할 일\n\n- 작업 1\n- 작업 2"
        file_path = writer.create_daily_note(content, folder="00. Inbox")

        # 파일 확인
        assert os.path.exists(file_path)
        assert "00. Inbox" in file_path

        # 파일명에 날짜가 포함되어 있는지 확인
        filename = os.path.basename(file_path)
        assert filename.endswith('.md')

    print("✅ test_create_daily_note: 테스트 통과")


def test_create_project_note():
    """프로젝트 노트 작성 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 프로젝트 노트
        title = "AI 에이전트 개발"
        content = "## 목표\n\n에이전트 기반 시스템 구축"
        file_path = writer.create_project_note(
            title,
            content,
            project_folder="automation",
            tags=["ai", "agent"]
        )

        # 파일 확인
        assert os.path.exists(file_path)
        assert "01. Projects" in file_path
        assert "automation" in file_path

        # YAML frontmatter 확인
        with open(file_path, 'r', encoding='utf-8') as f:
            written = f.read()
            assert "---" in written
            assert "type: project" in written
            assert "tags: [ai, agent]" in written

    print("✅ test_create_project_note: 테스트 통과")


def test_create_zettelkasten_note():
    """제텔카스텐 노트 작성 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 제텔카스텐 노트
        title = "하네스 엔지니어링"
        content = "## 핵심 개념\n\n환경 제약, 컨텍스트, 피드백"
        references = [
            "https://example.com/harness",
            "https://example.com/agents"
        ]

        file_path = writer.create_zettelkasten_note(title, content, references)

        # 파일 확인
        assert os.path.exists(file_path)
        assert "02. Zettelkasten" in file_path

        # 내용 확인
        with open(file_path, 'r', encoding='utf-8') as f:
            written = f.read()
            assert "## References" in written
            assert "https://example.com/harness" in written

    print("✅ test_create_zettelkasten_note: 테스트 통과")


def test_append_to_note():
    """노트 추가 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 먼저 노트 작성
        original_content = "# 원래 내용"
        writer.write_note(original_content, "append_test")

        # 내용 추가
        additional_content = "\n## 추가된 내용\n\n새로운 텍스트"
        success = writer.append_to_note(additional_content, "append_test")

        assert success

        # 확인
        file_path = os.path.join(temp_dir, "append_test.md")
        with open(file_path, 'r', encoding='utf-8') as f:
            final_content = f.read()
            assert "원래 내용" in final_content
            assert "추가된 내용" in final_content

    print("✅ test_append_to_note: 테스트 통과")


def test_search_notes():
    """노트 검색 테스트"""
    with tempfile.TemporaryDirectory() as temp_dir:
        writer = ObsidianWriter(vault_path=temp_dir)

        # 여러 노트 작성
        writer.write_note("내용 1", "test_note_1")
        writer.write_note("내용 2", "important_note")
        writer.write_note("내용 3", "test_note_2")

        # 검색
        results = writer.search_notes("test")

        assert len(results) == 2
        # 파일 경로에 "test"가 포함되어 있는지 확인
        for path in results:
            assert "test" in path.lower()

    print("✅ test_search_notes: 테스트 통과")


def test_interface_methods():
    """인터페이스 메서드 확인 테스트"""
    writer = ObsidianWriter()

    # 주요 메서드 확인
    assert hasattr(writer, 'write_note')
    assert hasattr(writer, 'create_daily_note')
    assert hasattr(writer, 'create_project_note')
    assert hasattr(writer, 'create_zettelkasten_note')
    assert hasattr(writer, 'append_to_note')
    assert hasattr(writer, 'search_notes')

    print("✅ test_interface_methods: 테스트 통과")


def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 옵시디언 노트 작성 에이전트 테스트 시작")
    print("=" * 50)

    test_writer_initialization()
    test_write_note()
    test_write_note_with_folder()
    test_create_daily_note()
    test_create_project_note()
    test_create_zettelkasten_note()
    test_append_to_note()
    test_search_notes()
    test_interface_methods()

    print("\n" + "=" * 50)
    print("✅ 모든 테스트 통과!")


if __name__ == "__main__":
    run_all_tests()
