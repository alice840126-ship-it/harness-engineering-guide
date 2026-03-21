#!/usr/bin/env python3
"""
다중 위치 기록 에이전트 v2 (BaseAgent 기반)

4곳 동시 기록 (work_log, session_log, shared_context, 옵시디언)
- 단일 책임: 다중 위치 기록만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from base_agent import BaseAgent


class MultiLocationRecorder(BaseAgent):
    """다중 위치 기록 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (경로들)
        """
        super().__init__("multi_location_recorder", config)

        self.work_log_path = Path(self.config.get("work_log_path",
            Path.home() / ".claude" / "work_log.json"))
        self.session_log_path = Path(self.config.get("session_log_path",
            Path.home() / ".claude" / "session_log.md"))
        self.shared_context_path = Path(self.config.get("shared_context_path",
            Path.home() / ".claude-unified" / "shared_context.md"))
        self.obsidian_vault_path = Path(self.config.get("obsidian_vault_path",
            Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"))

        # 폴더 생성
        self.work_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.shared_context_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        return "content" in data

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        다중 위치 기록 처리

        Args:
            data: {
                "content": str,          # 기록할 내용
                "date": str,             # 날짜 (선택)
                "source": str,           # 출처 (선택)
                "targets": list          # 기록 대상들 (선택, 기본: 전체)
            }

        Returns:
            {"results": dict, "success_count": int}
        """
        content = data["content"]
        date = data.get("date")
        source = data.get("source", "terminal")
        targets = data.get("targets", ["work_log", "session_log", "shared_context", "obsidian"])

        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        results = {}

        if "work_log" in targets:
            results["work_log"] = self._record_to_work_log(content, date)

        if "session_log" in targets:
            results["session_log"] = self._record_to_session_log(content, date)

        if "shared_context" in targets:
            results["shared_context"] = self._record_to_shared_context(content, date, source)

        if "obsidian" in targets:
            results["obsidian"] = self._record_to_obsidian_daily(content, date)

        success_count = sum(1 for v in results.values() if v)

        return {
            "results": results,
            "success_count": success_count,
            "total_targets": len(targets),
            "date": date
        }

    def _record_to_work_log(self, content: str, date: str) -> bool:
        """work_log.json에 기록"""
        try:
            data = []
            if self.work_log_path.exists():
                with open(self.work_log_path, 'r') as f:
                    data = json.load(f)

            entry = {
                "date": date,
                "time": datetime.now().strftime("%H:%M"),
                "content": content
            }

            data.append(entry)

            with open(self.work_log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception:
            return False

    def _record_to_session_log(self, content: str, date: str) -> bool:
        """session_log.md에 기록"""
        try:
            with open(self.session_log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n## {date}\n\n{content}\n")

            return True
        except Exception:
            return False

    def _record_to_shared_context(self, content: str, date: str, source: str) -> bool:
        """shared_context.md에 기록"""
        try:
            with open(self.shared_context_path, 'a', encoding='utf-8') as f:
                f.write(f"\n### {date} ({source})\n\n{content}\n")

            return True
        except Exception:
            return False

    def _record_to_obsidian_daily(self, content: str, date: str) -> bool:
        """옵시디언 데일리 노트에 기록"""
        try:
            daily_folder = self.obsidian_vault_path / "30. 자원 상자/01. 데일리 노트"
            daily_folder.mkdir(parents=True, exist_ok=True)

            filename = f"{date}.md"
            filepath = daily_folder / filename

            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n{content}\n")

            return True
        except Exception:
            return False
