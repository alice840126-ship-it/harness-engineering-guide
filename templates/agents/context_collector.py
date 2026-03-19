#!/usr/bin/env python3
"""
컨텍스트 수집 에이전트
- Claude 세션 기록에서 패턴 추출
- 결정, 선호도, 반복 패턴, 인사이트 자동 수집
- Shared Context 자동 업데이트
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class ContextCollector:
    """컨텍스트 수집 에이전트"""

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

    def __init__(
        self,
        history_file: Optional[str] = None,
        patterns_file: Optional[str] = None,
        shared_context_path: Optional[str] = None
    ):
        """
        초기화

        Args:
            history_file: Claude 세션 기록 파일 경로
            patterns_file: 학습된 패턴 저장 파일 경로
            shared_context_path: Shared Context 파일 경로
        """
        self.history_file = Path(history_file) if history_file else Path.home() / ".claude" / "history.jsonl"
        self.patterns_file = Path(patterns_file) if patterns_file else Path.home() / ".claude" / "learned_patterns.json"
        self.shared_context_path = Path(shared_context_path) if shared_context_path else Path.home() / ".claude-unified" / "shared_context.md"

    def collect_context(
        self,
        patterns: Optional[Dict[str, List[str]]] = None,
        limit: int = 50
    ) -> Dict[str, List[str]]:
        """
        컨텍스트 수집

        Args:
            patterns: 커스텀 패턴 정의
            limit: 분석할 최근 세션 수

        Returns:
            발견한 패턴 {"결정": [], "선호도": [], "패턴": [], "인사이트": []}
        """
        # 패턴 설정
        pattern_dict = patterns if patterns else self.DEFAULT_PATTERNS

        # 최근 세션 로드
        sessions = self._load_recent_history(limit)

        # 패턴 분석 - 패턴의 모든 키로 초기화
        all_findings = {key: [] for key in pattern_dict.keys()}

        for session in sessions:
            findings = self._analyze_session(session, pattern_dict)
            for key in all_findings:
                if key in findings:
                    all_findings[key].extend(findings[key])

        return all_findings

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

    def _analyze_session(
        self,
        session: Dict,
        patterns: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """세션 분석"""
        # 패턴의 모든 키를 포함하여 findings 초기화
        findings = {key: [] for key in patterns.keys()}

        # 사용자 메시지 분석
        for msg in session.get("messages", []):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    extracted = self._extract_patterns(content, patterns)
                    for key in findings:
                        if key in extracted:
                            findings[key].extend(extracted[key])

        # Assistant 응답에서도 문맥 추출
        for msg in session.get("messages", []):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str):
                    # "형님이 ~라고 했습니다" 같은 문맥에서 추출
                    extracted = self._extract_patterns(content, patterns)
                    for key in findings:
                        if key in extracted:
                            findings[key].extend(extracted[key])

        return findings

    def _extract_patterns(
        self,
        text: str,
        patterns: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """텍스트에서 패턴 추출"""
        # 패턴의 모든 키를 포함하여 findings 초기화
        findings = {key: [] for key in patterns.keys()}

        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    findings[category].extend(matches)

        return findings

    def generate_insights(self, findings: Dict[str, List[str]]) -> str:
        """발견한 패턴에서 인사이트 생성"""
        insights = []

        # 결정 패턴
        if findings["결정"]:
            insights.append("### 최근 결정\n")
            insights.append(f"- 최근 {len(findings['결정'])}개의 결정 패턴 발견\n")

        # 선호도
        if findings["선호도"]:
            insights.append("### 선호도\n")
            insights.append(f"- {len(findings['선호도'])}개의 선호도 패턴 발견\n")

        # 반복 패턴
        if findings["패턴"]:
            insights.append("### 반복 패턴\n")
            insights.append(f"- {len(findings['패턴'])}개의 반복 패턴 발견\n")

        # 비즈니스 인사이트
        if findings["인사이트"]:
            insights.append("### 비즈니스 인사이트\n")
            insights.append(f"- {len(findings['인사이트'])}개의 인사이트 발견\n")

        return "\n".join(insights)

    def save_patterns(self, findings: Dict[str, List[str]]) -> None:
        """발견한 패턴 저장"""
        patterns_data = {}

        if self.patterns_file.exists():
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                try:
                    patterns_data = json.load(f)
                except json.JSONDecodeError:
                    patterns_data = {}

        today = datetime.now().strftime("%Y-%m-%d")
        if today not in patterns_data:
            patterns_data[today] = {}

        for key, value in findings.items():
            if value:
                patterns_data[today][key] = value

        self.patterns_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.patterns_file, 'w', encoding='utf-8') as f:
            json.dump(patterns_data, f, ensure_ascii=False, indent=2)

    def update_shared_context(self, insights: str) -> bool:
        """Shared Context 업데이트"""
        if not self.shared_context_path.exists():
            return False

        with open(self.shared_context_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # "학습된 패턴" 섹션이 없으면 추가
        if "## 학습된 패턴" not in content:
            content += f"\n\n## 학습된 패턴\n\n{insights}\n"
        else:
            # 기존 섹션 업데이트
            content = re.sub(
                r"## 학습된 패턴\n\n.*?(?=\n\n##|\n*$)",
                f"## 학습된 패턴\n\n{insights}",
                content,
                flags=re.DOTALL
            )

        with open(self.shared_context_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True
