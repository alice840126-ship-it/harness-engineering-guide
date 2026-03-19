# ContextCollector 에이전트 PRD

## Purpose
Claude와 사용자 간의 대화 기록에서 중요한 컨텍스트(결정, 선호도, 패턴, 인사이트)를 자동으로 추출하고 저장하는 에이전트. 형님이 "기억해/기록해"라고 하기 전에 자동으로 맥락을 수집합니다.

## Inputs

### 메서드: `collect_context()`
- `history_file` (str): Claude 세션 기록 파일 경로 (.jsonl)
- `patterns` (dict, optional): 커스텀 패턴 정의
- `limit` (int, optional): 분석할 최근 세션 수 (기본: 50)

### 메서드: `analyze_session()`
- `session` (dict): Claude 세션 데이터 (messages 배열)

### 메서드: `update_shared_context()`
- `insights` (str): 생성된 인사이트
- `shared_context_path` (str): Shared Context 파일 경로

## Outputs

### collect_context()
- `dict`: 발견한 패턴 {"결정": [], "선호도": [], "패턴": [], "인사이트": []}

### analyze_session()
- `dict`: 세션에서 발견한 패턴

### update_shared_context()
- `bool`: Shared Context 업데이트 성공 여부

## Usage

### 기본 사용
```python
from context_collector import ContextCollector

collector = ContextCollector()

# 컨텍스트 수집
findings = collector.collect_context(
    history_file="~/.claude/history.jsonl",
    limit=50
)

print(f"결정: {len(findings['결정'])}개")
print(f"선호도: {len(findings['선호도'])}개")
```

### 커스텀 패턴
```python
custom_patterns = {
    "투자": [
        r"(주식|코인|부동산)(.*?)(매수|매도|확정)",
        r"(투자)(.*?)(결정|완료)"
    ],
    "일정": [
        r"(내일|다음 주)(.*?)(예약|확정)",
        r"(약속)(.*?)(하기로)"
    ]
}

findings = collector.collect_context(
    history_file="~/.claude/history.jsonl",
    patterns=custom_patterns
)
```

### Shared Context 업데이트
```python
insights = collector.generate_insights(findings)
collector.update_shared_context(
    insights=insights,
    shared_context_path="~/.claude-unified/shared_context.md"
)
```

## Reuse Locations

1. **자동 컨텍스트 수집**
   - 매시간 자동 실행 (LaunchAgent)
   - Claude가 형님의 선호도를 자동으로 학습

2. **세션 요약**
   - 대화 세션 종료 시 주요 결정사항 추출
   - 데일리 브리핑 생성

3. **프로젝트 관리**
   - 프로젝트 관련 결정사항 추적
   - 비즈니스 인사이트 자동 저장

## Dependencies

- **Python 내장**: json, re, datetime, pathlib
- **외부**: 없음

## Tests

1. **패턴 추출 테스트**
   - 결정 패턴 추출 확인
   - 선호도 패턴 추출 확인
   - 복합 패턴 추출 확인

2. **세션 분석 테스트**
   - 사용자 메시지에서 패턴 추출
   - Assistant 응답에서 문맥 추출

3. **인사이트 생성 테스트**
   - 발견한 패턴을 인사이트로 변환
   - 마크다운 포맷 확인

4. **Shared Context 업데이트 테스트**
   - 새로운 섹션 추가
   - 기존 섹션 업데이트

5. **파일 처리 테스트**
   - 존재하지 않는 history 파일 처리
   - 빈 세션 처리
   - 잘못된 JSON 처리

## Notes

### 기본 패턴 정의
```python
PATTERNS = {
    "결정": [
        r"(결정|확정|예약|신청|완료)(했어야?|할게|할께)",
        r"(하기로|하기로 햠|하기로 함)",
        r"(OK|오키|좋아|그래|알았어)",
    ],
    "선호도": [
        r"(좋아|좋아하는|선호|우선순위)",
        r"(싫어|별로|안 좋아|비추)",
        r"(필수|조건|요구사항)",
    ],
    "패턴": [
        r"(매일|매주|매달|항상|보통)",
        r"(루틴|습관|패턴)",
    ],
    "인사이트": [
        r"(투자|부동산|전략|비즈니스)(.*?)(핵심|중요|필수)",
        r"(인사이트|통찰|교훈)",
    ]
}
```

### history.jsonl 형식
```json
{
  "timestamp": "2026-03-19T10:30:00",
  "messages": [
    {"role": "user", "content": "내일 오전 10시로 예약해"},
    {"role": "assistant", "content": "내일 오전 10시로 예약 완료했습니다."}
  ]
}
```

### Shared Context 업데이트 방식
```markdown
## 학습된 패턴

### 최근 결정
- 최근 5개의 결정 패턴 발견

### 선호도
- 3개의 선호도 패턴 발견

### 반복 패턴
- 2개의 반복 패턴 발견
```

### 학습 데이터 저장
```json
{
  "2026-03-19": {
    "결정": ["내일 오전 10시로 예약", "주식 매수 결정"],
    "선호도": ["오전 일정 선호", "조용한 카페"],
    "패턴": ["매일 아침 명상"],
    "인사이트": ["시간 약속을 엄수함"]
  }
}
```

### 통합 방법
```python
# 자동 실행 (매시간)
collector = ContextCollector()
findings = collector.collect_context()
collector.save_patterns(findings)

# Shared Context 업데이트
insights = collector.generate_insights(findings)
collector.update_shared_context(insights)
```
