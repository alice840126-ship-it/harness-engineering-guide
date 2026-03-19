# ObsidianNoteCreator 에이전트 PRD

## Purpose
옵시디언 데일리 노트를 자동으로 생성하는 에이전트. YAML frontmatter가 포함된 템플릿을 지원하며, 매일 자동으로 실행되어 데일리 노트를 생성합니다.

## Inputs

### 메서드: `create_daily_note()`
- `vault_path` (str): 옵시디얼 볼트 경로
- `date` (datetime.date, optional): 생성할 날짜 (기본: 오늘)
- `template_type` (str, optional): 템플릿 타입 (기본: "default")
- `custom_goals` (list, optional): 커스텀 핵심 목표

### 메서드: `create_note()`
- `vault_path` (str): 옵시디얼 볼트 경로
- `filename` (str): 파일명 (확장자 제외)
- `folder` (str, optional): 저장할 폴더 (기본: 루트)
- `content` (str): 노트 내용
- `frontmatter` (dict, optional): YAML frontmatter 데이터

## Outputs

### create_daily_note()
- `str`: 생성된 파일 경로
- `None`: 이미 존재하거나 생성 실패

### create_note()
- `str`: 생성된 파일 경로
- `None`: 생성 실패

## Usage

### 데일리 노트 생성
```python
from obsidian_note_creator import ObsidianNoteCreator
from datetime import date

creator = ObsidianNoteCreator(vault_path="/path/to/vault")

# 오늘 데일리 노트 생성
file_path = creator.create_daily_note()

# 특정 날짜 데일리 노트 생성
file_path = creator.create_daily_note(
    date=date(2026, 3, 19),
    custom_goals=["운동", "명상"]
)
```

### 일반 노트 생성
```python
# 프로젝트 노트 생성
file_path = creator.create_note(
    filename="my-project",
    folder="Projects",
    content="# 프로젝트 개요\n\n설명...",
    frontmatter={
        "tags": ["project", "active"],
        "created": "2026-03-19"
    }
)
```

## Reuse Locations

1. **데일리 노트 자동화**
   - `~/.claude/scripts/create_daily_note.py` - Launchd로 매일 07:00 실행
   - 매일 아침 자동으로 데일리 노트 생성

2. **프로젝트 관리**
   - 새 프로젝트 시작 시 프로젝트 노트 자동 생성
   - 프로젝트 템플릿 적용

3. **Zettelkasten 시스템**
   - 영구 노트(Permanent Note) 생성
   - 문헌 노트(Literature Note) 생성

## Dependencies

- **Python 내장**: pathlib, datetime, os
- **외부**: 없음

## Tests

1. **데일리 노트 생성 테스트**
   - 오늘 날짜로 데일리 노트 생성
   - YAML frontmatter 올바른지 확인
   - 폴더 구조 (YYYY/MM월/) 올바른지 확인

2. **이미 존재하는 노트 처리 테스트**
   - 이미 존재하면 None 반환
   - 덮어쓰기 하지 않음

3. **커스텀 목록 테스트**
   - 커스텀 핵심 목표 적용
   - 커스텀 템플릿 적용

4. **일반 노트 생성 테스트**
   - YAML frontmatter 추가
   - 폴더 생성 확인

5. **경로 처리 테스트**
   - 상대 경로/절대 경로 모두 지원
   - 한국어 폴더명 지원

## Notes

### 템플릿 구조
```yaml
---
TYPE: "[[YYYY-MM-DD]]"
tags:
  - daily-note
date: YYYY-MM-DD
date created: YYYY-MM-DD
date modified: YYYY-MM-DD
---
```

### 폴더 구조
```
vault/
└── 30. 자원 상자/
    └── 01. 데일리 노트/
        ├── 2026/
        │   ├── 01월/
        │   │   ├── 2026-01-01.md
        │   │   └── ...
        │   ├── 02월/
        │   └── ...
```

### 기존 ObsidianWriter와의 차이점
- **ObsidianWriter**: 범용 옵시디언 노트 작성 (영구 노트, Zettelkasten 등)
- **ObsidianNoteCreator**: 데일리 노트 특화 (날짜 기반 폴더 구조, 자동 실행)

### 통합 방법
데일리 노트 생성 후 ObsidianWriter로 내용 추가 가능:
```python
creator = ObsidianNoteCreator()
file_path = creator.create_daily_note()

# 이후 내용 추가
writer = ObsidianWriter()
writer.append_to_note(file_path, "## 추가 내용\n\n...")
```
