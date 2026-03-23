#!/usr/bin/env python3
"""저녁 브리핑 - 매일 17:50 RSS+Naver 4섹션 + 자비스 통찰 텔레그램 전송"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

import re
import requests
import feedparser
from datetime import datetime
from telegram_sender import TelegramSender

YNA_ECONOMY_RSS = "https://www.yna.co.kr/rss/economy.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

SECTION_KEYWORDS = {
    "기업/재무":  ["기업", "실적", "주주", "재무", "상장", "합병", "인수", "매출", "영업이익"],
    "주거/생활":  ["부동산", "아파트", "전세", "주택", "임대", "청약", "분양"],
    "산업/기술":  ["반도체", "AI", "인공지능", "기술", "배터리", "수출", "산업", "스타트업"],
    "경제일반":   ["금리", "환율", "물가", "인플레", "경기", "GDP", "무역", "수출입"],
}

EVENING_INSIGHTS = [
    "오늘 시장에서 움직인 자금의 방향을 파악했다면, 내일의 포지션이 보입니다.",
    "하루 동안 쌓인 정보를 정리하세요. 잡음을 걷어내면 핵심 신호가 남습니다.",
    "매물 정보는 아침에 나오고, 결정은 저녁에 합니다. 오늘 본 것을 내일 행동으로 연결하세요.",
    "시장의 공포가 클수록 기회도 큽니다. 오늘의 불안이 내일의 진입 타이밍일 수 있습니다.",
    "좋은 입지는 항상 수요가 앞섭니다. 오늘 파악한 수요 신호를 기억하세요.",
    "기업 실적이 개선되면 임대 수요도 따라옵니다. 오늘 기업 뉴스를 부동산 렌즈로 다시 보세요.",
    "장기 트렌드를 읽으면 단기 변동에 흔들리지 않습니다. 큰 그림을 유지하세요.",
    "오늘 하루도 시장을 공부했습니다. 축적된 지식이 곧 경쟁력입니다.",
    "정책 방향이 시장 방향을 선도합니다. 오늘 발표된 정책 뉴스를 꼭 확인하세요.",
    "부동산은 타이밍보다 입지입니다. 단기 등락보다 장기 가치를 봐야 합니다.",
    "AI와 자동화가 바꾸는 업무 공간, 지식산업센터의 미래는 더 밝습니다.",
    "투자는 감이 아닌 데이터입니다. 오늘 수집한 정보가 내일의 판단 근거가 됩니다.",
    "시장이 조정받을 때 좋은 물건이 나옵니다. 현금 준비와 정보 준비를 동시에 하세요.",
    "공인중개사 자격은 시장을 보는 눈을 날카롭게 합니다. 오늘 공부도 투자입니다.",
]

KEYWORD_INSIGHTS = {
    "금리": "금리 변동이 핵심입니다. 중앙은행 방향성을 주시하면 다음 달 시장이 보입니다.",
    "AI": "AI 기술 투자가 산업 지형을 바꾸고 있습니다. 수혜 지역 부동산에 주목하세요.",
    "반도체": "반도체 클러스터 인근 지식산업센터는 장기 수요가 확실합니다. 입지를 선점하세요.",
    "부동산": "부동산 시장 변화의 속도가 빨라지고 있습니다. 정보 우위가 곧 수익 우위입니다.",
    "인플레": "인플레이션 환경에서는 실물 자산이 방어막이 됩니다. 부동산의 가치는 유효합니다.",
    "규제": "규제 변화는 시장 재편의 신호입니다. 정책 방향을 먼저 읽는 사람이 이깁니다.",
    "공급": "공급 부족 지역이 곧 수익 지역입니다. 수급 불균형을 찾아내세요.",
}


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_all_rss() -> list:
    try:
        res = requests.get(YNA_ECONOMY_RSS, timeout=10, verify=False, headers=HEADERS)
        feed = feedparser.parse(res.content)
        return [clean(entry.get("title", "")) for entry in feed.entries[:120] if entry.get("title")]
    except Exception as e:
        print(f"RSS 수집 오류: {e}")
        return []


def filter_by_keywords(all_titles: list, keywords: list, max_items: int = 5) -> list:
    results, seen = [], set()
    for title in all_titles:
        if any(kw in title for kw in keywords) and title not in seen:
            seen.add(title)
            results.append(title)
            if len(results) >= max_items:
                break
    return results


def fetch_naver_news(query: str, display: int = 5) -> list:
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    try:
        res = requests.get(url, headers=headers, params={"query": query, "display": display, "sort": "date"}, timeout=10)
        return [clean(item.get("title", "")) for item in res.json().get("items", [])]
    except Exception:
        return []


def get_section_news(section: str, all_rss: list) -> list:
    keywords = SECTION_KEYWORDS[section]
    titles = filter_by_keywords(all_rss, keywords, 5)
    if len(titles) < 3:
        titles = fetch_naver_news(" ".join(keywords[:3]), 5)
    return titles


def build_insight(all_titles: list, now: datetime) -> str:
    combined = " ".join(all_titles)
    for kw, insight in KEYWORD_INSIGHTS.items():
        if kw in combined:
            return insight
    return EVENING_INSIGHTS[now.timetuple().tm_yday % len(EVENING_INSIGHTS)]


def main():
    now = datetime.now()
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    today_str = now.strftime("%Y-%m-%d")
    lines = [f"🌆 경자방 저녁 브리핑 ({today_str})\n"]

    all_rss = fetch_all_rss()
    print(f"RSS 수집: {len(all_rss)}개")

    sections = [
        ("🏢 기업/재무",  "기업/재무"),
        ("🏠 주거/생활",  "주거/생활"),
        ("⚙️ 산업/기술",  "산업/기술"),
        ("📊 경제일반",   "경제일반"),
    ]

    all_titles = []
    for label, key in sections:
        titles = get_section_news(key, all_rss)
        all_titles.extend(titles)
        lines.append(f"\n{label}")
        if titles:
            for i, title in enumerate(titles, 1):
                lines.append(f"{i}. {title}")
        else:
            lines.append("뉴스 수집 실패")

    insight = build_insight(all_titles, now)
    lines.append(f'\n💡 자비스의 한 줄 통찰')
    lines.append(f'"{insight}"')
    lines.append(f"\n오늘 하루도 수고하셨습니다, 형님! ⚛️")

    message = "\n".join(lines)
    if len(message) > 4096:
        message = message[:4090] + "\n..."

    success = sender.send_message(message)
    print(f"저녁 브리핑 전송: {'성공' if success else '실패'}")


if __name__ == "__main__":
    main()
