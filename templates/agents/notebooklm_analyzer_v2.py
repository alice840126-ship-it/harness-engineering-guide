#!/usr/bin/env python3
"""
NotebookLM 분석 에이전트 v2 (BaseAgent 기반)

NotebookLM CLI를 활용한 뉴스/문서 분석
- 단일 책임: NotebookLM 분석만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import json
import subprocess
from typing import List, Dict, Optional, Any
from base_agent import BaseAgent


class NotebookLMAnalyzer(BaseAgent):
    """NotebookLM 분석 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (notebooklm_path, timeout)
        """
        super().__init__("notebooklm_analyzer", config)

        self.notebooklm_path = self.config.get("notebooklm_path", "notebooklm")
        self.timeout = self.config.get("timeout", 600)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "analyze")

        if operation == "analyze":
            return "prompt" in data
        elif operation == "news_trends":
            return "news_items" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        NotebookLM 분석 처리

        Args:
            data: {
                "operation": str,           # "analyze", "news_trends"
                "prompt": str,              # analyze용 프롬프트
                "news_items": list,         # news_trends용 뉴스
                "json_output": bool,        # JSON 출력 여부 (선택)
                "framework": str            # 프레임워크 (선택)
            }

        Returns:
            {"result": any, "operation": str}
        """
        operation = data.get("operation", "analyze")

        if operation == "analyze":
            return self._analyze_with_prompt(data)
        elif operation == "news_trends":
            return self._analyze_news_trends(data)
        else:
            return {"error": "잘못된 operation"}

    def _analyze_with_prompt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """프롬프트 기반 분석"""
        prompt = data["prompt"]
        json_output = data.get("json_output", True)

        try:
            cmd = [self.notebooklm_path, "ask", prompt]

            if json_output:
                cmd.append("--json")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode == 0:
                if json_output:
                    try:
                        return {
                            "result": json.loads(result.stdout),
                            "operation": "analyze",
                            "success": True
                        }
                    except json.JSONDecodeError:
                        return {
                            "result": result.stdout,
                            "operation": "analyze",
                            "success": True
                        }
                else:
                    return {
                        "result": result.stdout,
                        "operation": "analyze",
                        "success": True
                    }
            else:
                return {
                    "error": result.stderr,
                    "operation": "analyze",
                    "success": False
                }

        except subprocess.TimeoutExpired:
            return {"error": "시간 초과", "operation": "analyze", "success": False}
        except FileNotFoundError:
            return {"error": "NotebookLM CLI 없음", "operation": "analyze", "success": False}
        except Exception as e:
            return {"error": str(e), "operation": "analyze", "success": False}

    def _analyze_news_trends(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """뉴스 트렌드 분석"""
        news_items = data["news_items"]
        framework = data.get("framework", "deep_insight")

        # 뉴스를 텍스트로 변환
        news_text = self._news_items_to_text(news_items)

        # 프레임워크별 프롬프트
        prompts = {
            "deep_insight": f"""다음 뉴스들을 분석해서 깊은 인사이트를 도출해주세요:

{news_text}

다음 형식으로 JSON 출력:
{{
    "themes": ["테마1", "테마2"],
    "insights": ["인사이트1", "인사이트2"],
    "recommendations": ["추천1", "추천2"]
}}""",
            "quick_summary": f"""다음 뉴스들을 3문장으로 요약해주세요:

{news_text}"""
        }

        prompt = prompts.get(framework, prompts["deep_insight"])

        return self._analyze_with_prompt({
            "prompt": prompt,
            "json_output": True,
            "operation": "analyze"
        })

    def _news_items_to_text(self, news_items: List[Dict[str, str]]) -> str:
        """뉴스 아이템을 텍스트로 변환"""
        lines = []
        for item in news_items:
            title = item.get("title", "")
            url = item.get("url", "")
            description = item.get("description", "")

            line = f"- {title}"
            if description:
                line += f": {description}"
            if url:
                line += f" ({url})"

            lines.append(line)

        return "\n".join(lines)
