#!/usr/bin/env python3
"""GeekNews 스크래퍼 (한국판 HN - news.hada.io, HTML 파싱)"""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


def get_latest(limit: int = 10) -> list:
    """GeekNews 메인 페이지 HTML에서 최신 글 수집"""
    try:
        r = requests.get("https://news.hada.io/", headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        # 외부 링크(기사 URL) + 바로 다음 topic 설명 텍스트 파싱
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if not href.startswith("http") or "news.hada.io" in href:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 5 or href in seen:
                continue
            seen.add(href)
            # 바로 뒤 sibling에서 설명 추출
            desc = ""
            nxt = a.find_next("a", href=lambda h: h and h.startswith("topic?id="))
            if nxt:
                desc = nxt.get_text(strip=True)[:200]
            results.append({
                "title": title,
                "url": href,
                "description": desc,
                "source": "geeknews",
            })
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print(f"[geeknews_searcher] 실패: {e}")
        return []


def search(query: str, limit: int = 6) -> list:
    """GeekNews에서 키워드 매칭"""
    all_items = get_latest(limit=50)
    query_lower = query.lower()
    matched = [
        item for item in all_items
        if query_lower in (item["title"] + " " + item.get("description", "")).lower()
    ]
    return matched[:limit] if matched else all_items[:limit]
