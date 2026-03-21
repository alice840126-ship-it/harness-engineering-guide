# 에이전트 PRD 템플릿 v2 (BaseAgent 기반)

새 에이전트를 만들 때 이 양식을 따르세요.

---

## 📋 에이전트 기본 정보

- **이름**: 에이전트 클래스명 (예: `NewsAnalyzer`)
- **부모 클래스**: `BaseAgent` (필수)
- **목적**: 이 에이전트가 해결하는 문제
- **단일 책임**: 오직 한 가지 일만 수행

## 🎯 목적 (Purpose)

이 에이전트가 존재하는 이유와 해결하는 문제를 설명하세요.

**예시:**
```
목적: 뉴스 기사에서 키워드를 추출하고 테마별로 그룹핑하기

문제:
- 매번 키워드 추출 로직을 중복 작성
- 키워드 사전이 변경되면 여러 파일 수정
- 재사용이 불가능하여 유지보수 어려움
```

## 📥 입력 (Inputs)

`process()` 메서드가 받는 데이터 형식과 예시를 명시하세요.

```python
# 입력 형식
{
    "articles": List[Dict[str, str]],  # 기사 리스트
    "operation": str,                  # 수행할 작업
    "date_range": str,                 # 분석 기간 (선택)
}

# 입력 예시
{
    "articles": [
        {"title": "삼성전자 주가 상승", "content": "반도체 호재"},
        {"title": "SK하이닉스 HBM", "content": "AI 수요 증가"}
    ],
    "operation": "insights",
    "date_range": "2026-03-21"
}
```

## 📤 출력 (Outputs)

`process()` 메서드가 반환하는 데이터 형식과 예시를 명시하세요.

```python
# 출력 형식
Dict[str, Any]

# 출력 예시
{
    "insights": [
        {
            "type": "주요 테마",
            "insight": "'반도체'가 가장 활발한 키워드입니다",
            "evidence": ["삼성전자 주가 상승", "SK하이닉스 HBM"]
        }
    ]
}
```

## 🔧 사용법 (Usage)

실제 사용 예시를 보여주세요.

```python
# 기본 사용
from agents.news_analyzer_v2 import NewsAnalyzer

analyzer = NewsAnalyzer()

# run() 메서드로 실행 (입력/출력 검증 자동 수행)
result = analyzer.run({
    "articles": [...],
    "operation": "insights"
})

# 통계 확인
print(analyzer.get_stats())
# {"runs": 1, "errors": 0, "last_run": "2026-03-21T10:00:00"}

# 파이프라인에서 사용
from agents.pipeline_agent import PipelineAgent

pipeline = PipelineAgent(
    name="news_pipeline",
    agents=[ScraperAgent(), analyzer, SummarizerAgent()]
)
result = pipeline.run({"query": "부동산"})
```

## 🔄 재사용처 (Reuse)

이 에이전트를 사용하는 모든 곳을 나열하세요.

- `daily_news_pipeline.py` - 아침 뉴스 파이프라인
- `weekly_report.py` - 주간 뉴스 분석
- `market_insight.py` - 시장 인사이트 생성

## ⚙️ 의존성 (Dependencies)

필요한 라이브러리와 API를 명시하세요.

```python
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentError
import re
```

## 🧪 테스트 (Testing)

단위 테스트 예시를 작성하세요.

```python
# tests/test_news_analyzer_v2.py
import pytest
from agents.news_analyzer_v2 import NewsAnalyzer

def test_process_keywords():
    analyzer = NewsAnalyzer()

    result = analyzer.run({
        "articles": [
            {"title": "삼성전자 HBM", "content": "AI 반도체"}
        ],
        "operation": "keywords"
    })

    assert "keywords" in result
    assert len(result["keywords"]) > 0

def test_validate_input():
    analyzer = NewsAnalyzer()

    # 잘못된 입력
    with pytest.raises(Exception):
        analyzer.run({"wrong_key": "value"})  # articles 누락

def test_error_handling():
    analyzer = NewsAnalyzer()

    # 에러가 발생해도 통계가 기록됨
    try:
        analyzer.run({"articles": None})
    except:
        pass

    assert analyzer.get_stats()["errors"] == 1
```

## 📝 비고 (Notes)

특이 주의할 사항이나 제약사항을 적으세요.

- `validate_input()`을 오버라이드하여 입력 검증 커스터마이즈 가능
- `validate_output()`을 오버라이드하여 출력 검증 커스터마이즈 가능
- 에러 발생 시 `log_error()`가 자동 호출됨
- 환경변수 `AGENT_LOG_TO_FILE=true` 설정 시 파일에 로그 저장

## 🔗 관련 링크

- BaseAgent API: `base_agent.py` 참고
- PipelineAgent 사용법: `pipeline_agent.py` 참고
- 테스트 가이드: `tests/README.md` 참고

## 📚 추가 예시

### PipelineAgent와 함께 사용

```python
from pipeline_agent import PipelineAgent

# 다른 에이전트와 연결
pipeline = PipelineAgent(
    name="my_pipeline",
    agents=[
        PreviousAgent(),  # 앞 단계
        MyAgent(),        # 이 에이전트
        NextAgent()       # 다음 단계
    ]
)

result = pipeline.run({"input": "data"})
```

### 설정 전달

```python
# 설정 객체로 에이전트 커스터마이즈
config = {
    "max_retries": 3,
    "timeout": 30,
    "custom_param": "value"
}

agent = MyAgent(config)
result = agent.run({"data": "..."})

# 설정 확인
print(agent.config)  # {"max_retries": 3, ...}
```

## 💡 코드 템플릿

```python
#!/usr/bin/env python3
"""
에이전트 이름

에이전트 목적 설명
- 단일 책임: 무엇만 담당하는지
"""

from typing import Dict, Any, List, Optional
from base_agent import BaseAgent, AgentError


class MyAgent(BaseAgent):
    """에이전트 설명"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정
        """
        super().__init__("my_agent", config)

        # 설정에서 값 읽기
        self.some_setting = self.config.get("setting", "default_value")

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증 (선택 오버라이드)"""
        required_keys = ["required_key"]
        return all(key in data for key in required_keys)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 처리 (필수 구현)

        Args:
            data: 입력 데이터

        Returns:
            처리 결과
        """
        # 비즈니스 로직 구현
        input_value = data["required_key"]

        # 처리
        result = self._do_something(input_value)

        # 결과 반환
        return {"result": result}

    def _do_something(self, value: str) -> str:
        """내부 헬퍼 메서드"""
        # 실제 처리 로직
        return value.upper()
```
