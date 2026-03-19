#!/usr/bin/env python3
"""
ObsidianNoteCreator 에이전트 단위 테스트
"""

import unittest
import tempfile
import shutil
from datetime import date
from pathlib import Path
import sys
import os

# agents 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'templates', 'agents'))

from obsidian_note_creator import ObsidianNoteCreator


class TestObsidianNoteCreator(unittest.TestCase):
    """ObsidianNoteCreator 단위 테스트"""

    def setUp(self):
        """테스트 설정"""
        # 임시 볼트 생성
        self.temp_dir = tempfile.mkdtemp()
        self.creator = ObsidianNoteCreator(self.temp_dir)

    def tearDown(self):
        """테스트 정리"""
        # 임시 디렉토리 삭제
        shutil.rmtree(self.temp_dir)

    def test_create_daily_note_today(self):
        """오늘 날짜로 데일리 노트 생성"""
        file_path = self.creator.create_daily_note()

        self.assertIsNotNone(file_path)
        self.assertTrue(Path(file_path).exists())
        self.assertIn(date.today().strftime('%Y-%m-%d'), file_path)

    def test_create_daily_note_specific_date(self):
        """특정 날짜로 데일리 노트 생성"""
        test_date = date(2026, 3, 19)
        file_path = self.creator.create_daily_note(date=test_date)

        self.assertIsNotNone(file_path)
        self.assertIn('2026-03-19', file_path)
        self.assertIn('2026/03월', file_path)

    def test_create_daily_note_already_exists(self):
        """이미 존재하는 노트 처리"""
        test_date = date(2026, 3, 19)

        # 첫 번째 생성
        file_path1 = self.creator.create_daily_note(date=test_date)
        self.assertIsNotNone(file_path1)

        # 두 번째 생성 (이미 존재)
        file_path2 = self.creator.create_daily_note(date=test_date)
        self.assertIsNone(file_path2)

    def test_create_daily_note_custom_goals(self):
        """커스텀 핵심 목표 적용"""
        custom_goals = ["운동", "독서", "영어 공부"]
        file_path = self.creator.create_daily_note(custom_goals=custom_goals)

        self.assertIsNotNone(file_path)

        # 파일 내용 확인
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        for goal in custom_goals:
            self.assertIn(goal, content)

    def test_create_daily_note_yaml_frontmatter(self):
        """YAML frontmatter 올바른지 확인"""
        file_path = self.creator.create_daily_note()

        self.assertIsNotNone(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # YAML frontmatter 확인
        self.assertIn('---', content)
        self.assertIn('TYPE:', content)
        self.assertIn('tags:', content)
        self.assertIn('daily-note', content)
        self.assertIn('date:', content)

    def test_create_note_basic(self):
        """기본 노트 생성"""
        file_path = self.creator.create_note(
            filename="test-note",
            content="# 테스트 노트\n\n내용입니다."
        )

        self.assertIsNotNone(file_path)
        self.assertTrue(Path(file_path).exists())
        self.assertTrue(file_path.endswith('test-note.md'))

    def test_create_note_with_folder(self):
        """폴더 지정하여 노트 생성"""
        file_path = self.creator.create_note(
            filename="test-note",
            content="내용",
            folder="Projects/Test"
        )

        self.assertIsNotNone(file_path)
        self.assertIn('Projects/Test', file_path)

    def test_create_note_with_frontmatter(self):
        """YAML frontmatter와 함께 노트 생성"""
        file_path = self.creator.create_note(
            filename="project-note",
            content="# 프로젝트\n\n설명",
            frontmatter={
                "tags": ["project", "active"],
                "created": "2026-03-19",
                "status": "in-progress"
            }
        )

        self.assertIsNotNone(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('---', content)
        self.assertIn('tags:', content)
        self.assertIn('- project', content)
        self.assertIn('- active', content)
        self.assertIn('created: 2026-03-19', content)

    def test_create_note_auto_extension(self):
        """파일명에 자동으로 .md 확장자 추가"""
        file_path1 = self.creator.create_note(filename="test1", content="content")
        file_path2 = self.creator.create_note(filename="test2.md", content="content")

        self.assertTrue(file_path1.endswith('test1.md'))
        self.assertTrue(file_path2.endswith('test2.md'))

    def test_folder_structure(self):
        """폴더 구조 YYYY/MM월/ 확인"""
        test_date = date(2026, 12, 25)
        file_path = self.creator.create_daily_note(date=test_date)

        self.assertIsNotNone(file_path)
        self.assertIn('2026/12월', file_path)

        # 폴더가 실제로 생성되었는지 확인
        folder_path = Path(file_path).parent
        self.assertTrue(folder_path.exists())
        self.assertTrue(folder_path.is_dir())


if __name__ == '__main__':
    unittest.main()
