#!/usr/bin/env python3
"""주간/월간 뉴스 수집 + 테제 분석 템플릿 생성
- 주간: 일요일 09:00 → 50. 투자/02. 테제 분석/Weekly/
- 월간: 1일 09:00 → 50. 투자/02. 테제 분석/Monthly/
"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, VAULT_PATH

import re
import requests
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from telegram_sender import TelegramSender

QUERIES = [
    ("부동산/지식산업센터", "지식산업센터 부동산 매매 임대"),
    ("경제/금융",          "경제 금리 환율 증시 코스피"),
    ("AI/반도체",          "AI 인공지능 반도체 HBM 엔비디아"),
    ("지정학/국제",        "지정학 무역 미국 중국 이란 전쟁"),
]

KEYWORD_LIST = [
    "AI", "반도체", "금리", "부동산", "환율", "유가", "삼성전자", "SK하이닉스",
    "지식산업센터", "아파트", "인플레", "달러", "코스피", "이란", "HBM",
    "엔비디아", "무역", "청약", "전세", "규제", "투자", "수출"
]


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_naver_news(query: str, display: int = 10) -> list:
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    try:
        res = requests.get(url, headers=headers,
                           params={"query": query, "display": display, "sort": "date"},
                           timeout=10)
        res.raise_for_status()
        return res.json().get("items", [])
    except Exception as e:
        print(f"뉴스 오류 ({query}): {e}")
        return []


def extract_top_keywords(all_items: list, top_n: int = 5) -> list:
    counter = Counter()
    for item in all_items:
        title = clean(item.get("title", ""))
        for kw in KEYWORD_LIST:
            if kw in title:
                counter[kw] += 1
    return [kw for kw, _ in counter.most_common(top_n)]


def determine_period() -> tuple:
    now = datetime.now()
    if now.day == 1:
        return "monthly", now
    return "weekly", now


def get_week_range(now: datetime) -> tuple:
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def build_weekly_template(now: datetime, all_news: dict, top_keywords: list) -> str:
    week_start, week_end = get_week_range(now)
    date_range = f"{week_start.strftime('%m/%d')}_{week_end.strftime('%m/%d')}"
    kw_str = ", ".join(top_keywords) if top_keywords else "—"

    lines = [
        f"# {now.strftime('%Y년')} {date_range} 주간 분석: 구조적 변화의 흐름",
        f"",
        f"> **핵심 질문**",
        f'> "주식 차트를 넘어서, 이 흐름이 사회, 정치, 문화, 생활 방식을 어떻게 바꾸는가?"',
        f"",
        f"---",
        f"",
        f"## 🎯 깊은 통찰: 표면 뒤에 숨겨진 진짜 이야기",
        f"> **분석 프레임워크:** 표면적 사건 → 진짜 타겟 → 숨겨진 의도",
        f"",
        f"---",
        f"",
        f"## 📊 이번 주 주요 키워드",
        f"",
        f"**{kw_str}**",
        f"",
        f"---",
        f"",
    ]

    # 수집된 뉴스 섹션별 나열
    ref_n = 1
    for label, items in all_news.items():
        lines.append(f"## 📌 {label} ({len(items)}건)")
        lines.append("")
        for item in items:
            title = clean(item.get("title", ""))
            link = item.get("link", "")
            lines.append(f"[{ref_n}] {title}")
            lines.append(f"   - {link}")
            ref_n += 1
        lines.append("")

    lines += [
        "---",
        "",
        "## 🔍 핵심 키워드 1: (이번 주 가장 중요한 흐름)",
        "",
        "### 1층: 표면적 사건 (Surface)",
        "- ",
        "",
        "### 2층: 진짜 타겟 (Real Target)",
        "- ",
        "",
        "### 3층: 숨겨진 의도 (Hidden Agenda)",
        "- ",
        "",
        "---",
        "",
        "## 🔍 핵심 키워드 2: ",
        "",
        "### 1층: 표면적 사건 (Surface)",
        "- ",
        "",
        "### 2층: 진짜 타겟 (Real Target)",
        "- ",
        "",
        "### 3층: 숨겨진 의도 (Hidden Agenda)",
        "- ",
        "",
        "---",
        "",
        "## 🔍 핵심 키워드 3: ",
        "",
        "### 1층: 표면적 사건 (Surface)",
        "- ",
        "",
        "### 2층: 진짜 타겟 (Real Target)",
        "- ",
        "",
        "### 3층: 숨겨진 의도 (Hidden Agenda)",
        "- ",
        "",
        "---",
        "",
        "## 💡 최종 인사이트",
        "",
        '**"이 모든 파도의 출발점은 누구인가?"**',
        "",
        "**[핵심 통찰 한 줄 요약]**",
        '**""**',
        "",
        "---",
        "",
        f"**분석일:** {now.strftime('%Y년 %m월 %d일')}",
        "**기반:** NotebookLM 깊은 통찰 분석",
        "**목적:** 투자를 넘어선 사회적 흐름에 대한 통찰",
        "",
        "---",
    ]
    return "\n".join(lines)


def build_monthly_template(now: datetime, all_news: dict, top_keywords: list) -> str:
    kw_str = ", ".join(top_keywords) if top_keywords else "—"

    lines = [
        f"# {now.strftime('%Y년 %m월')} 월간 분석: 구조적 변화의 흐름",
        f"",
        f"> **핵심 질문**",
        f'> "지난 한 달, 어떤 구조적 변화가 시작되었는가?"',
        f"",
        f"---",
        f"",
        f"## 🎯 깊은 통찰: 표면 뒤에 숨겨진 진짜 이야기",
        f"> **분석 프레임워크:** 표면적 사건 → 진짜 타겟 → 숨겨진 의도",
        f"",
        f"---",
        f"",
        f"## 📊 이달 주요 키워드",
        f"",
        f"**{kw_str}**",
        f"",
        f"---",
        f"",
    ]

    ref_n = 1
    for label, items in all_news.items():
        lines.append(f"## 📌 {label} ({len(items)}건)")
        lines.append("")
        for item in items:
            title = clean(item.get("title", ""))
            link = item.get("link", "")
            lines.append(f"[{ref_n}] {title}")
            lines.append(f"   - {link}")
            ref_n += 1
        lines.append("")

    lines += [
        "---",
        "",
        "## 🔍 월간 분석 프레임워크: 3층 구조 깊은 통찰",
        "",
        "### 1. 주요 키워드: ",
        "1. **표면적 사건 (Surface):** ",
        "2. **진짜 타겟 (Real Target):** ",
        "3. **숨겨진 의도 (Hidden Agenda):** ",
        "4. **3개월 후, 1년 후 영향:**",
        "   * **3개월 후:** ",
        "   * **1년 후:** ",
        "",
        "### 2. 주요 키워드: ",
        "1. **표면적 사건 (Surface):** ",
        "2. **진짜 타겟 (Real Target):** ",
        "3. **숨겨진 의도 (Hidden Agenda):** ",
        "4. **3개월 후, 1년 후 영향:**",
        "   * **3개월 후:** ",
        "   * **1년 후:** ",
        "",
        "### 3. 주요 키워드: ",
        "1. **표면적 사건 (Surface):** ",
        "2. **진짜 타겟 (Real Target):** ",
        "3. **숨겨진 의도 (Hidden Agenda):** ",
        "4. **3개월 후, 1년 후 영향:**",
        "   * **3개월 후:** ",
        "   * **1년 후:** ",
        "",
        "---",
        "",
        "## 🧭 월간 분석의 핵심 질문",
        "",
        "**1. 주도권 누구에게?:**",
        "",
        "**2. 구조적 변화:**",
        "",
        "**3. 선택 강요의 딜레마:**",
        "",
        "---",
        "",
        "## 💡 최종 월간 인사이트",
        "",
        '**"이 모든 파도의 출발점은 누구인가?"**',
        "",
        "**🔥 이달의 깊은 통찰 한 문장:**",
        "",
        '**""**',
        "",
        "---",
        "",
        f"## 📌 3개월 후, 1년 후 전망",
        "",
        "### 3개월 후",
        "- ",
        "",
        "### 1년 후",
        "- ",
        "",
        "---",
        "",
        f"**분석일:** {now.strftime('%Y년 %m월 %d일')}",
        "**기반:** NotebookLM 월간 깊은 통찰 분석 (지난 30일)",
        "**목적:** 투자를 넘어선 사회적 흐름에 대한 통찰",
        "",
        "---",
    ]
    return "\n".join(lines)


def save_to_obsidian(period: str, content: str, now: datetime) -> str:
    vault = Path(VAULT_PATH)
    week_start, week_end = get_week_range(now)

    if period == "monthly":
        folder = vault / "50. 투자" / "02. 테제 분석" / "Monthly" / str(now.year)
        filename = f"{now.strftime('%Y-%m-%d')}_월간분석_구조적변화.md"
    else:
        folder = vault / "50. 투자" / "02. 테제 분석" / "Weekly" / str(now.year)
        ws = week_start.strftime('%Y-%m-%d')
        we = week_end.strftime('%m-%d')
        filename = f"{ws}_{we}_주간분석_구조적변화.md"

    folder.mkdir(parents=True, exist_ok=True)
    note_path = folder / filename
    note_path.write_text(content, encoding="utf-8")
    print(f"✅ 저장: {note_path}")
    return str(note_path)


def main():
    now = datetime.now()
    period, _ = determine_period()
    period_label = "월간" if period == "monthly" else "주간"
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    print(f"📰 {period_label} 뉴스 수집 + 테제 분석 템플릿 생성...")

    all_news = {}
    all_items = []
    for label, query in QUERIES:
        items = fetch_naver_news(query, 10)
        if items:
            all_news[label] = items
            all_items.extend(items)

    top_keywords = extract_top_keywords(all_items, 5)
    total = len(all_items)

    if period == "monthly":
        content = build_monthly_template(now, all_news, top_keywords)
    else:
        content = build_weekly_template(now, all_news, top_keywords)

    note_path = save_to_obsidian(period, content, now)

    # 텔레그램 알림
    kw_str = ", ".join(top_keywords) if top_keywords else "—"
    tg_msg = (
        f"📊 {period_label} 테제 분석 템플릿 생성 완료\n\n"
        f"총 {total}건 뉴스 수집\n"
        f"주요 키워드: {kw_str}\n\n"
        f"📁 옵시디언 저장 완료\n"
        f"→ 50. 투자/02. 테제 분석/{period_label.capitalize()}/\n\n"
        f"NotebookLM에서 뉴스 데이터 분석 후 채워주세요 ⚛️"
    )
    sender.send_message(tg_msg)


if __name__ == "__main__":
    main()
