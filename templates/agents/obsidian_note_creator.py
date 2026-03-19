#!/usr/bin/env python3
"""
옵시디언 데일리 노트 생성 에이전트
- YAML frontmatter 지원
- 날짜 기반 폴더 구조 (YYYY/MM월/)
- 데일리 노트 템플릿 제공
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional, Dict, List


class ObsidianNoteCreator:
    """옵시디언 데일리 노트 생성 에이전트"""

    def __init__(self, vault_path: str):
        """
        초기화

        Args:
            vault_path: 옵시디얼 볼트 경로
        """
        self.vault_path = Path(vault_path)

    def create_daily_note(
        self,
        date: Optional[date] = None,
        daily_note_folder: str = "30. 자원 상자/01. 데일리 노트",
        template_type: str = "default",
        custom_goals: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        데일리 노트 생성

        Args:
            date: 생성할 날짜 (기본: 오늘)
            daily_note_folder: 데일리 노트 저장 폴더 (볼트 내부 경로)
            template_type: 템플릿 타입
            custom_goals: 커스텀 핵심 목표

        Returns:
            생성된 파일 경로 (이미 존재하면 None)
        """
        if date is None:
            date = datetime.now().date()

        date_str = date.strftime('%Y-%m-%d')
        filename = f"{date_str}.md"

        # 날짜 기반 폴더 구조 (YYYY/MM월/)
        year_month = date.strftime('%Y/%m월')
        filepath = self.vault_path / daily_note_folder / year_month / filename

        # 이미 존재하면 건너뜀
        if filepath.exists():
            return None

        # 디렉토리 생성
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 템플릿 생성
        content = self._get_daily_note_template(date, template_type, custom_goals)

        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(filepath)

    def create_note(
        self,
        filename: str,
        content: str,
        folder: Optional[str] = None,
        frontmatter: Optional[Dict] = None
    ) -> Optional[str]:
        """
        일반 노트 생성

        Args:
            filename: 파일명 (확장자 제외)
            content: 노트 내용
            folder: 저장할 폴더 (볼트 내부 경로)
            frontmatter: YAML frontmatter 데이터

        Returns:
            생성된 파일 경로 (실패하면 None)
        """
        # 파일명에 확장자 추가
        if not filename.endswith('.md'):
            filename += '.md'

        # 경로 설정
        if folder:
            filepath = self.vault_path / folder / filename
        else:
            filepath = self.vault_path / filename

        # 디렉토리 생성
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # YAML frontmatter 추가
        if frontmatter:
            yaml_block = self._format_frontmatter(frontmatter)
            content = f"{yaml_block}\n\n{content}"

        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        return str(filepath)

    def _get_daily_note_template(
        self,
        date: date,
        template_type: str,
        custom_goals: Optional[List[str]]
    ) -> str:
        """데일리 노트 템플릿 생성"""
        date_str = date.strftime('%Y-%m-%d')

        # 기본 핵심 목표
        default_goals = [
            "운동",
            "명상은 언제나 늘 가까이",
            "나는 2026년에 공인중개사 1차 합격했다.",
            "나는 돈이 들어오는 수많은 파이프라인으로 일하지 않아도 세계를 여행하며 문화를 즐긴다.",
            "나는 매달 3000만원의 실적을 올린다.",
            "나는 표현을 잘 하는 person이고, 애정표현도 잘 하며, 잘 웃는다.",
            "주변의 생각, 말을 의식하지 말고, 내가 스스로 당당하게 열심히 살면 된다.",
            "지금 이순간이 최고다."
        ]

        # 커스텀 목표가 있으면 교체
        goals = custom_goals if custom_goals else default_goals

        template = f"""---
TYPE: "[[{date_str}]]"
tags:
  - daily-note
date: {date_str}
date created: {date_str}
date modified: {date_str}
---

## 핵심 목표
"""

        for goal in goals:
            template += f"- {goal}\n"

        template += """
---

## 오늘의 개의


### 핵심 목표



### 오늘의 일정



---

## 작업 로그




---

## 아이디어 & 노트




---

## 회고

### 오늘의 성과 및 배운 점



### 개선할 점 및 내일 할 일


"""
        return template

    def _format_frontmatter(self, data: Dict) -> str:
        """YAML frontmatter 포맷팅"""
        yaml_lines = ["---"]

        for key, value in data.items():
            if isinstance(value, list):
                yaml_lines.append(f"{key}:")
                for item in value:
                    yaml_lines.append(f"  - {item}")
            elif isinstance(value, dict):
                yaml_lines.append(f"{key}:")
                for k, v in value.items():
                    yaml_lines.append(f"  {k}: {v}")
            else:
                yaml_lines.append(f"{key}: {value}")

        yaml_lines.append("---")

        return "\n".join(yaml_lines)
