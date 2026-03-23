#!/usr/bin/env python3
"""주간/월간 뉴스 수집 → NotebookLM URL 추가 → 3층 분석 자동 생성 → 옵시디언 저장
- 주간: 일요일 09:00
- 월간: 1일 09:00
"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
sys.path.insert(0, "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents")
from config import BOT_TOKEN, CHAT_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, VAULT_PATH

import asyncio
import re
import requests
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from telegram_sender import TelegramSender

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


def determine_period() -> str:
    now = datetime.now()
    return "monthly" if now.day == 1 else "weekly"


def get_week_range(now: datetime) -> tuple:
    week_start = now - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def build_news_text(all_news: dict) -> str:
    """뉴스 전체를 하나의 텍스트로 묶기 (제목 + URL)"""
    lines = []
    n = 1
    for label, items in all_news.items():
        lines.append(f"=== {label} ===")
        for item in items:
            title = clean(item.get("title", ""))
            link = item.get("originallink") or item.get("link", "")
            lines.append(f"[{n}] {title}")
            lines.append(f"    URL: {link}")
            n += 1
        lines.append("")
    return "\n".join(lines)


async def full_pipeline(nb_id: str, news_text: str, prompt: str) -> str:
    """뉴스 텍스트를 소스 1개로 올리고 분석 요청"""
    from notebooklm import NotebookLMClient
    async with await NotebookLMClient.from_storage() as client:
        # 기존 소스 삭제
        try:
            existing = await client.sources.list(nb_id)
            for src in existing:
                await client.sources.delete(nb_id, src.id)
            print(f"  기존 소스 {len(existing)}개 삭제")
        except Exception as e:
            print(f"  소스 삭제 (무시): {e}")

        # 뉴스 전체를 텍스트 소스 1개로 추가
        source = await client.sources.add_text(nb_id, "이번 주 뉴스 모음", news_text)
        print("  텍스트 소스 1개 추가 완료")

        # 소스 처리 대기
        try:
            await asyncio.wait_for(
                client.sources.wait_for_sources(nb_id, [source.id]),
                timeout=120
            )
            print("  소스 처리 완료")
        except asyncio.TimeoutError:
            print("  소스 처리 타임아웃 (계속 진행)")
        except Exception:
            await asyncio.sleep(10)  # fallback 대기

        # 분석 요청
        print("  분석 요청 중... (최대 5분)")
        result = await asyncio.wait_for(
            client.chat.ask(nb_id, prompt),
            timeout=300
        )
        return getattr(result, 'text', '') or str(result)


def save_to_obsidian(period: str, analysis: str, now: datetime,
                     top_keywords: list, total_news: int) -> str:
    vault = Path(VAULT_PATH)
    week_start, week_end = get_week_range(now)
    kw_str = ", ".join(top_keywords) if top_keywords else "—"

    if period == "monthly":
        folder = vault / "50. 투자" / "02. 테제 분석" / "Monthly" / str(now.year)
        filename = f"{now.strftime('%Y-%m-%d')}_월간분석_구조적변화.md"
        header = (
            f"# {now.strftime('%Y년 %m월')} 월간 분석: 구조적 변화의 흐름\n\n"
            f"> **핵심 질문**\n"
            f'> "지난 한 달, 어떤 구조적 변화가 시작되었는가?"\n\n'
            f"---\n\n"
            f"## 🎯 깊은 통찰: 표면 뒤에 숨겨진 진짜 이야기\n"
            f"> **분석 프레임워크:** 표면적 사건 → 진짜 타겟 → 숨겨진 의도\n\n"
            f"---\n\n"
            f"## 📊 이달 주요 키워드\n\n**{kw_str}** (총 {total_news}건 기반)\n\n---\n\n"
        )
        footer = (
            f"\n\n---\n\n"
            f"**분석일:** {now.strftime('%Y년 %m월 %d일')}\n"
            f"**기반:** NotebookLM 월간 깊은 통찰 분석 (지난 30일)\n"
            f"**목적:** 투자를 넘어선 사회적 흐름에 대한 통찰\n\n"
            f"---\n\n"
            f'*"지난 한 달의 변화가 내년의 운명을 결정한다."*\n'
        )
    else:
        folder = vault / "50. 투자" / "02. 테제 분석" / "Weekly" / str(now.year)
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
            f"## 📊 이번 주 주요 키워드\n\n**{kw_str}** (총 {total_news}건 기반)\n\n---\n\n"
        )
        footer = (
            f"\n\n---\n\n"
            f"**분석일:** {now.strftime('%Y년 %m월 %d일')}\n"
            f"**기반:** NotebookLM 깊은 통찰 분석\n"
            f"**목적:** 투자를 넘어선 사회적 흐름에 대한 통찰\n\n"
            f"---\n\n"
            f'*"미국이 이란을 쳤는데, 진짜 맞은 건 러시아다." — 이런 통찰이야말로 진짜 분석이다.*\n'
        )

    folder.mkdir(parents=True, exist_ok=True)
    note_path = folder / filename
    note_path.write_text(header + analysis + footer, encoding="utf-8")
    print(f"✅ 저장: {note_path}")
    return str(note_path)


def main():
    now = datetime.now()
    period = determine_period()
    period_label = "월간" if period == "monthly" else "주간"
    nb_id = MONTHLY_NB_ID if period == "monthly" else WEEKLY_NB_ID
    prompt = MONTHLY_PROMPT if period == "monthly" else WEEKLY_PROMPT
    sender = TelegramSender(bot_token=BOT_TOKEN, chat_id=CHAT_ID)

    print(f"📰 {period_label} 뉴스 수집 중...")
    all_news = {}
    all_items = []
    for label, query in QUERIES:
        items = fetch_naver_news(query, 10)
        if items:
            all_news[label] = items
            all_items.extend(items)

    top_keywords = extract_top_keywords(all_items, 5)
    total = len(all_items)
    print(f"수집 완료: {total}건")
    print(f"주요 키워드: {', '.join(top_keywords)}")

    news_text = build_news_text(all_news)

    sender.send_message(
        f"⏳ {period_label} 테제 분석 시작\n"
        f"뉴스 {total}건 → NotebookLM 분석 중...\n"
        f"완료까지 약 3~5분 소요됩니다 ⚛️"
    )

    print(f"\nNotebookLM 파이프라인 실행 중...")
    try:
        analysis = asyncio.run(full_pipeline(nb_id, news_text, prompt))
        print(f"분석 완료 ({len(analysis)}자)")
    except asyncio.TimeoutError:
        analysis = "❌ NotebookLM 분석 타임아웃 (300초 초과)"
        print(analysis)
    except Exception as e:
        analysis = f"❌ 분석 오류: {e}"
        print(analysis)

    note_path = save_to_obsidian(period, analysis, now, top_keywords, total)

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
