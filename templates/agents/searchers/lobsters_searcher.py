#!/usr/bin/env python3
"""Lobsters 검색 - 공개 JSON API (인증 없음, HN 대안)"""
import requests


def search(query: str, limit: int = 6) -> list:
    """Lobsters 최신 글에서 키워드 매칭 (제목 기반)"""
    try:
        r = requests.get(
            "https://lobste.rs/newest.json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        items = r.json()
        query_lower = query.lower()
        results = []
        for item in items:
            title = item.get("title", "")
            desc = item.get("description", "")
            tags = " ".join(item.get("tags", []))
            if query_lower in (title + desc + tags).lower():
                results.append({
                    "title": title,
                    "url": item.get("url") or f"https://lobste.rs/s/{item.get('short_id','')}",
                    "description": desc[:200] if desc else "",
                    "score": item.get("score", 0),
                    "source": "lobsters",
                })
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print(f"[lobsters_searcher] 실패: {e}")
        return []


def get_top(limit: int = 8) -> list:
    """Lobsters 인기 글 수집"""
    try:
        r = requests.get(
            "https://lobste.rs/hottest.json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        items = r.json()[:limit]
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url") or f"https://lobste.rs/s/{item.get('short_id','')}",
                "description": "",
                "score": item.get("score", 0),
                "source": "lobsters",
            }
            for item in items
            if item.get("title")
        ]
    except Exception as e:
        print(f"[lobsters_searcher top] 실패: {e}")
        return []
