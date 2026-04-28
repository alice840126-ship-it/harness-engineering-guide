# 테스트 가이드

하네스 엔지니어링 에이전트 테스트 방법

## 🚀 빠른 시작

```bash
# 전체 테스트 실행
pytest

# 특정 테스트 파일
pytest test_base_agent.py

# 상세 출력
pytest -v

# 커버리지
pytest --cov=.
```

## 📁 테스트 구조

```
tests/
├── unit/                           # 단위 테스트
│   ├── test_base_agent.py          # BaseAgent 테스트
│   ├── test_pipeline_agent.py      # PipelineAgent 테스트
│   ├── test_news_scraper.py        # 뉴스 스크래퍼 테스트 ✅
│   ├── test_obsidian_writer.py     # 옵시디언 작성 테스트 ✅
│   └── test_news_analyzer.py       # 뉴스 분석 테스트 ✅
│
├── integration/                    # 통합 테스트
│   ├── test_daily_news_pipeline.py # 데일리 뉴스 파이프라인
│   └── test_evening_briefing.py    # 저녁 브리핑
│
└── pytest.ini                       # pytest 설정
```

## 🧪 테스트 작성 가이드

### 단위 테스트

각 에이전트를 독립적으로 테스트합니다.

```python
# tests/unit/test_my_agent.py
import pytest
from my_agent import MyAgent

class TestMyAgent:
    def test_process(self):
        agent = MyAgent()
        result = agent.process({"input": "test"})
        assert result["output"] == "expected"

    def test_error_handling(self):
        agent = MyAgent()
        with pytest.raises(ValueError):
            agent.process({"invalid": "data"})
```

### 통합 테스트

여러 에이전트가 함께 작동하는지 테스트합니다.

```python
# tests/integration/test_my_pipeline.py
def test_news_pipeline():
    # 1. 스크래핑
    scraper = NewsScraper()
    news = scraper.run({"query": "test"})

    # 2. 분석
    analyzer = NewsAnalyzer()
    analyzed = analyzer.run(news)

    # 3. 요약
    summarizer = Summarizer()
    summary = summarizer.run(analyzed)

    assert "summary" in summary
```

## 🎯 테스트 원칙

### 1. GIVEN-WHEN-THEN 패턴

```python
def test_agent_behavior():
    # GIVEN: 테스트 환경 설정
    agent = MyAgent()
    input_data = {"value": 10}

    # WHEN: 동작 실행
    result = agent.run(input_data)

    # THEN: 결과 검증
    assert result["output"] == 20
```

### 2. Mock 활용

외부 의존성을 Mock으로 대체합니다.

```python
from unittest.mock import Mock, patch

def test_with_mock():
    # Mock API 응답
    mock_response = Mock()
    mock_response.json.return_value = {"data": "test"}

    with patch('requests.get', return_value=mock_response):
        agent = MyAgent()
        result = agent.run({"query": "test"})
        assert result["data"] == "test"
```

### 3. 에러 케이스 테스트

```python
def test_error_cases():
    agent = MyAgent()

    # None 입력
    with pytest.raises(ValueError):
        agent.run(None)

    # 빈 데이터
    with pytest.raises(ValueError):
        agent.run({})

    # 잘못된 타입
    with pytest.raises(TypeError):
        agent.run("invalid")
```

## 📊 커버리지 확인

```bash
# 커버리지 리포트 생성
pytest --cov=. --cov-report=html

# 브라우저에서 확인
open htmlcov/index.html
```

## 🔄 CI/CD 연결

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install pytest pytest-cov
      - run: pytest --cov=. --cov-report=xml
```

## 💡 팁

### 1. 테스트 데이터 분리

```python
# conftest.py
@pytest.fixture
def sample_news():
    return {
        "title": "테스트 뉴스",
        "content": "테스트 내용"
    }

# 테스트에서 사용
def test_with_fixture(sample_news):
    agent = NewsAnalyzer()
    result = agent.run({"articles": [sample_news]})
```

### 2. 파라미터화된 테스트

```python
@pytest.mark.parametrize("input,expected", [
    ({"value": 1}, 2),
    ({"value": 2}, 4),
    ({"value": 3}, 6),
])
def test_multiply(input, expected):
    agent = MultiplyAgent()
    result = agent.run(input)
    assert result["value"] == expected
```

### 3. 통계 확인

```python
def test_stats_tracking():
    agent = MyAgent()

    # 실행 전
    assert agent.get_stats()["runs"] == 0

    # 실행
    agent.run({"input": "test"})

    # 실행 후
    assert agent.get_stats()["runs"] == 1
```
