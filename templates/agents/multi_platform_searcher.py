#!/usr/bin/env python3
"""
다중 플랫폼 검색 에이전트

네이버/Reddit/GitHub/X 통합 검색
한글 필터링 옵션 지원
"""

import os
import re
import random
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiPlatformSearcher:
    """다중 플랫폼 검색 에이전트"""

    def __init__(
        self,
        naver_client_id: Optional[str] = None,
        naver_client_secret: Optional[str] = None,
        timeout: int = 10
    ):
        """
        초기화

        Args:
            naver_client_id: 네이버 API 클라이언트 ID
            naver_client_secret: 네이버 API 클라이언트 시크릿
            timeout: 요청 타임아웃 (초)
        """
        self.naver_client_id = naver_client_id or os.getenv('NAVER_CLIENT_ID')
        self.naver_client_secret = naver_client_secret or os.getenv('NAVER_CLIENT_SECRET')
        self.timeout = timeout

    def is_korean(self, text: str) -> bool:
        """
        한글 포함 여부 확인

        Args:
            text: 확인할 텍스트

        Returns:
            한글 포함 여부
        """
        return bool(re.search(r'[가-힣]', text))

    def search_naver_webkr(
        self,
        keywords: List[str],
        limit: int = 10,
        sort: str = "sim"
    ) -> List[Dict[str, str]]:
        """
        네이버 웹문서 검색

        Args:
            keywords: 검색어 리스트
            limit: 최대 결과 수
            sort: 정렬 방식 (sim: 유사도, date: 날짜)

        Returns:
            [{title, url, description}] 리스트
        """
        if not self.naver_client_id or not self.naver_client_secret:
            logger.warning("⚠️ 네이버 API 키 없음")
            return []

        results = []

        for keyword in keywords[:3]:  # 최대 3개 키워드
            try:
                url = "https://openapi.naver.com/v1/search/webkr.json"
                headers = {
                    "X-Naver-Client-Id": self.naver_client_id,
                    "X-Naver-Client-Secret": self.naver_client_secret
                }
                params = {
                    "query": keyword,
                    "display": min(limit, 100),
                    "sort": sort
                }

                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])

                    for item in items:
                        title = item.get("title", "")
                        # HTML 태그 제거
                        title = re.sub(r'<[^>]+>', '', title)
                        title = html_unescape(title)

                        link = item.get("link", "")
                        description = item.get("description", "")

                        if title and link:
                            results.append({
                                "title": title,
                                "url": link,
                                "description": description,
                                "source": "네이버"
                            })

                        if len(results) >= limit:
                            break

                if len(results) >= limit:
                    break

            except Exception as e:
                logger.error(f"⚠️ 네이버 검색 실패 ({keyword}): {e}")

        logger.info(f"🔍 네이버 검색: {len(results)}개")
        return results

    def search_reddit(
        self,
        subreddits: List[str],
        limit: int = 10,
        filter_korean: bool = True
    ) -> List[Dict[str, str]]:
        """
        Reddit 검색

        Args:
            subreddits: 서브레딧 리스트 (예: ["Python", "programming"])
            limit: 최대 결과 수
            filter_korean: 한글만 필터링

        Returns:
            [{title, url, description, source}] 리스트
        """
        results = []
        headers = {'User-agent': 'ClaudeCode/1.0'}

        for subreddit in subreddits[:3]:  # 최대 3개 서브레딧
            try:
                url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50"
                response = requests.get(url, headers=headers, timeout=self.timeout)

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", {}).get("children", [])

                    for post in posts:
                        post_data = post.get("data", {})
                        title = post_data.get("title", "")
                        url = post_data.get("url", "")
                        selftext = post_data.get("selftext", "")
                        score = post_data.get("score", 0)

                        # 한글 필터링
                        if filter_korean and not self.is_korean(title):
                            continue

                        if title and url:
                            results.append({
                                "title": title,
                                "url": url,
                                "description": selftext[:150] if selftext else f"↑ {score} points",
                                "source": f"r/{subreddit}"
                            })

                        if len(results) >= limit:
                            break

                if len(results) >= limit:
                    break

            except Exception as e:
                logger.error(f"⚠️ Reddit 검색 실패 (r/{subreddit}): {e}")

        logger.info(f"🔴 Reddit 검색: {len(results)}개")
        return results

    def search_github(
        self,
        keywords: List[str],
        limit: int = 10,
        filter_korean: bool = True
    ) -> List[Dict[str, str]]:
        """
        GitHub 저장소 검색

        Args:
            keywords: 검색어 리스트
            limit: 최대 결과 수
            filter_korean: 한글 설명만 필터링

        Returns:
            [{title, url, description, source}] 리스트
        """
        results = []
        headers = {'Accept': 'application/vnd.github.v3+json'}

        for keyword in keywords[:3]:  # 최대 3개 키워드
            try:
                url = f"https://api.github.com/search/repositories"
                params = {
                    "q": keyword,
                    "sort": "stars",
                    "per_page": min(limit * 2, 100)  # 여유있게 가져오기
                }
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)

                if response.status_code == 200:
                    data = response.json()
                    repos = data.get("items", [])

                    for repo in repos:
                        name = repo.get("full_name", "")
                        url = repo.get("html_url", "")
                        description = repo.get("description", "")

                        # 한글 필터링
                        if filter_korean and description and not self.is_korean(description):
                            continue

                        if name and url:
                            results.append({
                                "title": name,
                                "url": url,
                                "description": description or "설명 없음",
                                "source": "GitHub"
                            })

                        if len(results) >= limit:
                            break

                if len(results) >= limit:
                    break

            except Exception as e:
                logger.error(f"⚠️ GitHub 검색 실패 ({keyword}): {e}")

        logger.info(f"🐙 GitHub 검색: {len(results)}개")
        return results

    def search_x(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, str]]:
        """
        X (트위터) 검색 (Nitter 공개 인스턴스 사용)

        Args:
            query: 검색어
            limit: 최대 결과 수

        Returns:
            [{title, url, description, source}] 리스트
        """
        results = []

        try:
            # 공개 Nitter 인스턴스 (무작위 선택)
            instances = [
                "nitter.net",
                "nitter.poast.org",
                "nitter.privacydev.net",
                "nitter.mint.lgbt"
            ]
            instance = random.choice(instances)

            url = f"https://{instance}/search?q={query}&f=tweets"
            headers = {'User-agent': 'ClaudeCode/1.0'}

            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                content = response.text

                # 한글 패턴 찾기 (간소화)
                korean_pattern = r'([가-힣]+.{1,100}[가-힣]+)'
                matches = re.findall(korean_pattern, content)

                if matches:
                    # URL 추출 (간소화)
                    urls = re.findall(r'href="/([^/]+)/status/\d+', content)

                    for i, text in enumerate(matches[:limit]):
                        if i < len(urls):
                            tweet_url = f"https://x.com/{urls[i]}"
                            results.append({
                                "title": text[:100] + "..." if len(text) > 100 else text,
                                "url": tweet_url,
                                "description": "트윗",
                                "source": "X"
                            })

        except Exception as e:
            logger.warning(f"⚠️ Nitter 검색 실패 (무시): {e}")

        logger.info(f"🐦 X 검색: {len(results)}개")
        return results

    def search_all(
        self,
        platforms: List[str],
        params: Dict[str, any],
        limit_per_platform: int = 5
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        여러 플랫폼 통합 검색

        Args:
            platforms: 플랫폼 리스트 (naver, reddit, github, x)
            params: 검색 파라미터
                - naver_keywords: 네이버 검색어
                - reddit_subreddits: 레딧 서브레딧
                - github_keywords: 깃허브 검색어
                - x_query: X 검색어
            limit_per_platform: 플랫폼별 최대 결과 수

        Returns:
            {platform: [{title, url, ...}]} 딕셔너리
        """
        results = {}

        if "naver" in platforms:
            keywords = params.get("naver_keywords", [])
            if keywords:
                results["naver"] = self.search_naver_webkr(keywords, limit_per_platform)

        if "reddit" in platforms:
            subreddits = params.get("reddit_subreddits", [])
            if subreddits:
                results["reddit"] = self.search_reddit(subreddits, limit_per_platform)

        if "github" in platforms:
            keywords = params.get("github_keywords", [])
            if keywords:
                results["github"] = self.search_github(keywords, limit_per_platform)

        if "x" in platforms:
            query = params.get("x_query", "")
            if query:
                results["x"] = self.search_x(query, limit_per_platform)

        return results


def html_unescape(text: str) -> str:
    """
    HTML 엔티티 디코딩

    Args:
        text: 디코딩할 텍스트

    Returns:
        디코딩된 텍스트
    """
    import html
    return html.unescape(text)
