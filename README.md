# 하네스 엔지니어링 가이드
> 에이전트 기반 개발 방법론 - 재사용 가능한 AI 에이전트 시스템 구축

## 🎯 목적

AI 개발에서 **하네스 엔지니어링(Harness Engineering)** 방법론을 적용하여 안정적이고 재사용 가능한 에이전트 시스템을 구축하는 가이드입니다.

### 핵심 원칙

1. **단일 책임 원칙 (Single Responsibility)** - 각 에이전트는 하나의 명확한 역할만 담당
2. **재사용성 (Reusability)** - 에이전트는 여러 프로젝트에서 재사용 가능
3. **명시적 인터페이스 (Explicit Interfaces)** - 입력/출력이 명확하게 정의됨
4. **테스트 주도 개발 (Test-Driven Development)** - 모든 에이전트는 단위 테스트 보유
5. **마이크로서비스 패턴 (Microservices Pattern)** - 독립적인 에이전트를 조립하여 복잡한 기능 구현

## 📁 구조

```
harness-engineering-guide/
├── templates/agents/          # 에이전트 템플릿
│   ├── AGENT_TEMPLATE.md     # 새 에이전트 PRD 템플릿
│   ├── telegram_sender.py    # 텔레그램 전송 에이전트
│   ├── summarizer.py         # 텍스트 요약 에이전트
│   ├── news_scraper.py       # 뉴스 스크래핑 에이전트
│   ├── obsidian_writer.py    # 옵시디언 작성 에이전트
│   ├── news_analyzer.py      # 뉴스 분석 에이전트
│   └── README.md             # 에이전트 사용 가이드
├── examples/tests/            # 테스트 예제
│   ├── test_telegram_sender.py
│   ├── test_summarizer.py
│   ├── test_news_scraper.py
│   ├── test_obsidian_writer.py
│   └── test_news_analyzer.py
├── docs/PRD/                  # PRD 문서
│   ├── AGENT_TEMPLATE.md
│   └── PRD_news_scraper.md
├── .cursorrules.example      # 프로젝트 규칙 예제
└── README.md                 # 이 파일
```

## 🚀 빠른 시작

### 1. 새 에이전트 만들기

```bash
# 1. PRD 작성
cp templates/agents/AGENT_TEMPLATE.md templates/agents/PRD_your_agent.md

# 2. PRD를 참고하여 에이전트 구현
# templates/agents/your_agent.py

# 3. 단위 테스트 작성
# examples/tests/test_your_agent.py

# 4. 테스트 실행
python -m pytest examples/tests/test_your_agent.py -v
```

### 2. 에이전트 사용 예시

```python
from telegram_sender import TelegramSender

# 에이전트 초기화
sender = TelegramSender()

# 단순 메시지 전송
sender.send_message("안녕하세요!")

# HTML 포맷 전송
sender.send_html("<b>굵은 글씨</b>와 <i>기울임</i>")

# 일일 리포트 전송
sender.send_daily_report(
    title="오늘의 요약",
    content="주요 내용",
    sections={"뉴스": "3건 수집", "일정": "5개"}
)
```

## 📚 에이전트 목록

### TelegramSender
- **역할:** 텔레그램 메시지/문서 전송
- **주요 메서드:** `send_message()`, `send_html()`, `send_daily_report()`, `send_document()`
- **재사용 위치:** 뉴스 스크랩, 일정 브리핑, 분석 리포트

### Summarizer
- **역할:** 텍스트/뉴스/작업로그 요약
- **주요 메서드:** `summarize_text()`, `summarize_news()`, `summarize_work_log()`
- **재사용 위치:** 뉴스 분석, 데일리 리포트, 작업 요약

### NewsScraper
- **역할:** 네이버 뉴스 스크래핑 + 필터링
- **주요 메서드:** `scrape_naver_news()`, `scrape_multiple_queries()`, `filter_spam()`
- **재사용 위치:** 아침 뉴스, 저녁 브리핑, 뉴스 분석

### ObsidianWriter
- **역할:** 옵시디언 노트 작성 (YAML frontmatter 지원)
- **주요 메서드:** `write_note()`, `create_daily_note()`, `create_project_note()`
- **재사용 위치:** 데일리 노트, 프로젝트 관리, Zettelkasten

### NewsAnalyzer
- **역할:** 뉴스 키워드 추출, 테마 그룹핑, 인사이트 도출
- **주요 메서드:** `extract_keywords()`, `group_by_theme()`, `derive_insights()`
- **재사용 위치:** 주간/월간 분석, 테마 추적

## 🧪 테스트

```bash
# 전체 테스트 실행
python -m pytest examples/tests/ -v

# 특정 에이전트 테스트
python -m pytest examples/tests/test_telegram_sender.py -v

# 커버리지 확인
python -m pytest examples/tests/ --cov=templates/agents --cov-report=html
```

## 📖 하네스 엔지니어링 방법론

### 3가지 핵심 요소

1. **환경 제약 (Environment Constraints)**
   - 에이전트가 작동하는 범위와 한계를 명확히 정의
   - "이 에이전트는 무엇을 할 수 있고, 무엇을 할 수 없는가?"

2. **컨텍스트 제공 (Context Provision)**
   - 에이전트가 작업에 필요한 모든 정보를 명시적으로 제공
   - 암묵적 가정을 배제하고 명시적 인터페이스 강조

3. **피드백 루프 (Feedback Loops)**
   - 단위 테스트를 통해 에이전트 동작을 지속적으로 검증
   - 실제 사용 피드백을 에이전트 개선에 반영

### 에이전트 개발 프로세스

```
1. PRD 작성
   ↓
2. 단위 테스트 작성 (Test-First)
   ↓
3. 에이전트 구현
   ↓
4. 테스트 통과 확인
   ↓
5. 실제 프로젝트에 통합
   ↓
6. 피드백 수집 및 개선
```

### 재사용성 원칙

- **DRY (Don't Repeat Yourself):** 반복되는 코드를 에이전트로 추출
- **구성 > 상속:** 복잡한 상속보다 단순한 에이전트 조합 선호
- **명시적 의존성:** 에이전트가 필요로 의존성을 명확히 선언

## 🔧 .cursorrules

`.cursorrules.example` 파일을 프로젝트 루트에 `.cursorrules`로 복사하여 사용하세요.

```bash
cp .cursorrules.example .cursorrules
```

이 파일은 Cursor IDE에서 자동으로 프로젝트 규칙을 적용하여 일관된 개발 스타일을 유지합니다.

## 📝 PRD 템플릿

새로운 에이전트를 만들 때 `templates/agents/AGENT_TEMPLATE.md`를 사용하세요.

필수 섹션:
- **Purpose:** 에이전트의 목적
- **Inputs:** 입력 파라미터
- **Outputs:** 반환 값
- **Usage:** 사용 예시
- **Reuse Locations:** 재사용 가능한 위치
- **Dependencies:** 외부 의존성
- **Tests:** 단위 테스트 계획

## 🤝 기여

이 가이드는 실제 프로젝트에서 검증된 에이전트들을 포함하고 있습니다.

새로운 에이전트를 추가하거나 개선할 때:
1. PRD 작성
2. 단위 테스트 작성
3. 에이전트 구현
4. 문서 업데이트

## 📂 예시 프로젝트

이 가이드의 에이전트들을 실제로 사용하는 프로젝트:
- **[crypto-stock-monitor](https://github.com/alice840126-ship-it/crypto-stock-monitor)** - 암호화폐/주식 모니터링 시스템

## 📄 라이선스

MIT License

---

**Made with ❤️ by alice840126-ship-it**
