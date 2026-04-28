#!/usr/bin/env python3
"""
X(트위터) 검색
- 기본: DuckDuckGo (야간 데몬 안정적)
- 선택: Chrome AppleScript (사용자 로그인 세션, 실시간)
- 최후: ntscraper (Nitter 기반, 대부분 불안정)
"""
import subprocess
import requests
from bs4 import BeautifulSoup


def search_ddg(query: str, limit: int = 8) -> list:
    """DuckDuckGo로 X 콘텐츠 검색 (가장 안정적)"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": f"site:twitter.com {query}", "kl": "us-en"},
            headers=headers,
            timeout=12,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for result in soup.select(".result")[:limit]:
            title_el = result.select_one(".result__title")
            url_el = result.select_one(".result__url")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": url_el.get_text(strip=True) if url_el else "",
                    "source": "twitter_ddg",
                })
        return results
    except Exception as e:
        print(f"[x_searcher ddg] 실패: {e}")
        return []


def search_chrome(query: str, limit: int = 8) -> list:
    """
    Chrome AppleScript으로 X 실시간 검색 (로그인 세션 활용).
    Chrome이 닫혀있거나 세션 만료 시 조용히 빈 배열 반환.
    사전 조건: Chrome > 보기 > 개발자 > Allow JavaScript from Apple Events 활성화
    """
    import urllib.parse
    encoded = urllib.parse.quote(query)
    url = f"https://x.com/search?q={encoded}&f=live"

    script = (
        'tell application "Google Chrome"\n'
        '    make new window\n'
        '    delay 2\n'
        f'    set URL of active tab of front window to "{url}"\n'
        '    delay 12\n'
        f'    set tweetData to execute active tab of front window javascript '
        '"Array.from(document.querySelectorAll(\'[data-testid=\\"tweetText\\"]\'))'
        f'.slice(0,{limit}).map(t=>t.innerText.replace(/\\\\n/g,\' \').substring(0,200)).join(\'|||\')"\n'
        '    close front window\n'
        '    return tweetData\n'
        'end tell\n'
    )
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        texts = [t.strip() for t in proc.stdout.strip().split("|||") if t.strip()]
        return [{"title": t, "url": f"https://x.com/search?q={encoded}", "source": "twitter_chrome"} for t in texts]
    except Exception as e:
        print(f"[x_searcher chrome] 실패: {e}")
        return []


def search_nitter(query: str, limit: int = 8) -> list:
    """ntscraper로 X 검색 (Nitter 인스턴스 기반, 대부분 불안정)"""
    try:
        from ntscraper import Nitter
        scraper = Nitter(log_level=0)
        result = scraper.get_tweets(query, mode="term", number=limit)
        tweets = result.get("tweets", [])
        return [
            {
                "title": t.get("text", "")[:200],
                "url": t.get("link", ""),
                "source": "twitter",
                "likes": t.get("stats", {}).get("likes", 0),
            }
            for t in tweets
            if t.get("text")
        ]
    except Exception as e:
        print(f"[x_searcher nitter] 실패: {e}")
        return []


def search(query: str, limit: int = 8) -> list:
    """DDG(기본, 안정) → Chrome(실시간, 조건부) → Nitter(최후)"""
    # DDG 먼저 (야간 안정성 최우선)
    results = search_ddg(query, limit)
    # Chrome으로 실시간 보완 (실패해도 무관)
    chrome_results = search_chrome(query, min(limit, 4))
    results.extend(chrome_results)
    # 그래도 없으면 Nitter
    if not results:
        results = search_nitter(query, limit)
    return results
