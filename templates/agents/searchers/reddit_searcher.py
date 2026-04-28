#!/usr/bin/env python3
"""Reddit 검색 - 공개 JSON API (인증 없음)"""
import time
import requests

# 형님 관심 영역 서브레딧 (자유롭게 탐색)
SUBREDDITS = "+".join([
    "selfhosted", "PKMS", "Entrepreneur", "financialindependence",
    "SideProject", "nocode", "digitalnomad", "Stoicism", "ObsidianMD",
    "running", "lifeprotips", "productivity", "passive_income",
    "personalfinance", "bodyweightfitness", "DecidingToBeBetter",
    "Parenting", "LifeAdvice", "RealEstate", "realestateinvesting",
])

# 실제 브라우저 UA (봇 차단 우회)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


def search(query: str, limit: int = 8) -> list:
    try:
        r = requests.get(
            f"https://www.reddit.com/r/{SUBREDDITS}/search.json",
            params={"q": query, "sort": "relevance", "t": "month", "limit": limit},
            headers=HEADERS,
            timeout=12,
        )
        if r.status_code == 429:
            print(f"[reddit_searcher] rate limited (429) — 스킵")
            return []
        if r.status_code != 200:
            print(f"[reddit_searcher] HTTP {r.status_code} — 스킵")
            return []
        posts = r.json().get("data", {}).get("children", [])
        return [
            {
                "title": p["data"].get("title", ""),
                "url": f"https://reddit.com{p['data'].get('permalink', '')}",
                "description": p["data"].get("selftext", "")[:200],
                "score": p["data"].get("score", 0),
                "subreddit": p["data"].get("subreddit", ""),
                "source": "reddit",
            }
            for p in posts
            if p["data"].get("title")
        ]
    except Exception as e:
        print(f"[reddit_searcher] 실패: {e}")
        return []


def top_posts(subreddit: str = "selfhosted", limit: int = 5) -> list:
    """특정 서브레딧 인기 글 수집"""
    try:
        time.sleep(1)  # rate limit 방어
        r = requests.get(
            f"https://www.reddit.com/r/{subreddit}/top.json",
            params={"t": "week", "limit": limit},
            headers=HEADERS,
            timeout=12,
        )
        if r.status_code != 200:
            return []
        posts = r.json().get("data", {}).get("children", [])
        return [
            {
                "title": p["data"].get("title", ""),
                "url": f"https://reddit.com{p['data'].get('permalink', '')}",
                "description": p["data"].get("selftext", "")[:200],
                "score": p["data"].get("score", 0),
                "subreddit": subreddit,
                "source": "reddit",
            }
            for p in posts
            if p["data"].get("title")
        ]
    except Exception as e:
        print(f"[reddit_searcher top] 실패: {e}")
        return []
