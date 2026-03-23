#!/usr/bin/env python3
"""아침 뉴스 - 매일 07:00 RSS+Naver 4섹션 + 미국증시 + 자비스 통찰 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

import re
import requests
import feedparser
from datetime import datetime
from telegram_sender import TelegramSender
from news_scraper_v2 import NewsScraper

YNA_ECONOMY_RSS = "https://www.yna.co.kr/rss/economy.xml"

SECTION_KEYWORDS = {
    "부동산":    ["부동산", "아파트", "주택", "임대", "오피스텔", "지식산업센터", "분양", "전세", "매매", "청약"],
    "금융/기업": ["금리", "증시", "주가", "코스피", "코스닥", "금융", "기업", "실적", "투자", "채권", "환율"],
    "산업/건설": ["건설", "산업", "반도체", "AI", "인공지능", "기술", "배터리", "수출", "제조"],
    "주거/트렌드": ["주거", "생활", "소비", "물가", "트렌드", "상권", "유통", "리테일"],
}

INSIGHTS = [
    "지식산업센터 수요는 중소기업 성장과 직결됩니다. 공급 과잉 지역보다 수요 집중 지역을 선별하는 안목이 승패를 가릅니다.",
    "금리 흐름이 곧 부동산 흐름입니다. 오늘의 뉴스가 내일의 가격에 반영된다는 걸 잊지 마세요.",
    "AI가 산업을 재편하는 속도가 빨라지고 있습니다. 기술 트렌드를 부동산 입지와 연결해서 보는 시각이 필요합니다.",
    "공급과 수요의 사이클을 파악하면 시장의 방향이 보입니다. 오늘도 데이터로 판단하세요.",
    "전통적인 오피스 수요가 지식산업센터로 이동하는 흐름이 가속화되고 있습니다. 선점이 핵심입니다.",
    "부동산 규제 완화는 시장 회복의 신호탄이 될 수 있습니다. 정책 방향을 면밀히 모니터링하세요.",
    "기업의 이익이 늘면 결국 부동산 수요로 이어집니다. 오늘 기업 뉴스가 내일의 시장입니다.",
    "정보의 속도가 수익의 속도입니다. 오늘 뉴스를 먼저 읽는 사람이 시장을 먼저 읽습니다.",
    "거시경제 흐름과 미시적 물건 분석, 두 가지 시각을 모두 갖춰야 진짜 전문가입니다.",
    "중소기업 경기가 살아나면 지식산업센터 임대 수요가 먼저 반응합니다. 선행 지표를 주목하세요.",
    "글로벌 AI 투자 확대는 데이터센터와 첨단 산업단지 수요 증가로 이어집니다. 수혜 지역을 선별하세요.",
    "금리 인하 기대와 인플레이션 우려가 공존하는 시장, 현금 흐름이 탄탄한 자산이 답입니다.",
    "반도체·배터리·AI 클러스터 인근 지식산업센터는 장기 수요가 보장됩니다. 입지가 곧 미래입니다.",
    "부동산 시장은 결국 사람이 모이는 곳을 따라갑니다. 일자리와 인프라가 집중되는 지역을 주목하세요.",
    "공인중개사 시험도 부동산 시장 흐름을 이해하는 실전 지식이 기반입니다. 공부가 곧 실력입니다.",
    "좋은 물건은 항상 먼저 사라집니다. 정보를 빨리 얻는 것이 좋은 딜을 만드는 첫걸음입니다.",
    "시장이 어려울 때 공부하는 사람이 회복기에 가장 큰 수익을 냅니다.",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_all_rss(max_items: int = 120) -> list:
    """연합뉴스 경제 RSS 전체 수집"""
    try:
        res = requests.get(YNA_ECONOMY_RSS, timeout=10, verify=False, headers=HEADERS)
        feed = feedparser.parse(res.content)
        return [clean(entry.get("title", "")) for entry in feed.entries[:max_items] if entry.get("title")]
    except Exception as e:
        print(f"RSS 수집 오류: {e}")
        return []


def filter_by_keywords(all_titles: list, keywords: list, max_items: int = 5) -> list:
    """키워드 기반 필터링"""
    results = []
    seen = set()
    for title in all_titles:
        if any(kw in title for kw in keywords) and title not in seen:
            seen.add(title)
            results.append(title)
            if len(results) >= max_items:
                break
    return results


def fetch_naver_news(query: str, display: int = 5) -> list:
    """Naver API 폴백 (하네스 에이전트 사용)"""
    scraper = NewsScraper(config={
        "naver_client_id": NAVER_CLIENT_ID,
        "naver_client_secret": NAVER_CLIENT_SECRET,
    })
    result = scraper.run({"operation": "scrape", "query": query, "display": display})
    return [item.get("title", "") for item in result.get("articles", [])]


def get_section_news(section: str, all_rss: list) -> list:
    """RSS 필터링 → 부족하면 Naver API로 보충"""
    keywords = SECTION_KEYWORDS[section]
    titles = filter_by_keywords(all_rss, keywords, 5)
    if len(titles) < 3:
        naver_query = " ".join(keywords[:3])
        titles = fetch_naver_news(naver_query, 5)
    return titles


def fetch_us_market() -> str:
    indices = [("S&P 500", "^spx"), ("NASDAQ", "^ndq"), ("DOW JONES", "^dji")]
    results = []
    for name, symbol in indices:
        try:
            url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcvn&h&e=csv"
            res = requests.get(url, timeout=10, verify=False)
            rows = res.text.strip().split("\n")
            if len(rows) >= 2:
                cols = rows[1].split(",")
                open_p, close_p = float(cols[3]), float(cols[6])
                chg = ((close_p - open_p) / open_p) * 100
                arrow = "▲" if chg >= 0 else "▼"
                results.append(f"{arrow} {name}: {close_p:,.2f} ({chg:+.2f}%)")
        except Exception:
            results.append(f"• {name}: 조회 불가")
    return "\n".join(results) if results else "미국증시 데이터 없음"


def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    today_str = now.strftime("%Y-%m-%d")
    lines = [f"⚛️ 경자방 아침 뉴스 리포트 ({today_str})\n"]

    all_rss = fetch_all_rss()
    print(f"RSS 수집: {len(all_rss)}개")

    sections = [
        ("🏘 부동산",    "부동산"),
        ("💰 금융/기업", "금융/기업"),
        ("🏭 산업/건설", "산업/건설"),
        ("🏡 주거/트렌드", "주거/트렌드"),
    ]

    for label, key in sections:
        titles = get_section_news(key, all_rss)
        lines.append(f"\n{label}")
        if titles:
            for i, title in enumerate(titles, 1):
                lines.append(f"{i}. {title}")
        else:
            lines.append("뉴스 수집 실패")

    lines.append(f"\n💰 전날 미국증시")
    lines.append(fetch_us_market())

    insight = INSIGHTS[now.timetuple().tm_yday % len(INSIGHTS)]
    lines.append(f'\n💡 자비스의 한 줄 통찰')
    lines.append(f'"{insight}"')
    lines.append(f"\n오늘도 형님의 승리하는 하루를 응원합니다! ⚛️")

    message = "\n".join(lines)
    if len(message) > 4096:
        message = message[:4090] + "\n..."

    success = sender.send_message(message)
    print(f"아침 뉴스 전송: {'성공' if success else '실패'}")


if __name__ == "__main__":
    main()
