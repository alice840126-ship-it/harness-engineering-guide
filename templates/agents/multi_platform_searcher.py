#!/usr/bin/env python3
"""
다중 플랫폼 검색 에이전트 v2 (BaseAgent 기반)

네이버/Reddit/GitHub/X 통합 검색
- 단일 책임: 다중 플랫폼 검색만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import os
import re
import requests
from typing import Dict, List, Optional, Any
from base_agent import BaseAgent


class MultiPlatformSearcher(BaseAgent):
    """다중 플랫폼 검색 에이전트 v2"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정 (naver_client_id, naver_client_secret, timeout)
        """
        super().__init__("multi_platform_searcher", config)

        self.naver_client_id = self.config.get("naver_client_id") or os.getenv('NAVER_CLIENT_ID')
        self.naver_client_secret = self.config.get("naver_client_secret") or os.getenv('NAVER_CLIENT_SECRET')
        self.timeout = self.config.get("timeout", 10)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        operation = data.get("operation", "naver")

        if operation == "naver":
            return "keywords" in data
        else:
            return False

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        검색 처리

        Args:
            data: {
                "operation": str,       # "naver"
                "keywords": list,        # 검색어 리스트
                "limit": int,            # 최대 결과 수 (선택)
                "sort": str,             # 정렬 방식 (선택)
                "korean_only": bool      # 한글만 (선택)
            }

        Returns:
            {"results": list, "count": int, "operation": str}
        """
        operation = data.get("operation", "naver")

        if operation == "naver":
            return self._search_naver(data)
        else:
            return {"error": "잘못된 operation"}

    def _search_naver(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """네이버 웹문서 검색"""
        keywords = data["keywords"]
        limit = data.get("limit", 10)
        sort = data.get("sort", "sim")
        korean_only = data.get("korean_only", False)

        if not self.naver_client_id or not self.naver_client_secret:
            return {
                "results": [],
                "error": "네이버 API 키 없음",
                "operation": "naver"
            }

        results = []

        for keyword in keywords[:3]:
            try:
                url = "https://openapi.naver.com/v1/search/webkr.json"
                headers = {
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret
                }
                params = {
                    "query": keyword,
                    "display": limit,
                    "sort": sort
                }

                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
                response.raise_for_status()

                data_json = response.json()
                items = data_json.get('items', [])

                for item in items:
                    title = item.get('title', '')
                    description = item.get('description', '')
                    link = item.get('link', '')

                    # 한글 필터링
                    if korean_only and not self.is_korean(title + description):
                        continue

                    results.append({
                        "title": title,
                        "url": link,
                        "description": description,
                        "keyword": keyword
                    })

            except Exception as e:
                continue

        return {
            "results": results,
            "count": len(results),
            "operation": "naver"
        }

    def is_korean(self, text: str) -> bool:
        """한글 포함 여부 확인"""
        return bool(re.search(r'[가-힣]', text))
