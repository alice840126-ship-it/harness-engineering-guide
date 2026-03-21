#!/usr/bin/env python3
"""
옵시디언 노트 작성 에이전트 v2 (BaseAgent 기반)

옵시디언 Vault에 마크다운 노트를 저장하는 재사용 가능한 에이전트
- 단일 책임: 옵시디언 노트 저장만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from base_agent import BaseAgent


class ObsidianWriter(BaseAgent):
    """옵시디언 노트 작성 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (vault_path)
        """
        super().__init__("obsidian_writer", config)

        self.vault_path = self.config.get("vault_path") or self._get_default_vault_path()

    def _get_default_vault_path(self) -> str:
        """기본 Vault 경로 반환"""
        default_path = os.path.expanduser(
            "~/Library/Mobile Documents/iCloud~md~obsidian/Documents"
        )

        if os.path.exists(default_path):
            vaults = [f for f in os.listdir(default_path)
                     if os.path.isdir(os.path.join(default_path, f))]
            if vaults:
                return os.path.join(default_path, vaults[0])

        return "."

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "write")

        if operation in ["write", "daily"]:
            return "content" in data
        elif operation in ["project", "zettel"]:
            return "title" in data and "content" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        옵시디언 노트 작성 처리

        Args:
            data: {
                "operation": str,    # "write", "daily", "project", "zettel", "append"
                "content": str,      # 노트 내용
                "filename": str,     # 파일명
                "folder": str,       # 폴더
                "subfolder": str,    # 하위 폴더
                "date": str,         # 날짜 (daily용)
                "title": str,        # 제목 (project/zettel용)
                "tags": list,        # 태그 (project용)
                "references": list   # 참고문헌 (zettel용)
            }

        Returns:
            {"path": str, "operation": str}
        """
        operation = data.get("operation", "write")

        if operation == "write":
            return self._write_note(data)
        elif operation == "daily":
            return self._create_daily_note(data)
        elif operation == "project":
            return self._create_project_note(data)
        elif operation == "zettel":
            return self._create_zettelkasten_note(data)
        elif operation == "append":
            return self._append_to_note(data)
        else:
            return {"path": "", "error": "잘못된 operation"}

    def _write_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """기본 노트 작성"""
        content = data["content"]
        filename = data.get("filename", "untitled")
        folder = data.get("folder", "")
        subfolder = data.get("subfolder", "")

        path_parts = [self.vault_path]

        if folder:
            path_parts.append(folder)

        if subfolder:
            path_parts.append(subfolder)

        folder_path = os.path.join(*path_parts)
        Path(folder_path).mkdir(parents=True, exist_ok=True)

        if not filename.endswith('.md'):
            filename += '.md'

        file_path = os.path.join(folder_path, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return {"path": file_path, "operation": "write"}

    def _create_daily_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """데일리 노트 작성"""
        content = data["content"]
        date = data.get("date")
        folder = data.get("folder", "00. Inbox")

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        filename = f"{date}.md"

        return self._write_note({
            "content": content,
            "filename": filename,
            "folder": folder
        })

    def _create_project_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """프로젝트 노트 작성"""
        title = data["title"]
        content = data["content"]
        project_folder = data.get("project_folder", "")
        tags = data.get("tags")

        # YAML frontmatter
        frontmatter = f"""---
type: project
title: {title}
created: {datetime.now().strftime("%Y-%m-%d")}
"""

        if tags:
            frontmatter += f"tags: [{', '.join(tags)}]"

        frontmatter += "---\n\n"

        full_content = frontmatter + f"# {title}\n\n" + content
        filename = title.replace(' ', '-').lower()

        return self._write_note({
            "content": full_content,
            "filename": filename,
            "folder": "01. Projects",
            "subfolder": project_folder
        })

    def _create_zettelkasten_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """제텔카스텐 노트 작성"""
        title = data["title"]
        content = data["content"]
        references = data.get("references")

        frontmatter = f"""---
type: zettel
title: {title}
created: {datetime.now().strftime("%Y-%m-%d")}
tags: [zettel]
---
"""

        full_content = frontmatter + f"# {title}\n\n" + content

        if references:
            full_content += "\n## References\n\n"
            for i, ref in enumerate(references, 1):
                full_content += f"{i}. {ref}\n"

        filename = title.replace(' ', '-')

        return self._write_note({
            "content": full_content,
            "filename": filename,
            "folder": "02. Zettelkasten"
        })

    def _append_to_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """기존 노트에 내용 추가"""
        content = data["content"]
        filename = data.get("filename", "")
        folder = data.get("folder", "")

        try:
            path_parts = [self.vault_path]

            if folder:
                path_parts.append(folder)

            file_path = os.path.join(*path_parts, filename)

            if not file_path.endswith('.md'):
                file_path += '.md'

            if not os.path.exists(file_path):
                return {"path": "", "error": "파일이 존재하지 않습니다"}

            with open(file_path, 'a', encoding='utf-8') as f:
                f.write('\n\n')
                f.write(content)

            return {"path": file_path, "operation": "append"}

        except Exception as e:
            return {"path": "", "error": str(e)}


# 편의 함수
def write_daily_note(content: str, date: Optional[str] = None) -> str:
    """데일리 노트 작성 (편의 함수)"""
    writer = ObsidianWriter()
    result = writer.run({
        "operation": "daily",
        "content": content,
        "date": date
    })
    return result.get("path", "")


def write_project_note(title: str, content: str, folder: str) -> str:
    """프로젝트 노트 작성 (편의 함수)"""
    writer = ObsidianWriter()
    result = writer.run({
        "operation": "project",
        "title": title,
        "content": content,
        "project_folder": folder
    })
    return result.get("path", "")


def write_zettelkasten_note(title: str, content: str) -> str:
    """제텔카스텐 노트 작성 (편의 함수)"""
    writer = ObsidianWriter()
    result = writer.run({
        "operation": "zettel",
        "title": title,
        "content": content
    })
    return result.get("path", "")
