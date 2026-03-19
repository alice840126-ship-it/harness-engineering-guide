#!/usr/bin/env python3
"""
옵시디언 노트 작성 에이전트

옵시디언 Vault에 마크다운 노트를 저장하는 재사용 가능한 에이전트
- 단일 책임: 옵시디언 노트 저장만 담당 (분석, 발송은 다른 에이전트)
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class ObsidianWriter:
    """옵시디언 노트 작성 에이전트"""

    def __init__(self, vault_path: Optional[str] = None):
        """
        초기화

        Args:
            vault_path: 옵시디언 Vault 경로 (None이면 기본 경로 사용)
        """
        self.vault_path = vault_path or self._get_default_vault_path()

    def _get_default_vault_path(self) -> str:
        """기본 Vault 경로 반환"""
        # macOS 기본 경로
        default_path = os.path.expanduser(
            "~/Library/Mobile Documents/iCloud~md~obsidian/Documents"
        )

        # Vault가 존재하는지 확인
        if os.path.exists(default_path):
            # 첫 번째 Vault 반환
            vaults = [f for f in os.listdir(default_path)
                     if os.path.isdir(os.path.join(default_path, f))]
            if vaults:
                return os.path.join(default_path, vaults[0])

        # 현재 디렉토리 사용
        return "."

    def write_note(
        self,
        content: str,
        filename: str,
        folder: str = "",
        subfolder: str = ""
    ) -> str:
        """
        옵시디언 노트 작성

        Args:
            content: 노트 내용 (마크다운)
            filename: 파일명 (확장자 자동 추가)
            folder: 상위 폴더 (옵션)
            subfolder: 하위 폴더 (옵션)

        Returns:
            저장된 파일의 전체 경로
        """
        # 경로 구성
        path_parts = [self.vault_path]

        if folder:
            path_parts.append(folder)

        if subfolder:
            path_parts.append(subfolder)

        # 폴더 생성
        folder_path = os.path.join(*path_parts)
        Path(folder_path).mkdir(parents=True, exist_ok=True)

        # 파일명에 확장자 추가
        if not filename.endswith('.md'):
            filename += '.md'

        # 전체 경로
        file_path = os.path.join(folder_path, filename)

        # 파일 작성
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return file_path

    def create_daily_note(
        self,
        content: str,
        date: Optional[str] = None,
        folder: str = "00. Inbox"
    ) -> str:
        """
        데일리 노트 작성

        Args:
            content: 노트 내용
            date: 날짜 (YYYY-MM-DD, None이면 오늘)
            folder: 저장 폴더

        Returns:
            저장된 파일의 전체 경로
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        filename = f"{date}.md"

        return self.write_note(content, filename, folder=folder)

    def append_to_note(
        self,
        content: str,
        filename: str,
        folder: str = ""
    ) -> bool:
        """
        기존 노트에 내용 추가

        Args:
            content: 추가할 내용
            filename: 파일명
            folder: 폴더

        Returns:
            성공 여부
        """
        try:
            # 경로 구성
            path_parts = [self.vault_path]

            if folder:
                path_parts.append(folder)

            file_path = os.path.join(*path_parts, filename)

            # 확장자 추가
            if not file_path.endswith('.md'):
                file_path += '.md'

            # 파일이 존재하는지 확인
            if not os.path.exists(file_path):
                return False

            # 내용 추가
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write('\n\n')
                f.write(content)

            return True

        except Exception as e:
            print(f"❌ 노트 추가 실패: {e}")
            return False

    def create_project_note(
        self,
        title: str,
        content: str,
        project_folder: str,
        tags: Optional[list] = None
    ) -> str:
        """
        프로젝트 노트 작성 (템플릿 기반)

        Args:
            title: 프로젝트 제목
            content: 프로젝트 내용
            project_folder: 프로젝트 폴더명
            tags: 태그 리스트

        Returns:
            저장된 파일의 전체 경로
        """
        # YAML frontmatter
        frontmatter = f"""---
type: project
title: {title}
created: {datetime.now().strftime("%Y-%m-%d")}
"""

        if tags:
            frontmatter += f"tags: [{', '.join(tags)}]"

        frontmatter += "---\n\n"

        # 내용 구성
        full_content = frontmatter + f"# {title}\n\n" + content

        # 파일명 (공백을 하이픈으로 변환)
        filename = title.replace(' ', '-').lower()

        return self.write_note(
            full_content,
            filename,
            folder="01. Projects",
            subfolder=project_folder
        )

    def create_zettelkasten_note(
        self,
        title: str,
        content: str,
        references: Optional[list] = None
    ) -> str:
        """
        제텔카스텐 노트 작성

        Args:
            title: 노트 제목
            content: 노트 내용
            references: 참고 문헌/링크 리스트

        Returns:
            저장된 파일의 전체 경로
        """
        # YAML frontmatter
        frontmatter = f"""---
type: zettel
title: {title}
created: {datetime.now().strftime("%Y-%m-%d")}
tags: [zettel]
---
"""

        # 내용 구성
        full_content = frontmatter + f"# {title}\n\n" + content

        # 참고 문헌 추가
        if references:
            full_content += "\n## References\n\n"
            for i, ref in enumerate(references, 1):
                full_content += f"{i}. {ref}\n"

        # 파일명 (제목 사용)
        filename = title.replace(' ', '-')

        return self.write_note(full_content, filename, folder="02. Zettelkasten")

    def search_notes(
        self,
        keyword: str,
        folder: str = ""
    ) -> list:
        """
        노트 검색 (파일명 기반)

        Args:
            keyword: 검색어
            folder: 검색할 폴더 (비어있으면 전체)

        Returns:
            일치하는 파일 경로 리스트
        """
        search_path = self.vault_path

        if folder:
            search_path = os.path.join(self.vault_path, folder)

        if not os.path.exists(search_path):
            return []

        matches = []

        for root, dirs, files in os.walk(search_path):
            for file in files:
                if file.endswith('.md') and keyword.lower() in file.lower():
                    matches.append(os.path.join(root, file))

        return matches


# 편의 함수
def write_daily_note(content: str, date: Optional[str] = None) -> str:
    """데일리 노트 작성 (편의 함수)"""
    return ObsidianWriter().create_daily_note(content, date)


def write_project_note(title: str, content: str, folder: str) -> str:
    """프로젝트 노트 작성 (편의 함수)"""
    return ObsidianWriter().create_project_note(title, content, folder)


def write_zettelkasten_note(title: str, content: str) -> str:
    """제텔카스텐 노트 작성 (편의 함수)"""
    return ObsidianWriter().create_zettelkasten_note(title, content)
