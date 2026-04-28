# HOW_TO_USE — DESIGN.md 도구별 적용 절차

> 같은 DESIGN.md 파일을 여러 도구가 다 인식. 도구별 적용 방식만 다름.

---

## 1. Claude Code (가장 자동화됨 — 권장 1순위)

### 방법: `~/.claude/CLAUDE.md`에 @import

`~/.claude/CLAUDE.md` 상단에 한 줄 추가:

```markdown
@/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/design/_meta_DESIGN.md
```

→ **모든 Claude Code 세션이 자동으로 메타 voice 인식.** 매번 업로드 불필요.

### 도메인별 import (선택)

특정 작업에서만 도메인 sub 적용하고 싶으면 그 작업 시작 시 명시:

```
@design/domains/blog-naver.md 따라서 블로그 글 써줘
```

또는 작업 폴더에 symlink:
```bash
ln -s /Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/design/domains/blog-naver.md \
      /path/to/project/DESIGN.md
```

---

## 2. Claude Design (claude.ai/design)

### 방법: 채팅에 업로드

1. https://claude.ai/design 접속
2. 새 프로젝트 또는 채팅 시작
3. **DESIGN.md 파일 업로드** — `_meta_DESIGN.md` 또는 도메인 sub 1개
4. 그 채팅 세션 동안 자동 적용

### 형님 권장 패턴
- **블로그 작업**: `domains/blog-naver.md` 업로드
- **러닝 앱 UI**: `domains/running-coach-app.md` 업로드
- **HTML 시각화**: `domains/visualization.md` 업로드
- **메타 voice만 원할 때**: `_meta_DESIGN.md` 업로드

### 한계
- 채팅 세션마다 다시 업로드 필요 (Claude Code처럼 자동 import 없음)
- 단, 한 채팅 안에서는 모든 메시지에 적용

---

## 3. Cursor / Windsurf / Kiro / v0 / Lovable

### 방법: 프로젝트 root에 DESIGN.md

대부분의 AI 코딩 도구는 프로젝트 root의 `DESIGN.md`를 자동 읽음.

```bash
# 프로젝트 root에 sym (마스터 사용)
cd /path/to/your/project
ln -s /Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/design/_meta_DESIGN.md DESIGN.md

# 또는 도메인 sub 사용
ln -s /Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/design/domains/running-coach-app.md DESIGN.md
```

### 우리 케이스 적용 예시
- **러닝 코치 앱** (`~/alice-github/running-coach-app/`): `running-coach-app.md` symlink
- **하네스 가이드** (`~/alice-github/harness-engineering-guide/`): `_meta_DESIGN.md` symlink

---

## 4. 우리 자체 자동화 (blog-image / running_coach 등)

### Phase 7+ (점진 마이그레이션 후)

기존 `blog-image.md`, `blog-writer-naver.md`, `running_coach_agent.py` 등이 점진적으로 `design/domains/*.md`를 reference 하는 형태로 전환.

### 마이그레이션 패턴 (예시)

**Before** (blog-image.md 단독):
```
[562줄의 자세한 룰]
```

**After** (얇은 래퍼):
```markdown
# blog-image agent

너는 design/domains/blog-naver.md의 "이미지 섹션"을 따른다.

@/Users/oungsooryu/.../design/domains/blog-naver.md

추가 작업별 지침:
- ...
```

→ 핵심 룰은 `design/`에 한 곳, 자동화 파일은 사용·호출만 정의.

---

## 5. 운영 시나리오 — 형님 일상 use case

### 시나리오 A: "/블로그 키워드" 실행 시
1. `/블로그` 슬래시 커맨드 → orchestration-blog-naver.md 호출
2. (Phase 7 후) orchestration이 `design/domains/blog-naver.md` 자동 reference
3. 모든 글·이미지가 통일된 voice로 생성

### 시나리오 B: claude.ai/design에서 빠른 mockup
1. `domains/visualization.md` 업로드
2. "[데이터] 시각화 페이지 만들어줘" 입력
3. Inter+Noto·8pt 그리드·신호색 자동 적용된 HTML

### 시나리오 C: Cursor에서 러닝 코치 앱 컴포넌트 추가
1. 프로젝트 root에 `running-coach-app.md` symlink (한 번만)
2. Cursor에 "회복 카드 컴포넌트 만들어줘" 입력
3. 메타 voice + 앱 컴포넌트 룰이 자동 적용

### 시나리오 D: 새 도구 등장 (예: 미래의 X-AI)
1. 그 도구가 DESIGN.md 표준 인식하면 → 마스터 그대로 적용
2. 인식 안 하면 → 마스터 내용 prompt에 복붙 (수동)
3. **lock-in 없음 — 형님 자산은 plain markdown으로 보존**

---

## 6. 변경·운영 룰

### 변경 발생 시 SPoE 흐름
1. 변경 의도 발생
2. **`_meta_DESIGN.md`에 변경** (마스터)
3. 영향 받는 `domains/*.md` 갱신
4. 영향 받는 자동화 파일 (Phase 7+ 마이그레이션 완료된 곳만)

### 변경 로그 의무
- 모든 .md 파일 하단에 `## 변경 로그` 섹션 유지
- 날짜 + 한 줄 요약

### 검증 (분기 1회 권장)
- 산출물 샘플 5개 (블로그 1, 코치 카드 1, 시각화 1, 앱 1, 전자책 1) 모아 voice 일관성 점검
- 어긋난 부분 있으면 마스터·sub 갱신

---

## 7. 자주 받는 질문

**Q: 마스터 변경하면 기존 자동화 다 깨지나?**
A: 아니요. Phase 7 마이그레이션 완료된 자동화만 영향. 그 전엔 기존 가이드 그대로 작동.

**Q: 도메인 sub 없는 작업은 어떻게?**
A: 마스터 (`_meta_DESIGN.md`)만 적용. 새 도메인이 자주 쓰이면 그때 sub 신설.

**Q: Claude Design 업로드 한 번 하면 다른 채팅도 인식?**
A: 아니요. 채팅마다 다시 업로드 (또는 그 채팅 내에서만 적용). Claude Code 방식이 자동화엔 더 좋음.

**Q: 외부 references 폴더는 뭐냐?**
A: Whoop·Runna 같은 외부 디자인 시스템 영감용. 직접 적용 X, 형님 sub 만들 때 참고만.

---

## 변경 로그

- **2026-04-28**: 초안 작성 (Phase 4)
