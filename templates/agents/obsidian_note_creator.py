#!/usr/bin/env python3
"""
옵시디언 데일리 노트 생성 에이전트 v2 (BaseAgent 기반)

YAML frontmatter 지원 데일리 노트 생성
- 단일 책임: 데일리 노트 생성만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from base_agent import BaseAgent
from obsidian_writer import build_yaml, ObsidianWriter


class ObsidianNoteCreator(BaseAgent):
    """옵시디언 데일리 노트 생성 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (vault_path)
        """
        super().__init__("obsidian_note_creator", config)

        self.vault_path = Path(self.config.get("vault_path",
            Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"))

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "daily")

        if operation == "daily":
            return True  # 모든 파라미터는 선택사항
        elif operation == "note":
            return "filename" in data and "content" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        노트 생성 처리

        Args:
            data: {
                "operation": str,           # "daily", "note"
                "date": str,                # daily용 날짜 (선택)
                "template_type": str,       # daily용 템플릿 타입 (선택)
                "custom_goals": list,       # daily용 커스텀 목표 (선택)
                "filename": str,            # note용 파일명
                "content": str,             # note용 내용
                "folder": str,              # note용 폴더 (선택)
                "frontmatter": dict         # note용 frontmatter (선택)
            }

        Returns:
            {"path": str, "operation": str} 또는 {"already_exists": bool}
        """
        operation = data.get("operation", "daily")

        if operation == "daily":
            return self._create_daily_note(data)
        elif operation == "note":
            return self._create_note(data)
        else:
            return {"error": "잘못된 operation"}

    def _create_daily_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """데일리 노트 생성"""
        date_str = data.get("date")
        template_type = data.get("template_type", "default")
        custom_goals = data.get("custom_goals")

        if date_str:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            date = datetime.now().date()

        date_str = date.strftime('%Y-%m-%d')
        filename = f"{date_str}.md"

        daily_note_folder = "30. 자원 상자/01. 데일리 노트"
        year_month = date.strftime('%Y/%m월')
        filepath = self.vault_path / daily_note_folder / year_month / filename

        if filepath.exists():
            return {"already_exists": True, "path": str(filepath)}

        filepath.parent.mkdir(parents=True, exist_ok=True)
        content = self._get_daily_note_template(date, template_type, custom_goals)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return {"path": str(filepath), "operation": "daily", "created": True}

    def _create_note(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """일반 노트 생성 — obsidian_writer.save_note() 경유, 표준 YAML 보장"""
        note_type = data.get("type", "note")
        title     = data.get("title") or data.get("filename", "untitled").replace(".md", "")
        content   = data.get("content", "")
        folder    = data.get("folder", "")
        tags      = data.get("tags")
        extra     = data.get("extra")
        filename  = data.get("filename")

        writer = ObsidianWriter()
        path = writer.save_note(
            note_type=note_type,
            title=title,
            content=content,
            folder=folder,
            tags=tags,
            extra=extra,
            filename=filename,
        )
        return {"path": path, "operation": "note", "created": True}

    def _get_daily_note_template(self, date: date, template_type: str, custom_goals: Optional[List[str]]) -> str:
        """데일리 노트 템플릿 생성"""
        date_str = date.strftime('%Y-%m-%d')
        weekday = date.strftime('%A')

        if custom_goals:
            goals_text = "\n".join([f"- {goal}" for goal in custom_goals])
        else:
            goals_text = "- [ ] 목표 1\n- [ ] 목표 2\n- [ ] 목표 3"

        if template_type == "default":
            return build_yaml("daily", ["daily"]) + f"""
# {date_str} ({weekday})

## 🎯 핵심 목표

{goals_text}

## 📋 오늘의 할 일

- [ ]
- [ ]
- [ ]

## 💡 인사이트



## 📝 메모



"""
        elif template_type == "simple":
            return f"""# {date_str}

## 할 일



## 메모



"""
        else:
            return self._get_daily_note_template(date, "default", custom_goals)
