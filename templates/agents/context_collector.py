#!/usr/bin/env python3
"""
컨텍스트 수집 에이전트 v2 (BaseAgent 기반)

Claude 세션 기록에서 패턴 추출
- 단일 책임: 컨텍스트 수집만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from base_agent import BaseAgent


class ContextCollector(BaseAgent):
    """컨텍스트 수집 에이전트 v2"""

    # 기본 패턴 정의
    DEFAULT_PATTERNS = {
        "결정": [
            r"(결정|확정|예약|신청|완료)(했어야?|할게|할께|해)",
            r"(하기로|하기로 햠|하기로 함)",
            r"(OK|오키|좋아|그래|알았어)",
        ],
        "선호도": [
            r"(좋아|좋아하는|선호|우선순위)",
            r"(싫어|별로|안 좋아|비추)",
            r"(필수|조건|요구사항)",
        ],
        "패턴": [
            r"(매일|매주|매달|항상|보통)",
            r"(루틴|습관|패턴)",
        ],
        "인사이트": [
            r"(투자|부동산|전략|비즈니스)(.*?)(핵심|중요|필수)",
            r"(인사이트|통찰|교훈)",
        ]
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (history_file, patterns_file, shared_context_path)
        """
        super().__init__("context_collector", config)

        self.history_file = Path(self.config.get("history_file",
            Path.home() / ".claude" / "history.jsonl"))
        self.patterns_file = Path(self.config.get("patterns_file",
            Path.home() / ".claude" / "learned_patterns.json"))
        self.shared_context_path = Path(self.config.get("shared_context_path",
            Path.home() / ".claude-unified" / "shared_context.md"))

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "collect")

        if operation == "collect":
            return True  # patterns, limit은 선택사항
        elif operation == "save":
            return "findings" in data
        elif operation == "update_shared":
            return "insights" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        컨텍스트 수집 처리

        Args:
            data: {
                "operation": str,           # "collect", "save", "update_shared"
                "patterns": dict,            # 커스텀 패턴 (선택)
                "limit": int,                # 분석할 최근 세션 수 (선택)
                "findings": dict,            # save용
                "insights": str              # update_shared용
            }

        Returns:
            {"findings": dict, "operation": str} 또는 {"success": bool}
        """
        operation = data.get("operation", "collect")

        if operation == "collect":
            return self._collect_context(data)
        elif operation == "save":
            return self._save_patterns(data)
        elif operation == "update_shared":
            return self._update_shared_context(data)
        else:
            return {"findings": {}, "error": "잘못된 operation"}

    def _collect_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """컨텍스트 수집"""
        patterns = data.get("patterns")
        limit = data.get("limit", 50)

        # 패턴 설정
        pattern_dict = patterns if patterns else self.DEFAULT_PATTERNS

        # 최근 세션 로드
        sessions = self._load_recent_history(limit)

        # 패턴 분석
        all_findings = {key: [] for key in pattern_dict.keys()}

        for session in sessions:
            findings = self._analyze_session(session, pattern_dict)
            for key in all_findings:
                if key in findings:
                    all_findings[key].extend(findings[key])

        return {
            "findings": all_findings,
            "operation": "collect",
            "sessions_analyzed": len(sessions)
        }

    def _save_patterns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """패턴 저장"""
        findings = data["findings"]

        try:
            patterns_data = {}
            if self.patterns_file.exists():
                with open(self.patterns_file, 'r', encoding='utf-8') as f:
                    patterns_data = json.load(f)

            today = datetime.now().strftime("%Y-%m-%d")
            if today not in patterns_data:
                patterns_data[today] = {}

            for key, value in findings.items():
                if value:
                    patterns_data[today][key] = value

            self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(patterns_data, f, ensure_ascii=False, indent=2)

            return {"success": True, "operation": "save"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_shared_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Shared Context 업데이트"""
        insights = data["insights"]

        if not self.shared_context_path.exists():
            return {"success": False, "error": "Shared Context 파일 없음"}

        try:
            with open(self.shared_context_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if "## 학습된 패턴" not in content:
                content += f"\n\n## 학습된 패턴\n\n{insights}\n"
            else:
                content = re.sub(
                    r"## 학습된 패턴\n\n.*?(?=\n\n##|\n*$)",
                    f"## 학습된 패턴\n\n{insights}",
                    content,
                    flags=re.DOTALL
                )

            with open(self.shared_context_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return {"success": True, "operation": "update_shared"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _load_recent_history(self, limit: int = 50) -> List[Dict]:
        """최근 세션 기록 로드"""
        if not self.history_file.exists():
            return []

        with open(self.history_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-limit:]

        sessions = []
        for line in lines:
            try:
                sessions.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        return sessions

    def _analyze_session(self, session: Dict, patterns: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """세션 분석"""
        findings = {key: [] for key in patterns.keys()}

        for msg in session.get("messages", []):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    extracted = self._extract_patterns(content, patterns)
                    for key in findings:
                        if key in extracted:
                            findings[key].extend(extracted[key])

        return findings

    def _extract_patterns(self, text: str, patterns: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """텍스트에서 패턴 추출"""
        findings = {key: [] for key in patterns.keys()}

        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    findings[category].extend(matches)

        return findings
