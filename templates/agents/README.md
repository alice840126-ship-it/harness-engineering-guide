# Claude Agents - 재사용 가능한 에이전트 모음

에이전트 기반 아키텍처를 통해 AI가 안정적이고 반복 가능한 결과를 냅니다.

## 📁 에이전트 목록

### ✅ 완성된 에이전트

| 에이전트 | 파일 | 목적 | 재사용처 |
|---------|------|------|----------|
| **텔레그램 발송** | `telegram_sender.py` | 텔레그램 메시지/사진/문서 발송 | 20개 파일 |
| **요약** | `summarizer.py` | 텍스트/뉴스/작업 로그 요약 | 18개 파일 |
| **뉴스 스크래핑** | `news_scraper.py` | 네이버 뉴스 수집 + 필터링 | 5개 파일 |
| **옵시디언 작성** | `obsidian_writer.py` | 옵시디언 노트 저장 | 3개 파일 |
| **뉴스 분석** | `news_analyzer.py` | 뉴스 키워드 추출/테마 분석 | 2개 파일 |
| **데일리 노트 생성** | `obsidian_note_creator.py` | 옵시디언 데일리 노트 자동 생성 | 1개 파일 |
| **컨텍스트 수집** | `context_collector.py` | Claude 세션에서 패턴/선호도 추출 | 1개 파일 |
| **캘린더 도우미** | `calendar_helper.py` | Google Calendar 일정 조회 | 3개 파일 |

## 🔧 에이전트 사용법

### 1. 텔레그램 발송

```python
from agents.telegram_sender import TelegramSender

sender = TelegramSender()

# 기본 메시지
sender.send_message("안녕하세요!")

# HTML 포맷
sender.send_html("<b>볼드</b>와 <i>이탤릭</i>")

# 알림
sender.send_alert("알림", "중요한 메시지", emoji="🚨")

# 데일리 리포트
sender.send_daily_report(
    "아침 리포트",
    "오늘의 주요 뉴스입니다",
    {"경제": "3건", "부동산": "2건"}
)
```

### 2. 요약

```python
from agents.summarizer import Summarizer

summarizer = Summarizer()

# 텍스트 요약
short = summarizer.summarize_text(long_text, max_sentences=3)

# 뉴스 요약
news_summary = summarizer.summarize_news(news_list, max_count=5)

# 작업 로그 요약
work_summary = summarizer.summarize_work_log(work_items, group_by_category=True)
```

### 3. 뉴스 스크래핑

```python
from agents.news_scraper import NewsScraper

scraper = NewsScraper()

# 단일 검색어
news = scraper.scrape_naver_news("삼성전자", display=10)

# 여러 검색어
queries = ["경제", "부동산", "AI"]
news = scraper.scrape_multiple_queries(queries, display_per_query=5)

# 필터 적용 (스팸 제거 + 정렬)
news = scraper.scrape_with_filters(
    query="주식 시장",
    display=10,
    filter_spam=True,
    sort_by="source_score"  # 출처 신뢰도순 정렬
)

# 스팸 필터링
filtered_news = scraper.filter_spam(news_items)

# 본문 추출 (newspaper3k 필요)
full_text = scraper.fetch_full_article(url, max_sentences=3)
```

### 4. 옵시디언 작성

```python
from agents.obsidian_writer import ObsidianWriter

writer = ObsidianWriter()

# 기본 노트 작성
writer.write_note("# 노트 제목\n\n내용", "my_note")

# 데일리 노트 작성
writer.create_daily_note("## 오늘의 할 일\n\n- 작업 1")

# 프로젝트 노트 작성 (YAML frontmatter 포함)
writer.create_project_note(
    title="AI 에이전트 개발",
    content="## 목표\n\n에이전트 시스템 구축",
    project_folder="automation",
    tags=["ai", "agent"]
)

# 제텔카스텐 노트 작성
writer.create_zettelkasten_note(
    title="하네스 엔지니어링",
    content="환경 제약, 컨텍스트, 피드백",
    references=["https://example.com"]
)
```

### 5. 뉴스 분석

```python
from agents.news_analyzer import NewsAnalyzer

analyzer = NewsAnalyzer()

# 키워드 추출
text = "삼성전자와 SK하이닉스가 HBM 반도체를 생산합니다."
keywords = analyzer.extract_keywords(text)
# [('AI', 'HBM'), ('AI', '반도체'), ('AI', '삼성전자'), ...]

# 테마 그룹핑
articles = [
    {'title': '삼성전자 HBM', 'content': '...'},
    {'title': 'SK하이닉스 칩', 'content': '...'},
]
themes = analyzer.group_by_theme(articles, min_articles=2)

# 인사이트 도출
insights = analyzer.derive_insights(themes, "2026-03-19")

# 감성 분석
sentiment = analyzer.calculate_sentiment("주가 상승, 성장세 지속")
# {'score': 0.5, 'label': '긍정', 'positive': 2, 'negative': 0}
```

## 📋 새 에이전트 만들 때

### 1. PRD 작성
`AGENT_TEMPLATE.md`를 참고해서 기능 명세를 작성하세요.

### 2. 단일 책임 확인
- 에이전트가 **하나의 일**만 하도록 설계
- 다른 기능이 필요하면 새 에이전트로 분리

### 3. 인터페이스 명시
```python
class MyAgent:
    def process(self, input_data: dict) -> dict:
        """입력/출력 명확히 정의"""
        result = do_something(input_data)
        return result
```

### 4. 테스트 작성
`tests/test_my_agent.py`에 단위 테스트를 작성하세요.

### 5. 문서화
- 에이전트 파일 상단에 주석으로 목적과 사용법 명시
- 이 README에 에이전트를 추가

## 🎯 하네스 규칙

### 핵심 원칙

1. **환경 제약**
   - 복잡한 작업은 반드시 에이전트로 분리
   - 각 에이전트는 단일 책임만
   - 재사용을 우선 고려

2. **컨텍스트 제공**
   - 각 에이전트의 목적과 인터페이스 명확히 문서화
   - PRD와 예시 코드 제공

3. **피드백 루프**
   - 단위 테스트로 에이전트 검증
   - 에러 발생 시 어디서 문제인지 바로 파악
   - 점진적 개선

## 📁 폴더 구조

```
~/.claude/
├── agents/                           # 재사용 가능한 에이전트
│   ├── telegram_sender.py            # 텔레그램 발송
│   ├── summarizer.py                  # 요약
│   ├── news_scraper.py                # 뉴스 스크래핑 ✅
│   ├── obsidian_writer.py             # 옵시디언 작성 ✅
│   ├── news_analyzer.py               # 뉴스 분석 ✅
│   ├── AGENT_TEMPLATE.md              # PRD 템플릿
│   └── README.md                       # 이 파일
│
├── orchestrators/                    # 에이전트 조립
│   ├── morning_news.py                # 뉴스 + 요약 + 발송
│   └── evening_briefing.py            # 저녁 브리핑
│
└── tests/                           # 단위 테스트
    ├── test_telegram_sender.py       # 텔레그램 테스트
    ├── test_summarizer.py             # 요약 테스트
    ├── test_news_scraper.py           # 뉴스 스크래핑 테스트 ✅
    ├── test_obsidian_writer.py        # 옵시디언 작성 테스트 ✅
    └── test_news_analyzer.py          # 뉴스 분석 테스트 ✅
```

## 🔄 에이전트 조립 예시

### Before: 거대한 스크립트 (안티패턴)

```python
def morning_news():
    # 150줄의 거대한 함수
    news = scrape_naver()     # 50줄
    summary = do_sum()        # 30줄
    send_telegram(summary)   # 70줄
```

### After: 에이전트 조립 (하네스 패턴)

```python
# 30줄로 줄어듦!
from agents.news_scraper import NewsScraper
from agents.summarizer import Summarizer
from agents.telegram_sender import TelegramSender

def morning_news():
    scraper = NewsScraper()
    summarizer = Summarizer()
    sender = TelegramSender()

    news = scraper.scrape("경제", "금리", 5)
    summary = summarizer.summarize_news(news)
    sender.send_daily_report("아침 뉴스", summary)
```

## 📊 재사용 효과

| 항목 | Before | After |
|------|--------|-------|
| 코드 중복 | 5번 반복 | 1번 작성 |
| 수정 범위 | 5개 파일 | 1개 에이전트 |
| 에러 추적 | 어려움 | 즉시 파악 |
| 테스트 | 통합만 가능 | 단위 테스트 가능 |

---

**참고**: [하네스 엔지니어링 완전 가이드](https://www.nxcode.io/ko/resources/news/harness-engineering-complete-guide-ai-agent-codex-2026)
