#!/usr/bin/env python3
"""주간/월간 뉴스 수집 → NotebookLM 3층 분석 → 옵시디언 저장
- 주간: 일요일 09:00
- 월간: 1일 09:00
"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, VAULT_PATH

import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from telegram_sender import TelegramSender
from news_scraper_v2 import NewsScraper
from news_analyzer_v2 import NewsAnalyzer
from obsidian_writer_v2 import ObsidianWriter
from notebooklm_analyzer_v2 import NotebookLMAnalyzer

WEEKLY_NB_ID  = "25b3c51b-841a-42c4-91df-34f506e0eb29"
MONTHLY_NB_ID = "e5effd07-1d26-448c-aec7-e63410182c4f"

QUERIES = [
    ("부동산/지식산업센터", "지식산업센터 부동산 매매 임대"),
    ("경제/금융",           "경제 금리 환율 증시 코스피"),
    ("AI/반도체",           "AI 인공지능 반도체 HBM 엔비디아"),
    ("지정학/국제",         "지정학 무역 미국 중국 이란 전쟁"),
]

KEYWORD_LIST = [
    "AI", "반도체", "금리", "부동산", "환율", "유가", "삼성전자", "SK하이닉스",
    "지식산업센터", "아파트", "인플레", "달러", "코스피", "이란", "HBM",
    "엔비디아", "무역", "청약", "전세", "규제", "투자", "수출"
]

WEEKLY_PROMPT = """제공된 이번 주 뉴스 기사들을 기반으로, 다음 3층 구조 분석 프레임워크를 적용해 깊은 통찰을 도출해주세요.

**분석 프레임워크: 표면적 사건 → 진짜 타겟 → 숨겨진 의도**
**핵심 질문:** "주식 차트를 넘어서, 이 흐름이 사회, 정치, 문화, 생활 방식을 어떻게 바꾸는가?"

가장 중요한 3개의 핵심 키워드를 선정하고 각각 아래 형식으로 분석해주세요:

## 🔍 핵심 키워드 1: [키워드명]

### 1층: 표면적 사건 (Surface)
- [뉴스 번호 인용 포함]

### 2층: 진짜 타겟 (Real Target)
- [실제 피해자/수혜자]

### 3층: 숨겨진 의도 (Hidden Agenda)
- [배후 의도, 선택 강요 딜레마]

---

## 🔍 핵심 키워드 2: [키워드명]
(동일 형식)

---

## 🔍 핵심 키워드 3: [키워드명]
(동일 형식)

---

## 💡 최종 인사이트

**"이 모든 파도의 출발점은 누구인가?"**

[한국의 주도권과 위치 분석]

**[핵심 통찰 한 줄 요약]**
**"..."**"""

MONTHLY_PROMPT = """제공된 지난 한 달의 뉴스 기사들을 기반으로, 월간 구조적 변화를 3층 분석 프레임워크로 도출해주세요.

**분석 프레임워크: 표면적 사건 → 진짜 타겟 → 숨겨진 의도**
**핵심 질문:** "지난 한 달, 어떤 구조적 변화가 시작되었는가?"

3개의 주요 키워드에 대해 각각 아래 형식으로 분석해주세요:

### [번호]. 주요 키워드: [키워드명]
1. **표면적 사건 (Surface):** [뉴스 번호 인용]
2. **진짜 타겟 (Real Target):** [실제 영향받는 대상]
3. **숨겨진 의도 (Hidden Agenda):** [배후 의도]
4. **3개월 후, 1년 후 영향:**
   * **3개월 후:**
   * **1년 후:**

---

## 🧭 월간 분석의 핵심 질문

**1. 주도권 누구에게?:**

**2. 구조적 변화:**

**3. 선택 강요의 딜레마:**

---

## 💡 최종 월간 인사이트

**"이 모든 파도의 출발점은 누구인가?"**

**🔥 이달의 깊은 통찰 한 문장:**
**"..."**

---

## 📌 3개월 후, 1년 후 전망

### 3개월 후
-

### 1년 후
- """


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def determine_period() -> str:
    now = datetime.now()
    return "monthly" if now.day == 1 else "weekly"


def get_week_range(now: datetime) -> tuple:
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def build_news_text(articles: list) -> str:
    """뉴스 목록을 하나의 텍스트로 (제목 + URL)"""
    lines = []
    for n, item in enumerate(articles, 1):
        title = item.get("title", "")
        link = item.get("link", "")
        lines.append(f"[{n}] {title}")
        lines.append(f"    URL: {link}")
    return "\n".join(lines)


def build_monthly_news_text(now: datetime) -> tuple:
    """지난달 데일리 뉴스 MD 파일들에서 제목+URL 추출해 하나의 텍스트로 묶기"""
    last_month = now.replace(day=1) - timedelta(days=1)
    year, month = last_month.year, last_month.month

    vault = Path(VAULT_PATH)
    daily_folder = vault / "50. 투자" / "01. 뉴스 스크랩" / str(year) / f"{month:02d}"

    if not daily_folder.exists():
        print(f"  데일리 폴더 없음: {daily_folder}")
        return "", [], 0

    md_files = sorted(daily_folder.glob("*.md"))
    if not md_files:
        print(f"  데일리 MD 파일 없음: {daily_folder}")
        return "", [], 0

    lines = [f"=== {year}년 {month:02d}월 전체 뉴스 모음 ({len(md_files)}일치) ===\n"]
    all_titles = []
    n = 1

    for md_file in md_files:
        date_str = md_file.stem
        lines.append(f"--- {date_str} ---")
        content = md_file.read_text(encoding="utf-8")
        title_matches = re.findall(r"^### \d+\.\s+(.+?)\s*⭐", content, re.MULTILINE)
        url_matches = re.findall(r"-\s+\*\*URL:\*\*\s+(\S+)", content)
        for i, title in enumerate(title_matches):
            url = url_matches[i] if i < len(url_matches) else ""
            title_clean = clean(title)
            lines.append(f"[{n}] {title_clean}")
            if url:
                lines.append(f"    URL: {url}")
            all_titles.append(title_clean)
            n += 1
        lines.append("")

    total = n - 1
    print(f"  {year}년 {month:02d}월 데일리 {len(md_files)}일치, 총 {total}건 추출")

    counter = Counter()
    for title in all_titles:
        for kw in KEYWORD_LIST:
            if kw in title:
                counter[kw] += 1
    top_keywords = [kw for kw, _ in counter.most_common(5)]
    return "\n".join(lines), top_keywords, total


def build_obsidian_content(period: str, analysis: str, now: datetime,
                           top_keywords: list, total: int) -> tuple:
    """옵시디언 저장용 (folder, filename, content) 반환"""
    week_start, week_end = get_week_range(now)
    kw_str = ", ".join(top_keywords) if top_keywords else "—"

    if period == "monthly":
        folder = f"50. 투자/02. 테제 분석/Monthly/{now.year}"
        filename = f"{now.strftime('%Y-%m-%d')}_월간분석_구조적변화.md"
        header = (
            f"# {now.strftime('%Y년 %m월')} 월간 분석: 구조적 변화의 흐름\n\n"
            f"> **핵심 질문**\n"
            f'> "지난 한 달, 어떤 구조적 변화가 시작되었는가?"\n\n'
            f"---\n\n"
            f"## 🎯 깊은 통찰: 표면 뒤에 숨겨진 진짜 이야기\n"
            f"> **분석 프레임워크:** 표면적 사건 → 진짜 타겟 → 숨겨진 의도\n\n"
            f"---\n\n"
            f"## 📊 이달 주요 키워드\n\n**{kw_str}** (총 {total}건 기반)\n\n---\n\n"
        )
        footer = (
            f"\n\n---\n\n"
            f"**분석일:** {now.strftime('%Y년 %m월 %d일')}\n"
            f"**기반:** NotebookLM 월간 깊은 통찰 분석 (지난 30일)\n"
            f"**목적:** 투자를 넘어선 사회적 흐름에 대한 통찰\n"
        )
    else:
        folder = f"50. 투자/02. 테제 분석/Weekly/{now.year}"
        ws = week_start.strftime('%Y-%m-%d')
        we = week_end.strftime('%m-%d')
        filename = f"{ws}_{we}_주간분석_구조적변화.md"
        date_range = f"{week_start.strftime('%m/%d')}_{week_end.strftime('%m/%d')}"
        header = (
            f"# {now.strftime('%Y년')} {date_range} 주간 분석: 구조적 변화의 흐름\n\n"
            f"> **핵심 질문**\n"
            f'> "주식 차트를 넘어서, 이 흐름이 사회, 정치, 문화, 생활 방식을 어떻게 바꾸는가?"\n\n'
            f"---\n\n"
            f"## 🎯 깊은 통찰: 표면 뒤에 숨겨진 진짜 이야기\n"
            f"> **분석 프레임워크:** 표면적 사건 → 진짜 타겟 → 숨겨진 의도\n\n"
            f"---\n\n"
            f"## 📊 이번 주 주요 키워드\n\n**{kw_str}** (총 {total}건 기반)\n\n---\n\n"
        )
        footer = (
            f"\n\n---\n\n"
            f"**분석일:** {now.strftime('%Y년 %m월 %d일')}\n"
            f"**기반:** NotebookLM 깊은 통찰 분석\n"
            f"**목적:** 투자를 넘어선 사회적 흐름에 대한 통찰\n"
        )

    return folder, filename, header + analysis + footer


def main():
    now = datetime.now()
    period = determine_period()
    period_label = "월간" if period == "monthly" else "주간"
    nb_id = MONTHLY_NB_ID if period == "monthly" else WEEKLY_NB_ID
    prompt = MONTHLY_PROMPT if period == "monthly" else WEEKLY_PROMPT
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    if period == "monthly":
        print("📰 지난달 데일리 뉴스 수집 중...")
        news_text, top_keywords, total = build_monthly_news_text(now)
        if not news_text:
            print("❌ 데일리 뉴스 파일 없음 - 종료")
            return
    else:
        print("📰 주간 뉴스 수집 중...")
        scraper = NewsScraper(config={
            "naver_client_id": NAVER_CLIENT_ID,
            "naver_client_secret": NAVER_CLIENT_SECRET
        })
        result = scraper.run({
            "operation": "multiple",
            "queries": [q for _, q in QUERIES],
            "display_per_query": 10,
            "remove_duplicates": True
        })
        articles = result.get("articles", [])
        total = len(articles)

        analyzer = NewsAnalyzer(config={"keywords": {"전체": KEYWORD_LIST}})
        kw_result = analyzer.run({
            "articles": [{"title": a.get("title", ""), "content": a.get("description", "")} for a in articles],
            "operation": "keywords"
        })
        kw_pairs = kw_result.get("keywords", [])
        if kw_pairs and isinstance(kw_pairs[0], (list, tuple)):
            seen, top_keywords = set(), []
            for _, kw in kw_pairs:
                if kw not in seen:
                    seen.add(kw)
                    top_keywords.append(kw)
                if len(top_keywords) == 5:
                    break
        else:
            top_keywords = list(dict.fromkeys(kw_pairs))[:5]

        news_text = build_news_text(articles)

    print(f"수집 완료: {total}건")
    print(f"주요 키워드: {', '.join(top_keywords)}")

    sender.send_message(
        f"⏳ {period_label} 테제 분석 시작\n"
        f"뉴스 {total}건 → NotebookLM 분석 중...\n"
        f"완료까지 약 3~5분 소요됩니다 ⚛️"
    )

    print("\nNotebookLM 파이프라인 실행 중...")
    nb_analyzer = NotebookLMAnalyzer()
    nb_result = nb_analyzer.run({
        "operation": "analyze",
        "notebook_id": nb_id,
        "news_text": news_text,
        "source_title": f"{period_label} 뉴스 모음",
        "prompt": prompt
    })

    if nb_result.get("success"):
        analysis = nb_result["result"]
        print(f"분석 완료 ({len(analysis)}자)")
    else:
        analysis = f"❌ 분석 오류: {nb_result.get('error', '알 수 없음')}"
        print(analysis)

    folder, filename, content = build_obsidian_content(period, analysis, now, top_keywords, total)
    writer = ObsidianWriter(config={"vault_path": VAULT_PATH})
    write_result = writer.run({
        "operation": "write",
        "folder": folder,
        "filename": filename,
        "content": content
    })
    note_path = write_result.get("path", "")
    print(f"✅ 저장: {note_path}")

    kw_str = ", ".join(top_keywords)
    sender.send_message(
        f"✅ {period_label} 테제 분석 완료!\n\n"
        f"뉴스 {total}건 분석\n"
        f"주요 키워드: {kw_str}\n\n"
        f"📁 50. 투자/02. 테제 분석/{period_label.capitalize()}/\n"
        f"옵시디언에서 확인하세요 ⚛️"
    )


if __name__ == "__main__":
    main()
