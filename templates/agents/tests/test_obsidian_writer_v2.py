#!/usr/bin/env python3
"""
ObsidianWriter v2 단위 테스트
"""

import pytest
import os
import tempfile
from pathlib import Path
from obsidian_writer_v2 import ObsidianWriter


class TestObsidianWriter:
    """ObsidianWriter 테스트"""

    def test_init(self):
        """초기화 테스트"""
        writer = ObsidianWriter()
        assert writer.name == "obsidian_writer"

    def test_init_with_config(self):
        """설정과 함께 초기화"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"vault_path": tmpdir}
            writer = ObsidianWriter(config)
            assert writer.vault_path == tmpdir

    def test_validate_input_write(self):
        """쓰기 입력 검증"""
        writer = ObsidianWriter()
        assert writer.validate_input({
            "operation": "write",
            "content": "test content"
        }) is True

    def test_validate_input_daily(self):
        """데일리 노트 입력 검증"""
        writer = ObsidianWriter()
        assert writer.validate_input({
            "operation": "daily",
            "content": "test content"
        }) is True

    def test_validate_input_project(self):
        """프로젝트 노트 입력 검증"""
        writer = ObsidianWriter()
        assert writer.validate_input({
            "operation": "project",
            "title": "Test Project",
            "content": "test content"
        }) is True

    def test_validate_input_invalid(self):
        """잘못된 입력 검증"""
        writer = ObsidianWriter()
        assert writer.validate_input({
            "operation": "project",
            "title": "Test"
        }) is False

    def test_process_write_operation(self):
        """쓰기 처리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ObsidianWriter({"vault_path": tmpdir})
            result = writer.run({
                "operation": "write",
                "content": "# Test Note\n\nTest content",
                "filename": "test_note"
            })
            assert "path" in result
            assert os.path.exists(result["path"])

    def test_process_daily_operation(self):
        """데일리 노트 처리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ObsidianWriter({"vault_path": tmpdir})
            result = writer.run({
                "operation": "daily",
                "content": "## Daily Note\n\nToday's tasks"
            })
            assert "path" in result
            assert os.path.exists(result["path"])

    def test_process_project_operation(self):
        """프로젝트 노트 처리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ObsidianWriter({"vault_path": tmpdir})
            result = writer.run({
                "operation": "project",
                "title": "Test Project",
                "content": "Project description",
                "project_folder": "test-folder"
            })
            assert "path" in result
            assert os.path.exists(result["path"])
            # YAML frontmatter 확인
            with open(result["path"], "r") as f:
                content = f.read()
                assert "type: project" in content

    def test_process_zettel_operation(self):
        """제텔카스텐 노트 처리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ObsidianWriter({"vault_path": tmpdir})
            result = writer.run({
                "operation": "zettel",
                "title": "Test Zettel",
                "content": "Zettel content",
                "references": ["https://example.com"]
            })
            assert "path" in result
            assert os.path.exists(result["path"])
            # YAML frontmatter 확인
            with open(result["path"], "r") as f:
                content = f.read()
                assert "type: zettel" in content
                assert "## References" in content

    def test_process_append_operation(self):
        """추가 처리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ObsidianWriter({"vault_path": tmpdir})
            # 먼저 파일 생성
            writer.run({
                "operation": "write",
                "content": "Original content",
                "filename": "append_test"
            })
            # 내용 추가
            result = writer.run({
                "operation": "append",
                "content": "Appended content",
                "filename": "append_test.md"
            })
            assert "path" in result
            # 파일이 존재하고 내용이 추가되었는지 확인
            with open(result["path"], "r") as f:
                content = f.read()
                assert "Original content" in content
                assert "Appended content" in content


class TestConvenienceFunctions:
    """편의 함수 테스트"""

    def test_write_daily_note_signature(self):
        """write_daily_note 함수 시그니처"""
        from obsidian_writer_v2 import write_daily_note
        assert callable(write_daily_note)

    def test_write_project_note_signature(self):
        """write_project_note 함수 시그니처"""
        from obsidian_writer_v2 import write_project_note
        assert callable(write_project_note)

    def test_write_zettelkasten_note_signature(self):
        """write_zettelkasten_note 함수 시그니처"""
        from obsidian_writer_v2 import write_zettelkasten_note
        assert callable(write_zettelkasten_note)
