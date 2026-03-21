#!/usr/bin/env python3
"""
웹 콘텐츠 리더 에이전트 v2 (BaseAgent 기반)

웹페이지 본문 추출 (trafilatura 사용)
- 단일 책임: 웹 콘텐츠 읽기만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from base_agent import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebContentReader(BaseAgent):
    """웹 콘텐츠 리더 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (timeout, max_chars)
        """
        super().__init__("web_content_reader", config)

        self.timeout = self.config.get("timeout", 15)
        self.max_chars = self.config.get("max_chars", 2000)

        try:
            import trafilatura
            self.trafilatura = trafilatura
        except ImportError:
            self.trafilatura = None

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "read")

        if operation == "read":
            return "url" in data
        elif operation == "multiple":
            return "urls" in data
        elif operation == "html":
            return "html" in data
        elif operation == "metadata":
            return "url" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        웹 콘텐츠 읽기 처리

        Args:
            data: {
                "operation": str,           # "read", "multiple", "html", "metadata"
                "url": str,                 # read/metadata용
                "urls": list,               # multiple용
                "html": str,                # html용
                "include_comments": bool,   # 댓글 포함 (선택)
                "include_tables": bool,     # 표 포함 (선택)
                "skip_errors": bool         # multiple용 에러 스킵 (선택)
            }

        Returns:
            operation에 따른 결과
        """
        operation = data.get("operation", "read")

        if operation == "read":
            return self._read_content(data)
        elif operation == "multiple":
            return self._read_multiple(data)
        elif operation == "html":
            return self._extract_from_html(data)
        elif operation == "metadata":
            return self._get_metadata(data)
        else:
            return {"error": "잘못된 operation"}

    def _read_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """단일 URL 본문 추출"""
        url = data["url"]
        include_comments = data.get("include_comments", False)
        include_tables = data.get("include_tables", False)

        if not self.trafilatura:
            return {"content": None, "error": "trafilatura 없음"}

        if not self._is_valid_url(url):
            return {"content": None, "error": "유효하지 않은 URL"}

        try:
            downloaded = self.trafilatura.fetch_url(url, timeout=self.timeout)

            if not downloaded:
                return {"content": None, "error": "다운로드 실패"}

            content = self.trafilatura.extract(
                downloaded,
                include_comments=include_comments,
                include_tables=include_tables,
                no_fallback=False
            )

            if content:
                if len(content) > self.max_chars:
                    content = content[:self.max_chars]

                return {
                    "content": content,
                    "url": url,
                    "length": len(content),
                    "operation": "read"
                }
            else:
                return {"content": None, "error": "추출 실패"}

        except Exception as e:
            return {"content": None, "error": str(e)}

    def _read_multiple(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """여러 URL 일괄 본문 추출"""
        urls = data["urls"]
        include_comments = data.get("include_comments", False)
        include_tables = data.get("include_tables", False)
        skip_errors = data.get("skip_errors", True)

        results = []

        for url in urls:
            result = self._read_content({
                "url": url,
                "include_comments": include_comments,
                "include_tables": include_tables,
                "operation": "read"
            })

            status = "success" if result.get("content") else "failed"

            results.append({
                "url": url,
                "content": result.get("content"),
                "status": status
            })

            if not skip_errors and not result.get("content"):
                break

        success_count = sum(1 for r in results if r["status"] == "success")

        return {
            "results": results,
            "total_count": len(urls),
            "success_count": success_count,
            "operation": "multiple"
        }

    def _extract_from_html(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """HTML에서 본문 추출"""
        html = data["html"]

        if not self.trafilatura:
            return {"content": None, "error": "trafilatura 없음"}

        try:
            content = self.trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False
            )

            if content and len(content) > self.max_chars:
                content = content[:self.max_chars]

            return {
                "content": content,
                "length": len(content) if content else 0,
                "operation": "html"
            }

        except Exception as e:
            return {"content": None, "error": str(e)}

    def _get_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """웹페이지 메타데이터 추출"""
        url = data["url"]

        if not self.trafilatura:
            return {"metadata": None, "error": "trafilatura 없음"}

        try:
            downloaded = self.trafilatura.fetch_url(url, timeout=self.timeout)

            if not downloaded:
                return {"metadata": None, "error": "다운로드 실패"}

            metadata = self.trafilatura.extract_metadata(downloaded)

            if metadata:
                return {
                    "metadata": {
                        "title": metadata.title or "",
                        "author": metadata.author or "",
                        "date": metadata.date or "",
                        "url": url
                    },
                    "operation": "metadata"
                }

            return {"metadata": None, "error": "메타데이터 없음"}

        except Exception as e:
            return {"metadata": None, "error": str(e)}

    def _is_valid_url(self, url: str) -> bool:
        """URL 유효성 검사"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
