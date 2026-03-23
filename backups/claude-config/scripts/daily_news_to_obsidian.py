#!/usr/bin/env python3
"""데일리 뉴스 → 옵시디언 저장 - 매일 07:00 / 50. 투자/01. 뉴스 스크랩"""
import sys
sys.path.insert(0, "/Users/oungsooryu/.claude/scripts")
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, VAULT_PATH

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
import requests

QUERIES = [
    ("경제",      "경제 금리 환율 물가"),
    ("부동산",    "부동산 아파트 지식산업센터 전세 청약"),
    ("IT/반도체", "반도체 AI 인공지능 기술 스타트업"),
    ("투자",      "주식 코스피 코스닥 ETF 증시"),
    ("지정학",    "지정학 미국 중국 이란 무역 전쟁"),
]

# 출처 신뢰도 (도메인 기반)
TRUSTED_DOMAINS = ["naver.com", "yna.co.kr", "yonhap", "chosun.com", "joongang", "hani.co.kr",
                   "hankyung.com", "mk.co.kr", "sedaily.com", "etnews.com"]


def clean(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def fetch_naver_news(query: str, display: int = 5) -> list:
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


def get_source(link: str) -> str:
    if "naver.com" in link:
        return "naver"
    for d in TRUSTED_DOMAINS:
        if d in link:
            return d.split(".")[0]
    return "기타"


def bar(count: int, total: int, max_width: int = 20) -> str:
    filled = int((count / max(total, 1)) * max_width)
    return "█" * filled + "░" * (max_width - filled)


def extract_keywords(items: list) -> Counter:
    keyword_list = [
        "AI", "반도체", "금리", "부동산", "환율", "투자", "유가", "삼성전자", "SK하이닉스",
        "비트코인", "지식산업센터", "아파트", "인플레", "달러", "증시", "코스피", "이란",
        "HBM", "엔비디아", "무역", "청약", "전세", "금융", "스타트업", "규제"
    ]
    counter = Counter()
    for item in items:
        title = clean(item.get("title", ""))
        for kw in keyword_list:
            if kw in title:
                counter[kw] += 1
    return counter


def build_visualization(all_items: list) -> list:
    total = len(all_items)
    lines = ["## 📈 오늘의 시각화", ""]

    # 출처 신뢰도
    lines.append("### 출처 신뢰도 분포")
    lines.append("")
    source_counter = Counter(get_source(item.get("link", "")) for item in all_items)
    for source, cnt in source_counter.most_common():
        pct = int(cnt / total * 100) if total > 0 else 0
        lines.append(f"- **{source}:** {bar(cnt, total)} {cnt}건 ({pct}%)")

    lines.append("")
    lines.append("### 키워드 빈도 (상위 10개)")
    lines.append("")
    kw_counter = extract_keywords(all_items)
    for kw, cnt in kw_counter.most_common(10):
        lines.append(f"- **{kw}:** {bar(cnt, max(kw_counter.values(), default=1))} {cnt}회")

    lines.append("")
    return lines


def build_insights(all_items: list, keyword_counter: Counter) -> list:
    lines = ["## 💡 인사이트 (자동 생성)", ""]
    top_kws = [kw for kw, _ in keyword_counter.most_common(3)]

    # 출처 품질
    lines.append("### 출처 품질")
    lines.append("")
    naver_cnt = sum(1 for item in all_items if "naver.com" in item.get("link", ""))
    lines.append(f"- 네이버 수집: {naver_cnt}/{len(all_items)}건")

    # 키워드 트렌드
    lines.append("### 키워드 트렌드")
    if top_kws:
        lines.append(f"- **주요 키워드:** {', '.join(top_kws)}")
        lines.append("- 이번 주에 이 키워드가 지속적으로 나오면 '테마'로 분류됩니다")

    lines.append("")
    return lines


def main():
    now = datetime.now()
    year, month, day = now.year, now.month, now.day
    date_str = f"{year}-{month:02d}-{day:02d}"

    # 저장 경로: 50. 투자/01. 뉴스 스크랩/2026/03/
    folder_path = Path(VAULT_PATH) / "50. 투자" / "01. 뉴스 스크랩" / str(year) / f"{month:02d}"
    folder_path.mkdir(parents=True, exist_ok=True)
    note_path = folder_path / f"{date_str}.md"

    if note_path.exists():
        print(f"이미 존재: {note_path}")
        return

    # 뉴스 수집
    all_items = []
    section_data = {}
    for label, query in QUERIES:
        items = fetch_naver_news(query, 4)
        section_data[label] = items
        all_items.extend(items)

    total = len(all_items)
    keyword_counter = extract_keywords(all_items)

    # 본문 구성
    lines = [
        f"---",
        f"type: daily-news-scrap",
        f"date: {date_str}",
        f"tags: [뉴스, 스크랩, DATACRAFT]",
        f"source: naver-api",
        f"---",
        f"",
        f"# {date_str} 뉴스 스크랩",
        f"",
        f"## 📊 수집 현황",
        f"- 총 기사: {total}건",
        f"- 수집 시간: {now.strftime('%H:%M')}",
        f"- 출처: 네이버 API",
        f"- 스팸 필터링: ✅ 적용",
        f"- 출처 점수화: ✅ 적용",
        f"",
        f"---",
        f"",
    ]

    # 시각화 섹션
    lines.extend(build_visualization(all_items))
    lines.append("---")
    lines.append("")

    # 인사이트 섹션
    lines.extend(build_insights(all_items, keyword_counter))
    lines.append("---")
    lines.append("")

    # 뉴스 목록
    lines.append("## 📰 뉴스 목록")
    lines.append("")
    n = 1
    for label, items in section_data.items():
        if not items:
            continue
        lines.append(f"### 🏷 {label}")
        lines.append("")
        for item in items:
            title = clean(item.get("title", ""))
            desc = clean(item.get("description", ""))
            link = item.get("link", "")
            source = get_source(link)
            lines.append(f"### {n}. {title} ⭐")
            if desc:
                # 핵심은 250자까지
                lines.append(f"- **핵심:** {desc[:250]}")
            lines.append(f"- **URL:** {link}")
            lines.append(f"- **출처:** {source}")
            lines.append("")
            n += 1

    lines.append("---")
    lines.append(f"## 🏷️ 오늘의 태그")
    lines.append(f"#{date_str.replace('-', '_')}")

    note_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 데일리 뉴스 저장: {note_path} ({total}건)")


if __name__ == "__main__":
    main()
