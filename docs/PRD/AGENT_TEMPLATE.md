# 에이전트 PRD 템플릿

새 에이전트를 만들 때 이 양식을 따르세요.

---

## 📋 에이전트 기본 정보

- **이름**: 에이전트 클래스명 (예: `NewsScraper`)
- **목적**: 이 에이전트가 해결하는 문제
- **단일 책임**: 오직 한 가지 일만 수행

## 🎯 목적 (Purpose)

이 에이전트가 존재하는 이유와 해결하는 문제를 설명하세요.

**예시:**
```
목적: 네이버 뉴스에서 뉴스 기사를 수집하고 파싱하기

문제:
- 매번 뉴스 스크래핑 코드를 중복 작성
- HTML 구조가 바뀌면 여러 파일 수정해야 함
- 재사용이 불가능하여 유지보수 어려움
```

## 📥 입력 (Inputs)

에이전트가 받는 데이터 형식과 예시를 명시하세요.

```python
# 입력 형식
{
    "category": str,        # 뉴스 카테고리
    "query": str,           # 검색어
    "count": int,           # 수집 개수
}

# 입력 예시
{
    "category": "경제",
    "query": "금리 인플레이션",
    "count": 5
}
```

## 📤 출력 (Outputs)

에이전트가 반환하는 데이터 형식과 예시를 명시하세요.

```python
# 출력 형식
List[Dict[str, str]]

# 출력 예시
[
    {
        "title": "삼성전자 주가 3% 상승",
        "link": "https://news.naver.com/...",
        "description": "반도체 호재로..."
    }
]
```

## 🔧 사용법 (Usage)

실제 사용 예시를 보여주세요.

```python
# 기본 사용
from agents.news_scraper import NewsScraper

scraper = NewsScraper()
news = scraper.scrape("경제", "금리", 5)

# 다른 에이전트와 조립
from agents.summarizer import Summarizer
from agents.telegram_sender import TelegramSender

scraper = NewsScraper()
summarizer = Summarizer()
sender = TelegramSender()

news = scraper.scrape("경제", "금리", 5)
summary = summarizer.summarize_news(news)
sender.send_daily_report("경제 뉴스", summary)
```

## 🔄 재사용처 (Reuse)

이 에이전트를 사용하는 모든 곳을 나열하세요.

- `morning_news.py` - 아침 경제 뉴스
- `evening_briefing.py` - 저녁 종합 뉴스
- `weekly_report.py` - 주간 경제 뉴스 요약

## ⚙️ 의존성 (Dependencies)

필요한 라이브러리와 API를 명시하세요.

```python
import requests
from bs4 import BeautifulSoup
import os
```

## 🧪 테스트 (Testing)

단위 테스트 예시를 작성하세요.

```python
# tests/test_news_scraper.py
def test_scrape_news():
    scraper = NewsScraper()
    news = scraper.scrape("경제", "테스트", 3)

    assert len(news) > 0
    assert "title" in news[0]
    assert "link" in news[0]
```

## 📝 비고 (Notes)

특이 주의할 사항이나 제약사항을 적으세요.

- 네이버 API 키 필요 (`NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`)
- 요청 제한: 초당 10회
- 에러 발생 시 빈 리스트 반환
