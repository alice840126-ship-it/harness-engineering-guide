#!/usr/bin/env python3
"""
옵시디언 노트 작성 에이전트

옵시디언 Vault에 마크다운 노트를 저장하는 재사용 가능한 에이전트
- 단일 책임: 옵시디언 노트 저장만 담당 (분석, 발송은 다른 에이전트)

표준 YAML (5개 필드 — 모든 에이전트가 build_yaml()로만 생성):
    type / author / date created / date modified / tags
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from base_agent import BaseAgent

VAULT_PATH = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"
)
AUTHOR = '"[[류웅수]]"'

VALID_TYPES = {
    "note", "study", "book", "blog", "project",
    "daily", "meeting", "idea", "analysis", "health", "travel", "memo"
}


def build_yaml(
    note_type: str,
    tags: Optional[List[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    표준 YAML frontmatter 생성 — 모든 에이전트가 이 함수만 사용할 것.

    Args:
        note_type : VALID_TYPES 중 하나
        tags      : 태그 리스트 (주제태그 + 목적태그, 최대 5개)
        extra     : 타입별 추가 필드 (camelCase 규칙)
                    예) {"keyword": "지식산업센터", "bookAuthor": "손의찬"}
    Returns:
        '---\n...\n---\n' 형태의 문자열
    """
    if note_type not in VALID_TYPES:
        note_type = "note"

    now = datetime.now().strftime("%Y-%m-%d")

    lines = ["---"]
    lines.append(f"type: {note_type}")
    lines.append(f"author:")
    lines.append(f"  - {AUTHOR}")
    lines.append(f"date created: {now}")
    lines.append(f"date modified: {now}")

    if tags:
        clean = [t.lstrip("#").strip() for t in tags if t.strip()]
        lines.append("tags:")
        for t in clean:
            lines.append(f"  - {t}")
    else:
        lines.append("tags: []")

    if extra:
        for k, v in extra.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for i in v:
                    lines.append(f"  - {i}")
            else:
                lines.append(f"{k}: {v}")

    lines.append("---")
    return "\n".join(lines) + "\n"


class ObsidianWriter(BaseAgent):
    """옵시디언 노트 작성 에이전트 (BaseAgent 기반)"""

    def __init__(self, vault_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            vault_path: 옵시디언 Vault 경로 (None이면 기본 경로 사용)
            config: BaseAgent 호환 설정 dict (vault_path 키 지원)
        """
        cfg = config or {}
        super().__init__("obsidian_writer", cfg)
        self.vault_path = vault_path or cfg.get("vault_path") or self._get_default_vault_path()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        BaseAgent.run() 인터페이스 — operation에 따라 분기

        Args:
            data: {
                "operation": "write" | "append" | "daily",
                "folder": str,
                "filename": str,
                "content": str,
            }

        Returns:
            {"path": str} 또는 {"success": bool}
        """
        operation = data.get("operation", "write")

        if operation == "write":
            folder = data.get("folder", "")
            filename = data.get("filename", "untitled.md")
            content = data.get("content", "")
            path = self.write_note(content, filename, folder=folder)
            return {"path": path}

        elif operation == "append":
            filename = data.get("filename", "")
            folder = data.get("folder", "")
            content = data.get("content", "")
            success = self.append_to_note(content, filename, folder=folder)
            return {"success": success}

        elif operation == "daily":
            content = data.get("content", "")
            date = data.get("date")
            folder = data.get("folder", "00. Inbox")
            path = self.create_daily_note(content, date=date, folder=folder)
            return {"path": path}

        else:
            return {"error": f"알 수 없는 operation: {operation}"}

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

    def save_note(
        self,
        note_type: str,
        title: str,
        content: str,
        folder: str,
        tags: Optional[List[str]] = None,
        extra: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        표준 YAML + 내용으로 노트 저장 — 권장 메서드.
        모든 에이전트는 write_note 대신 이 메서드를 사용할 것.

        Args:
            note_type : 노트 종류 (VALID_TYPES)
            title     : 노트 제목 (H1 헤더로 사용)
            content   : 본문 (마크다운, YAML 없이)
            folder    : 볼트 내 저장 폴더 경로
            tags      : 태그 리스트
            extra     : 타입별 추가 YAML 필드 (camelCase)
            filename  : 파일명 (None이면 title에서 자동 생성)

        Returns:
            저장된 파일의 전체 경로
        """
        yaml_block = build_yaml(note_type, tags, extra)
        full_content = yaml_block + "\n" + f"# {title}\n\n" + content

        if filename is None:
            filename = title.replace(" ", "-")
        if not filename.endswith(".md"):
            filename += ".md"

        return self.write_note(full_content, filename, folder=folder)

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
        full_content = build_yaml("project", tags) + "\n" + f"# {title}\n\n" + content

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
        full_content = build_yaml("note", ["zettel"]) + "\n" + f"# {title}\n\n" + content

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
