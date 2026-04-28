#!/usr/bin/env python3
"""
테크 스카우트 에이전트 (BaseAgent 기반)

매주 최신 Claude Code 생태계(스킬, MCP, 플러그인, 라이브러리)를 탐색하고
텔레그램으로 요약 발송하는 에이전트

단일 책임: Claude를 헤드리스로 실행해 기술 트렌드 수집만 담당

사용법:
    python3 agents/tech_scout.py  # 직접 실행 테스트
"""

import os
import sys
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base_agent import BaseAgent, AgentError

CLAUDE_BIN = os.path.expanduser("~/.npm-global/bin/claude")
CLAUDE_ENV = {
    "HOME": os.path.expanduser("~"),
    "PATH": "/usr/local/bin:/usr/bin:/bin:/Users/oungsooryu/.npm-global/bin",
}

SCOUT_PROMPT = """지금부터 Claude Code 생태계의 최신 동향을 탐색해줘.

탐색 대상 (전 분야 오픈):
- 새로운 MCP 서버 (어떤 분야든)
- 새로운 Claude Code 스킬/플러그인
- 주목할 만한 AI 에이전트 도구/라이브러리
- GitHub에서 떠오르는 Claude/AI 자동화 도구
- Anthropic 공식 업데이트 및 신기능

탐색 방법:
1. web_search로 "claude code new MCP server 2026", "claude code skills trending" 등 검색
2. GitHub Awesome Claude 리스트 확인
3. skills.cokac.com 최신 스킬 확인

결과 형식 (반드시 이 형식으로):
🔍 **이번 주 테크 스카우트** ({date})

🆕 **주목할 신규 도구 TOP 5**
1. [도구명] — [한 줄 설명] | [설치/링크]
2. ...

💡 **왜 주목해야 하나**
- [도구1]: [간단한 이유]
- ...

📌 **형님 시스템에 바로 쓸 수 있는 것**
- [해당 있으면 명시, 없으면 "이번 주 없음"]

탐색 후 결과만 출력하고 다른 작업은 하지 말 것.""".format(
    date=datetime.now().strftime("%Y-%m-%d")
)


class TechScout(BaseAgent):
    """테크 스카우트 에이전트 — Claude 헤드리스 실행으로 기술 트렌드 수집"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="TechScout", config=config or {})
        self.timeout = self.config.get("timeout", 180)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        data 키:
            prompt  : 탐색 프롬프트 (기본값: SCOUT_PROMPT)
            timeout : 제한 시간 (기본값: 180초)
        """
        prompt = data.get("prompt", SCOUT_PROMPT)
        timeout = data.get("timeout", self.timeout)

        print(f"[TechScout] Claude 헤드리스 실행 중... (최대 {timeout}초)")

        try:
            result = subprocess.run(
                [CLAUDE_BIN, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=CLAUDE_ENV,
            )
        except subprocess.TimeoutExpired:
            raise AgentError(f"타임아웃 ({timeout}초 초과)", self.name)
        except FileNotFoundError:
            raise AgentError(f"Claude 바이너리 없음: {CLAUDE_BIN}", self.name)

        if result.returncode != 0:
            raise AgentError(f"Claude 실행 실패: {result.stderr[:200]}", self.name)

        report = result.stdout.strip()
        if not report:
            raise AgentError("Claude 응답이 비어있음", self.name)

        print(f"[TechScout] 완료 — {len(report)}자 수신")
        return {"report": report, "date": datetime.now().strftime("%Y-%m-%d")}


# ── 단독 실행 테스트 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    agent = TechScout()
    try:
        result = agent.run({"prompt": SCOUT_PROMPT})
        print("\n" + "=" * 60)
        print(result["report"])
    except Exception as e:
        print(f"오류: {e}")
        sys.exit(1)
