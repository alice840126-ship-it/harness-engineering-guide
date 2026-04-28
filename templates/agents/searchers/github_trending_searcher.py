#!/usr/bin/env python3
"""GitHub Trending 스크래퍼 (인증 없음, HTML 파싱)"""
import requests
from bs4 import BeautifulSoup


def get_trending(language: str = "python", since: str = "daily", limit: int = 8) -> list:
    """GitHub Trending 레포 수집"""
    try:
        url = f"https://github.com/trending/{language}?since={since}"
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=12,
        )
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        repos = soup.select("article.Box-row")[:limit]
        results = []
        for repo in repos:
            name_el = repo.select_one("h2 a")
            desc_el = repo.select_one("p")
            stars_el = repo.select_one("a[href$='/stargazers']")
            if not name_el:
                continue
            path = name_el.get("href", "").strip("/")
            results.append({
                "title": path.replace("/", " / "),
                "url": f"https://github.com/{path}",
                "description": desc_el.get_text(strip=True)[:200] if desc_el else "",
                "score": stars_el.get_text(strip=True).replace(",", "") if stars_el else "0",
                "source": "github_trending",
            })
        return results
    except Exception as e:
        print(f"[github_trending] 실패: {e}")
        return []


def search(query: str, limit: int = 6) -> list:
    """Python + 전체 언어 trending 중 키워드 매칭"""
    all_repos = get_trending("python", limit=25) + get_trending("", limit=15)
    query_lower = query.lower()
    matched = [
        r for r in all_repos
        if query_lower in (r["title"] + " " + r.get("description", "")).lower()
    ]
    # 매칭 없으면 Python trending 상위 반환
    return matched[:limit] if matched else get_trending("python", limit=limit)
