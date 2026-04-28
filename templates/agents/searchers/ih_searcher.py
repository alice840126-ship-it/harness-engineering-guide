#!/usr/bin/env python3
"""Indie Hackers 검색 - DuckDuckGo site: 검색 + 인터뷰 피드"""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def search(query: str, limit: int = 8) -> list:
    """DuckDuckGo로 Indie Hackers 콘텐츠 검색"""
    results = []

    # 인터뷰 검색
    results.extend(_ddg_search(f"site:indiehackers.com/interview {query}", limit // 2))
    # 포스트 검색
    results.extend(_ddg_search(f"site:indiehackers.com/post {query}", limit // 2))

    # 중복 제거
    seen = set()
    unique = []
    for r in results:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)
    return unique[:limit]


def _ddg_search(query: str, limit: int) -> list:
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "us-en"},
            headers=HEADERS,
            timeout=12,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for item in soup.select(".result")[:limit]:
            title_el = item.select_one(".result__title")
            snippet_el = item.select_one(".result__snippet")
            url_el = item.select_one("a.result__url")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "description": snippet_el.get_text(strip=True) if snippet_el else "",
                    "url": url_el.get("href", "") if url_el else "",
                    "source": "indiehackers",
                })
        return results
    except Exception as e:
        print(f"[ih_searcher ddg] 실패: {e}")
        return []


def get_recent_interviews(limit: int = 5) -> list:
    """최신 인터뷰 직접 수집"""
    try:
        r = requests.get(
            "https://www.indiehackers.com/interviews",
            headers=HEADERS,
            timeout=15,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for item in soup.select("a[href*='/interview/']")[:limit]:
            title = item.get_text(strip=True)
            if title and len(title) > 10:
                results.append({
                    "title": title,
                    "url": f"https://www.indiehackers.com{item.get('href', '')}",
                    "source": "indiehackers_interview",
                })
        return results
    except Exception as e:
        print(f"[ih_searcher interviews] 실패: {e}")
        return []
