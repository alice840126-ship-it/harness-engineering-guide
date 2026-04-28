#!/usr/bin/env python3
"""
범용 웹 데이터 수집기

어떤 URL이든 Playwright headless로 렌더링 후 텍스트/테이블 추출.
사이트별 로직 없음 — Claude가 적절한 URL을 결정하고 이 스크립트에 전달.

사용법:
    python3 web_data_scraper.py "https://hogangnono.com/region/1144012700"
    python3 web_data_scraper.py "https://부동산플래닛.com/..." --table
    python3 web_data_scraper.py "https://kais.or.kr/..." --wait "table.data"
"""

import sys
import re
import argparse
from typing import Optional
from datetime import datetime

# Playwright는 선택적 의존성
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ playwright 미설치 — pip3 install playwright && python3 -m playwright install chromium")

# requests는 fallback용
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


def _wrap_if_needed(text: str, shield: bool, source: Optional[str]) -> str:
    """shield=True일 때만 injection_shield.wrap_external로 감싸기 (실패 시 원본 반환)"""
    if not shield:
        return text
    try:
        import sys as _sys
        _sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
        from injection_shield import wrap_external
        return wrap_external(text, source=source or "web")
    except Exception:
        return text


class WebDataScraper:
    """범용 웹 데이터 수집기 — Playwright headless + requests fallback"""

    def __init__(self, timeout: int = 30000):
        self.timeout = timeout

    def scrape(self, url: str, wait_selector: Optional[str] = None, extract_tables: bool = False,
               shield: bool = False, shield_source: Optional[str] = None) -> str:
        """URL 렌더링 후 텍스트 추출 (동적 사이트 포함)

        Args:
            url: 크롤링할 URL
            wait_selector: 특정 요소가 나타날 때까지 대기 (CSS selector)
            extract_tables: True면 <table> 요소만 추출
            shield: True면 반환 전에 injection_shield.wrap_external로 외부 데이터 격리
            shield_source: shield 래핑 시 source 라벨 (미지정 시 url)

        Returns:
            렌더링된 페이지의 텍스트 내용
        """
        if PLAYWRIGHT_AVAILABLE:
            text = self._scrape_with_playwright(url, wait_selector, extract_tables)
        elif REQUESTS_AVAILABLE:
            text = self._scrape_with_requests(url)
        else:
            text = "ERROR: playwright, requests 모두 미설치"
        return _wrap_if_needed(text, shield, shield_source or url)

    def _scrape_with_playwright(self, url: str, wait_selector: Optional[str] = None, extract_tables: bool = False) -> str:
        """Playwright headless로 동적 사이트 크롤링"""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=self.timeout)

                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=self.timeout)
                else:
                    page.wait_for_load_state("networkidle", timeout=self.timeout)
                    page.wait_for_timeout(2000)  # React 등 SPA 추가 렌더링 대기

                if extract_tables:
                    tables = page.query_selector_all("table")
                    result = []
                    for i, table in enumerate(tables):
                        text = table.inner_text()
                        if text.strip():
                            result.append(f"=== 테이블 {i+1} ===\n{text}")
                    if result:
                        text = "\n\n".join(result)
                    else:
                        text = page.inner_text("body")
                else:
                    text = page.inner_text("body")

                browser.close()
                return text

        except Exception as e:
            return f"ERROR: Playwright 크롤링 실패 — {str(e)}"

    def _scrape_with_requests(self, url: str) -> str:
        """requests fallback (정적 사이트만)"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        except Exception as e:
            return f"ERROR: requests 크롤링 실패 — {str(e)}"


def format_report(url: str, raw_text: str) -> str:
    """수집된 원시 데이터를 리포트 형식으로 포맷"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status = "성공" if not raw_text.startswith("ERROR") else "실패"

    report = f"""=== 웹 데이터 수집 결과 ===
URL: {url}
수집일시: {now}
상태: {status}

--- 수집 데이터 ---
{raw_text[:8000]}
{'... (8000자 초과 생략)' if len(raw_text) > 8000 else ''}
=== END ==="""

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="범용 웹 데이터 수집기 — URL을 주면 크롤링")
    parser.add_argument("url", help="크롤링할 URL")
    parser.add_argument("--table", action="store_true",
                        help="<table> 요소만 추출")
    parser.add_argument("--wait", default=None,
                        help="특정 CSS selector가 나타날 때까지 대기")
    parser.add_argument("--timeout", type=int, default=30000,
                        help="페이지 로딩 타임아웃 ms (default: 30000)")
    parser.add_argument("--raw", action="store_true",
                        help="리포트 포맷 없이 원시 텍스트만 출력")
    parser.add_argument("--shield", action="store_true",
                        help="injection_shield.wrap_external로 외부 데이터 격리 래핑")

    args = parser.parse_args()
    scraper = WebDataScraper(timeout=args.timeout)
    raw = scraper.scrape(args.url, wait_selector=args.wait, extract_tables=args.table,
                         shield=args.shield)

    if args.raw:
        print(raw)
    else:
        print(format_report(args.url, raw))
