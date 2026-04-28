# 형님(류웅수) DESIGN.md 시스템

> **목적:** 모든 산출물(블로그·러닝 코치 앱·HTML 시각화·전자책·강의)의 voice·시각·행동 가이드를 한 곳에 정리. AI 도구(Claude Design / Claude Code / Cursor / 미래 도구) 모두 자동 인식.
>
> **상태 (2026-04-28):** Phase 2 완료 — 폴더 + README. Phase 3 (_meta_DESIGN.md) 진행 중.

---

## 폴더 구조

```
agents/design/
├── README.md                    # 이 파일 (시스템 안내·운영 원칙)
├── _meta_DESIGN.md              # ⭐ 마스터 — 형님 voice·정체성 (모든 도메인의 기반)
├── domains/                     # 도메인별 sub-DESIGN.md (각자 표준 9 sections)
│   ├── blog-naver.md            # 네이버 블로그 (글·이미지·해시태그·톤)
│   ├── running-coach-app.md     # 러닝 코치 앱 UI·UX (Whoop/Runna 톤)
│   ├── visualization.md         # /시각화 HTML (Inter+Noto·차트·모바일)
│   ├── ebook.md                 # 전자책 DOCX (해상도 시리즈)
│   ├── coach-voice.md           # 러닝 코치 멘트 (친동생·약어 금지)
│   └── ... (점진 확장)
├── _references/                 # 외부 영감 (참고만, 직접 적용 X)
│   ├── whoop.md                 # 회복+데이터 시각화
│   ├── runna.md                 # 러닝 트레이닝 UX
│   ├── linear.md                # 미니멀 productivity
│   └── ...
├── _legacy/                     # 기존 흩어진 자산 매핑 (마이그레이션 출처)
│   └── audit-2026-04-28.md      # Phase 1 audit 결과
└── HOW_TO_USE.md                # 도구별 적용 절차 (Claude Design 업로드 / CLAUDE.md hook 등)
```

---

## 운영 원칙 (5개)

### 1. 마스터 1개 + 도메인 sub
- **`_meta_DESIGN.md` = 형님 voice·정체성·핵심 원칙** (한 곳, 짧게)
- **`domains/*.md` = 산출물별 구체 룰** (각자 9 sections + Don'ts)
- 도메인은 메타를 import (`@_meta_DESIGN.md` 명시)

### 2. 표준 spec 따른다 (Google Stitch / google-labs-code/design.md)
- YAML frontmatter (machine-readable tokens)
- Markdown body (human-readable rationale)
- 9 sections: Brand Voice → Color → Typography → Spacing → Components → Motion → Iconography → Accessibility → **Don'ts (마지막)**

### 3. **하이브리드** — 표준 + 우리 강점
- 표준 spec 위에 우리 자동화 시스템 전용 cheatsheet 추가 가능
- 추가 섹션은 `## 🛠️ Tooling` 또는 `## 🚨 Anti-heuristics`로 명시
- 표준 도구 (Claude Design / Cursor)는 표준 섹션만 읽음. 우리 자동화는 추가 섹션도 활용

### 4. 기존 흩어진 자산은 점진 마이그레이션 (안전 원칙)
- 기존 파일 (blog-image.md / blog-writer-naver.md / 시각화.md / running_*.py) **즉시 변경 X**
- Phase 별로 도메인 sub 작성 시 해당 자산을 참조 (= 표준 형식으로 옮김)
- 마이그레이션 완료 시 기존 파일은 sub를 import 하는 얇은 래퍼로 축소
- **절대 한 번에 다 갈아엎지 않음 (regression 위험)**

### 5. SPoE 원칙 적용
- 한 가이드는 한 곳에만 (Single Point of Edit)
- 변경 발생 시 마스터 → 도메인 sub 순서로 전파
- 기존 산출물 자동화는 design/ 모듈을 reference 하는 형태로 점진 전환

---

## 도구별 적용 (`HOW_TO_USE.md` 참고)

| 도구 | 적용 방식 |
|---|---|
| **Claude Code** | `~/.claude/CLAUDE.md`에 `@/path/to/_meta_DESIGN.md` import. 모든 세션 자동 적용 |
| **Claude Design** (claude.ai/design) | `_meta_DESIGN.md` 또는 도메인 sub 1개 업로드. 그 채팅 세션에 적용 |
| **Cursor / Windsurf / v0** | 프로젝트 root에 DESIGN.md symlink (또는 사본) |
| **우리 자동화 (blog-image 등)** | 점진적으로 design/domains/* 를 reference (Phase 7+) |

---

## 단계별 로드맵

| Phase | 작업 | 상태 |
|---|---|---|
| 1 | 자산 audit | ✅ 완료 (2026-04-28) |
| 2 | 폴더 + README 신설 | ✅ 완료 (2026-04-28) |
| 3 | `_meta_DESIGN.md` 작성 (형님 voice 표준 spec) | 🚧 진행 중 |
| 4 | Claude Code hook (`~/.claude/CLAUDE.md` @import 안내) | 대기 |
| 5 | HARNESS_DOMAIN_REGISTRY.md 갱신 | 대기 |
| 6 | 첫 도메인 sub: `blog-naver.md` | 대기 |
| 7 | 점진 마이그레이션 (기존 자동화 → design/ reference) | 점진 |
| 8 | references 큐레이션 (Whoop/Runna/Linear 등 5~10개) | 점진 |

---

## 안전 원칙 (반복 강조)

- ✅ **신규 폴더만 추가** — 기존 파일 0건 수정
- ✅ **점진적 마이그레이션** — 검증 단계마다 형님 확인 후 진행
- ✅ **기존 자동화 정상 동작 유지** — 새 시스템이 완성·검증될 때까지 기존 가이드 그대로 사용
- ✅ **롤백 가능** — design/ 폴더 통째로 삭제하면 원상 복구

---

## 변경 로그

- **2026-04-28**: 폴더 + README 신설 (Phase 2 완료)
