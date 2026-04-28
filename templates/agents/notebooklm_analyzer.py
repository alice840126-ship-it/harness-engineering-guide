#!/usr/bin/env python3
"""
NotebookLM 분석 에이전트 v2 (BaseAgent 기반)

notebooklm-py Python SDK를 활용한 노트북 질문/분석
- "ask": 기존 노트북에 직접 질문
- "analyze": 텍스트 소스 업로드 후 질문
"""

import asyncio
import re
from typing import Dict, Optional, Any
from base_agent import BaseAgent


def _remove_citations(text: str) -> str:
    """[1], [1,2], [3-5] 등 인용 표시 제거"""
    return re.sub(r"\s*\[[\d,\s\-]+\]", "", text)


class NotebookLMAnalyzer(BaseAgent):
    """NotebookLM 분석 에이전트 v2 (Python SDK 기반)"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("notebooklm_analyzer", config)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        operation = data.get("operation", "ask")
        if operation == "ask":
            return "notebook_id" in data and "prompt" in data
        elif operation == "analyze":
            return "notebook_id" in data and "news_text" in data and "prompt" in data
        return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        NotebookLM 분석 처리

        Args:
            data: {
                "operation": str,          # "ask" | "analyze"

                # ask (기존 노트북에 직접 질문):
                "notebook_id": str,        # 노트북 ID
                "prompt": str,             # 질문
                "ask_timeout": int,        # 응답 대기 초 (기본 180)

                # analyze (소스 업로드 후 질문):
                "notebook_id": str,
                "news_text": str,          # 업로드할 텍스트 내용
                "prompt": str,
                "source_title": str,       # 소스 제목 (기본 "뉴스 모음")
                "clear_sources": bool,     # 기존 소스 삭제 여부 (기본 True)
                "source_timeout": int,     # 소스 처리 대기 초 (기본 120)
                "ask_timeout": int,        # 분석 대기 초 (기본 300)
            }

        Returns:
            {"result": str, "operation": str, "success": bool}
        """
        operation = data.get("operation", "ask")
        if operation == "ask":
            return asyncio.run(self._ask(data))
        elif operation == "analyze":
            return asyncio.run(self._analyze_with_source(data))
        return {"error": "잘못된 operation (ask 또는 analyze)", "success": False}

    async def _ask(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """기존 노트북에 직접 질문"""
        notebook_id = data["notebook_id"]
        prompt = data["prompt"]
        timeout = data.get("ask_timeout", 180)
        try:
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                result = await asyncio.wait_for(
                    client.chat.ask(notebook_id, prompt),
                    timeout=timeout
                )
                answer = result.answer if hasattr(result, "answer") else str(result)
                return {
                    "result": _remove_citations(answer),
                    "operation": "ask",
                    "success": True
                }
        except asyncio.TimeoutError:
            return {"error": f"응답 시간 초과 ({timeout}초)", "operation": "ask", "success": False}
        except Exception as e:
            return {"error": str(e), "operation": "ask", "success": False}

    async def _analyze_with_source(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """텍스트 소스 업로드 후 질문"""
        notebook_id = data["notebook_id"]
        news_text = data["news_text"]
        prompt = data["prompt"]
        source_title = data.get("source_title", "뉴스 모음")
        clear_sources = data.get("clear_sources", True)
        source_timeout = data.get("source_timeout", 120)
        ask_timeout = data.get("ask_timeout", 300)
        try:
            from notebooklm import NotebookLMClient
            async with await NotebookLMClient.from_storage() as client:
                if clear_sources:
                    try:
                        existing = await client.sources.list(notebook_id)
                        for src in existing:
                            await client.sources.delete(notebook_id, src.id)
                        print(f"  기존 소스 {len(existing)}개 삭제")
                    except Exception as e:
                        print(f"  소스 삭제 (무시): {e}")

                source = await client.sources.add_text(notebook_id, source_title, news_text)
                print("  텍스트 소스 1개 추가 완료")

                try:
                    await asyncio.wait_for(
                        client.sources.wait_for_sources(notebook_id, [source.id]),
                        timeout=source_timeout
                    )
                    print("  소스 처리 완료")
                except asyncio.TimeoutError:
                    print("  소스 처리 타임아웃 (계속 진행)")
                except Exception:
                    await asyncio.sleep(10)

                print("  분석 요청 중... (최대 5분)")
                result = await asyncio.wait_for(
                    client.chat.ask(notebook_id, prompt),
                    timeout=ask_timeout
                )
                answer = result.answer if hasattr(result, "answer") else str(result)
                return {
                    "result": _remove_citations(answer),
                    "operation": "analyze",
                    "success": True
                }
        except asyncio.TimeoutError:
            return {"error": f"분석 시간 초과 ({ask_timeout}초)", "operation": "analyze", "success": False}
        except Exception as e:
            return {"error": str(e), "operation": "analyze", "success": False}
