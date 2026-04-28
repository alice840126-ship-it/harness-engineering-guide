#!/usr/bin/env python3
"""HackerNews 검색 - Algolia API (무료, 인증 없음)"""
import requests


def search(query: str, limit: int = 8) -> list:
    try:
        r = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": query,
                "tags": "story",
                "hitsPerPage": limit,
                "numericFilters": "points>15",
            },
            timeout=10,
        )
        hits = r.json().get("hits", [])
        return [
            {
                "title": h.get("title", ""),
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                "score": h.get("points", 0),
                "comments": h.get("num_comments", 0),
                "source": "hackernews",
            }
            for h in hits
            if h.get("title")
        ]
    except Exception as e:
        print(f"[hn_searcher] 실패: {e}")
        return []


def get_front_page(limit: int = 10) -> list:
    """HN 프런트페이지 최근 글 (쿼리 없이) — Algolia front_page 태그"""
    try:
        r = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "tags": "front_page",
                "hitsPerPage": limit,
            },
            timeout=10,
        )
        hits = r.json().get("hits", [])
        return [
            {
                "title": h.get("title", ""),
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                "score": h.get("points", 0),
                "comments": h.get("num_comments", 0),
                "source": "hackernews",
            }
            for h in hits
            if h.get("title")
        ]
    except Exception as e:
        print(f"[hn_searcher front_page] 실패: {e}")
        return []


# Show HN 전용 검색 (직접 만든 것들)
def search_show_hn(query: str, limit: int = 8) -> list:
    try:
        r = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={
                "query": f"Show HN {query}",
                "tags": "show_hn",
                "hitsPerPage": limit,
            },
            timeout=10,
        )
        hits = r.json().get("hits", [])
        return [
            {
                "title": h.get("title", ""),
                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                "score": h.get("points", 0),
                "source": "hackernews_show",
            }
            for h in hits
            if h.get("title")
        ]
    except Exception as e:
        print(f"[hn_searcher show_hn] 실패: {e}")
        return []
