#!/usr/bin/env python3
"""
ObsidianNoteCreator v2 단위 테스트
"""

import pytest
import tempfile
from pathlib import Path
from obsidian_note_creator_v2 import ObsidianNoteCreator


class TestObsidianNoteCreator:
    """ObsidianNoteCreator 테스트"""

    def test_init(self):
        """초기화 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            creator = ObsidianNoteCreator({"vault_path": tmpdir})
            assert creator.name == "obsidian_note_creator"

    def test_validate_input_daily(self):
        """데일리 노트 입력 검증"""
        creator = ObsidianNoteCreator()
        assert creator.validate_input({"operation": "daily"}) is True

    def test_validate_input_note(self):
        """노트 입력 검증"""
        creator = ObsidianNoteCreator()
        assert creator.validate_input({
            "operation": "note",
            "filename": "test",
            "content": "test content"
        }) is True

    def test_process_note(self):
        """노트 처리"""
        with tempfile.TemporaryDirectory() as tmpdir:
            creator = ObsidianNoteCreator({"vault_path": tmpdir})
            result = creator.run({
                "operation": "note",
                "filename": "test_note",
                "content": "# Test\n\nContent"
            })
            assert "path" in result

    def test_get_stats(self):
        """통계 확인"""
        creator = ObsidianNoteCreator()
        stats = creator.get_stats()
        assert "runs" in stats
