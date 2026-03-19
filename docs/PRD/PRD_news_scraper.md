# 뉴스 스크래핑 에이전트 PRD

## 에이전트 개요

**이름:** `NewsScraper`

**목적:** 네이버 검색 API, 웹 스크래핑을 통해 뉴스를 수집하는 재사용 가능한 에이전트

**단일 책임:** 오직 뉴스 수집만 담당 (요약, 발송은 다른 에이전트)

## 입력 (Inputs)

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `query` | `str` | ✅ | 검색어 |
| `queries` | `List[str]` | ✅ | 검색어 리스트 (다중 검색용) |
| `display` | `int` | ❌ | 결과 개수 (기본값: 10) |
| `sort` | `str` | ❌ | 정렬 방식: "date" 또는 "source_score" |
| `filter_spam` | `bool` | ❌ | 스팸 필터링 여부 (기본값: True) |
| `fetch_full_content` | `bool` | ❌ | 본문 추출 여부 (기본값: False) |

## 출력 (Outputs)

### `scrape_naver_news()` 반환값

```python
List[Dict[str, Any]]
[
    {
        "title": "뉴스 제목",
        "description": "요약 설명",
        "link": "기사 URL",
        "pubDate": "발행일",
        "source_score": 3  # 출처 신뢰도 점수 (1~3)
    },
    ...
]
```

## 사용 예시

### 1. 기본 사용

```python
from agents.news_scraper import NewsScraper

scraper = NewsScraper()

# 단일 검색어
news = scraper.scrape_naver_news("삼성전자", display=10)
```

### 2. 여러 검색어

```python
queries = ["경제", "부동산", "AI", "금리"]
news = scraper.scrape_multiple_queries(queries, display_per_query=5, max_total=20)
```

### 3. 필터 적용

```python
# 스팸 제거 + 출처 점수순 정렬
news = scraper.scrape_with_filters(
    query="주식 시장",
    display=10,
    filter_spam=True,
    sort_by="source_score"
)
```

### 4. 본문 추출

```python
# newspaper3k로 본문 전체 추출
url = "https://www.hankyung.com/article/2023..."
full_text = scraper.fetch_full_article(url, max_sentences=3)
```

## 재사용 위치

| 파일 | 사용 방식 | 빈도 |
|------|----------|------|
| `scripts/morning_news.py` | 아침 뉴스 수집 | 매일 07:00 |
| `scripts/evening_briefing.py` | 저녁 마감 뉴스 | 매일 17:50 |
| `scripts/news_scraper.py` | 일일 뉴스 스크랩 | 매일 07:00 |
| `scripts/news_collector.py` | 뉴스 수집 | 수시 |
| `scripts/monitor_itcen_btc.py` | 관련 뉴스 모니터링 | 수시 |

## 의존성 (Dependencies)

### 필수
- `requests` - HTTP 요청
- `python-dotenv` - 환경 변수 관리

### 선택적
- `newspaper3k` - 본문 추출 (미설치 시 기본 description만 사용)

### 환경 변수
```bash
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
```

## 핵심 기능

### 1. 네이버 검색 API
- 검색어 기반 뉴스 수집
- 최신순/관련도순 정렬
- 최대 100개 결과

### 2. HTML 정제
- HTML 태그 제거
- 특수 문자 디코딩
- 대괄호 안 내용 제거

### 3. 스팸 필터링
- 기본 스팸 키워드: "속보", "재업로드", "2보" 등
- 커스텀 키워드 지원

### 4. 출처 신뢰도 점수화
- 1티어 (3점): 한국경제, 매일경제 등 주요 경제지
- 2티어 (2점): 연합뉴스, 뉴시스 등 주요 일간지
- 3티어 (1점): 기타

### 5. 본문 추출 (선택)
- newspaper3k로 전체 본문 추출
- 상위 N개 문장 요약
- 실패 시 기본 description 사용

## 테스트

```bash
# 단위 테스트 실행
python3 tests/test_news_scraper.py
```

### 테스트 커버리지

| 테스트 | 설명 |
|--------|------|
| `test_scraper_initialization` | 초기화 및 환경변수 확인 |
| `test_clean_html_text` | HTML 정제 기능 |
| `test_source_score` | 출처 점수 계산 |
| `test_spam_filtering` | 스팸 필터링 |
| `test_sort_by_source_score` | 점수별 정렬 |

## 설계 결정

### 왜 단일 책임인가?
- 뉴스 수집 = 스크래핑 + 요약 + 발송
- 각각 별개의 관심사
- 변경 이유가 다름
- 재사용성을 높이기 위해 분리

### 왜 newspaper3k가 선택적인가?
- 모든 상황에서 본문 추출이 필요하지 않음
- 제목만으로도 충분한 경우가 많음
- 의존성 최소화 원칙

### 왜 출처 점수화인가?
- 모든 뉴스가 동일한 신뢰도가 아님
- 주요 경제지 > 기타
- 정렬에 활용 가능

## 제한 사항

1. **네이버 API에 의존**
   - API 한계: 최대 100개 결과
   - 속도 제한: 초당 10회 이하 권장

2. **본문 추출 불안정성**
   - 일부 사이트는 robot.txt 차단
   - 동적 로딩 불가
   - newspaper3k 실패 시 fallback 필요

3. **언어 제한**
   - 현재 한국어 네이버 뉴스만 지원
   - 해외 뉴스는 별도 구현 필요

## 개선 계획

- [ ] 구글 뉴스 API 추가
- [ ] RSS 피드 지원
- [ ] 캐싱 기능 (중복 요청 방지)
- [ ] 비동기 요청 (속도 개선)
- [ ] 해외 뉴스 소스 추가

---

**작성일:** 2026-03-19
**버전:** 1.0.0
**상태:** ✅ 완성 및 테스트 통과
