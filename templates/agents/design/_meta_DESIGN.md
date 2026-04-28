---
# 형님(류웅수) 메타 DESIGN.md — 마스터 voice·정체성
# 표준 spec: google-labs-code/design.md (YAML frontmatter + Markdown body)
# 모든 도메인 sub은 이 파일을 import 한다 (`@design/_meta_DESIGN.md`)

brand:
  name: "류웅수 / 구해줘 부동산"
  honorific: "형님"   # 사용자 호칭 (모든 자동화에 적용)
  timezone: "Asia/Seoul"
  language: "ko"

voice:
  archetypes:
    - "압도적 실행력"      # CLAUDE.md 정의
    - "본질 추구"
    - "효율 중시"
  philosophy:
    - "스토아 (마르쿠스 아우렐리우스)"
    - "멘탈모델 (Charlie Munger)"
  default_tone: "친근한 경어체 + 친동생 텐션"
  formality: "high"          # 공적 산출물(블로그·전자책)은 합쇼체 강제
  formality_exceptions:
    - "russell_chat: 형님과 대화할 때만 편한 말투 + 형님 호칭"
    - "coach_voice: 친동생 톤 (~해요/~네요/~가요)"

audience:
  primary: "한국 30~50대 직장인·예비 자영업자·부동산 관심층"
  secondary: "러닝 입문~중급자, 마라톤 준비자"
  literacy: "비전문가 — 영문 약어·전문 용어 풀어 써야 함"

design_principles:
  - "정확성 > 화려함 — 추측·과장 금지, 출처 없는 수치 금지"
  - "간결 > 디테일 — 짧게 핵심만, 5단락 안에 결론"
  - "독자 수준 맞춤 — 비전문가에겐 풀어 쓰고, 전문가/전문 영역에선 정확한 용어 그대로 사용 (도메인 sub에서 cheatsheet 정의)"
  - "다양성 > 일관성 강박 — 글마다 다른 톤·시각 OK, 한 글 안에서만 통일"
  - "재사용 > 중복 — SPoE 원칙 (같은 가이드 두 곳에 두지 않기)"

# color_default / typography_default 의미:
#   "모든 산출물의 기본 색·폰트 토큰 (디폴트값). 도메인 sub에서 카테고리별 override 가능."
#   예: 부동산 글은 accent_warm(Terra) 사용, 분석 글은 accent_cool(Steel Blue) 사용.
#   /시각화·러닝 코치 앱·블로그 커버 등에 자동 적용되어 시각 일관성 유지.

color_default:
  primary: "#1A1C1E"          # Ink Black — 본문 텍스트·강조
  secondary: "#6C7278"        # Graphite — 보조 텍스트·라벨
  accent_warm: "#B8422E"      # Terra — 부동산·따뜻한 카테고리
  accent_cool: "#345D7E"      # Steel Blue — 분석·데이터·신뢰
  surface_light: "#F7F5F2"    # Paper — 기본 밝은 배경
  surface_dark: "#111317"     # Ink — 다크 모드 배경

typography_default:
  korean: "Noto Sans KR"      # 본문·UI 한글
  latin: "Inter"              # 영문·숫자
  display_weight: 700         # 큰 제목 (display·H1)
  body_weight: 400            # 본문
  caption_weight: 300         # 캡션·각주

forbidden_phrases:
  # 모든 산출물 공통 금지어 (블로그·시각화·이메일 등 전 도메인 적용)
  - "다양한 측면에서"
  - "종합적으로"
  - "이처럼"
  - "이에 따라"
  - "이를 통해"
  - "도움이 되셨으면"
  - "활용"
  - "기반으로 한"
  - "뿐만 아니라"
  - "더불어"
  - "나아가"
  - "제시합니다"
  - "소개합니다"
  - "본 글에서는"
  - "~적인 남발 (종합적인·효과적인·실질적으로)"

# 도메인 전용 cheatsheet (영문 약어 풀이 등)는 메타에 두지 않음.
# coach-voice / running-blog 등 해당 도메인 sub에서 정의.
# 메타는 "독자 수준에 맞춰 용어 풀이는 도메인별로 정의" 원칙만 둔다 (위 design_principles 참조).
---

# 형님(류웅수) 메타 DESIGN.md

> 모든 산출물의 voice·정체성 마스터. 도메인 sub은 이 파일을 기반으로 9 sections 표준에 맞춰 확장한다.

---

## 1. Brand Voice & Overview

**누구:** 류웅수 (호칭 "형님"). **1984년생**, 한국. 구해줘 부동산 운영(지식산업센터 전문). 공인중개사 1차 준비 중. 가족: 아내 이소연, 딸 시아(9살). 압도적 실행력으로 다중 도메인(부동산·블로그·러닝·앱 개발·교육) 운영.

**철학:** 스토아 + 멘탈모델. 본질 추구·효율 중시·정확성 우선.

**산출물에 깔리는 5개 톤 원칙:**

1. **정확성** — 추측·과장·반올림 부풀림 금지. 출처 없는 수치 금지. 모르면 "확인 필요"
2. **간결성** — 5단락 안에 결론. 디테일은 부록으로
3. **독자 수준 맞춤** — 비전문가용 글은 풀어 쓰고, 전문가/전문 영역(법령·계약·기술 spec 등)에선 정확한 용어 그대로 사용. 도메인 sub에서 cheatsheet 정의
4. **다양성** — 글마다 다른 톤·시각 시도. 한 글 안에서만 통일
5. **재사용성** — 한 가이드는 한 곳에만 (SPoE)

**감정 기조:** 친근하면서 단호. 진단은 직설적, 응원은 따뜻하게.

**문체 정의 (헷갈리지 않게):**
- **합쇼체** = "~합니다 / ~습니다 / ~입니다 / ~했습니다" 형태 (격식체 중 가장 정중) — 블로그·전자책·공적 글 강제
- **해라체** = "~다 / ~이다 / ~한다 / ~했다" 형태 (반말 진술형) — 공적 글에 혼용 절대 금지
- **친근 경어체** = "~해요 / ~네요 / ~가요" 형태 — 러닝 코치 멘트·UI 텍스트
- **반말 (편한 말투)** = "~지 / ~잖아 / ~어" — 형님과 채팅 대화에만

---

## 2. Color Palette

### Core Neutrals
| 토큰 | Hex | 역할 |
|---|---|---|
| Paper | `#F7F5F2` | 기본 배경, 페이퍼 톤 영역 |
| Ink Black | `#1A1C1E` | 본문 텍스트, 강조 |
| Graphite | `#6C7278` | 보조 텍스트, 라벨 |
| Stone Gray | `#A8A29A` | 구분선, 비활성 |

### Signal Accents
| 토큰 | Hex | 역할 |
|---|---|---|
| Terra | `#B8422E` | 부동산·전통·따뜻한 카테고리 |
| Steel Blue | `#345D7E` | 분석·데이터·신뢰 |
| Forest | `#34C759` | 성공·통과·완료 (✅) |
| Amber | `#FF9500` | 주의·팁 (💡) |
| Crimson | `#FF3B30` | 경고·위험 (⚠️) |

> 도메인 sub에서 카테고리별 팔레트 override 가능. 기본 신호색 5개는 일관 유지.

---

## 3. Typography

### 폰트 패밀리
| 용도 | 한글 | 영문/숫자 |
|---|---|---|
| 본문·UI | Noto Sans KR | Inter |
| 데이터·코드 | (해당 없음) | JetBrains Mono / Menlo |
| 캘리그래피 (필요 시) | Calligraphy / Ink Wash | (사용 안 함) |

### 타입 스케일 (9 levels)
| 레벨 | Size (px) | Weight | 용도 |
|---|---|---|---|
| display_xl | 56 | 700 | 히어로 타이틀 (랜딩·시각화) |
| display_lg | 40 | 700 | H1 |
| headline | 28 | 600 | H2 |
| title | 22 | 600 | H3 / 카드 제목 |
| body_lg | 18 | 400 | 본문 (블로그·기사) |
| body | 15 | 400 | 본문 (UI·대시보드) |
| body_sm | 13 | 400 | 보조 텍스트 |
| label | 12 | 500 | 라벨·태그 |
| caption | 11 | 400 | 출처·푸터 |

### 한글 가독성 룰
- 한글 본문은 `line-height: 1.6` 이상
- 영문·숫자는 `letter-spacing: -0.01em`로 한글과 시각 균형
- 숫자는 영문 폰트 (Inter) 강제 — 한글 폰트의 숫자는 가독성 떨어짐

---

## 4. Spacing & Layout

### 8pt 그리드
모든 spacing은 8의 배수: `8 / 16 / 24 / 32 / 48 / 64 / 96`

### 컨테이너
- 모바일 우선 (형님 결과물 70%가 폰에서 소비됨)
- 콘텐츠 max-width: 720px (블로그) / 1200px (대시보드)
- side padding: 16px (모바일) / 32px (태블릿+) / 64px (데스크탑+)

### 카드
- border-radius: 12~16px (모던하지만 과하지 않게)
- shadow: `0 2px 8px rgba(0,0,0,0.06)` (얕게)
- 카드 간 gap: 16~24px

---

## 5. Components

### 기본 패턴 (도메인 sub에서 구체화)

- **Button:** Primary (Steel Blue) / Secondary (outline) / Tertiary (text only). 높이 44px (터치 타겟)
- **Card:** title (title) + body (body) + footer (caption). 그림자 얕게
- **Coach Box:** signal color (warn/tip/ok) 좌측 4px border + 상단 아이콘 + 4 bullets
- **Data Table:** 헤더 굵게 (label), zebra stripe 없음, 행 간격 8px
- **Hashtag:** `#키워드` 형식, label weight, 회색 배경 round-pill

> 자세한 컴포넌트는 `domains/visualization.md` / `domains/running-coach-app.md` 참조

---

## 6. Motion

- **원칙: 최소화** (모션이 정보 전달 방해 안 되게)
- 페이드: 200ms ease-out
- 슬라이드: 300ms ease-out
- 데이터 카운터 애니메이션: 600ms (`/시각화` HTML)
- 호버: 100ms (즉각 반응)

---

## 7. Iconography & Imagery

### 아이콘
- 시스템 아이콘: 시각적 일관성을 위해 1개 라이브러리만 (Lucide / SF Symbols)
- 시각 아이콘 (signal): `✅ ⚠️ 💡 🎯 💪 💚 ❤️ 📊 📈 📉 🛋️ 🥃 ☕ 🥐` 등 이모지 OK (친근감)

### 이미지 스타일 (블로그·HTML)
- 35종 비주얼 스타일 카탈로그 (`domains/blog-naver.md`에 자세히)
- 카테고리별 후보 풀 (`domains/blog-naver.md` 라우터 참조)
- **한 글 = 한 스타일** 원칙 (절대 규칙)
- 글과 글 사이는 다양성 추구 (직전 1~2개 스타일 회피)

---

## 8. Accessibility

- 본문 대비비 4.5:1 이상 (WCAG AA)
- 인터랙티브 요소 터치 타겟 44×44px 이상
- 색상에만 의존하는 정보 전달 금지 (signal 색상 + 아이콘 + 텍스트 함께)
- 모바일 우선 + iOS Telegram 웹뷰 호환 (`/시각화` 룰 참조)

---

## 9. 🚫 Don'ts (절대 금지 — 위반 시 글/UI 폐기 또는 재작성)

### 9.1 글쓰기 금지

**문체:**
- ❌ 해라체와 합쇼체 혼용 (한 글 안에서)
- ❌ 도메인 cheatsheet에 명시된 영문 약어를 비전문가용 글에 그대로 사용 (각 도메인 sub의 `forbidden_jargon` 참조)
- ❌ "친절히 설명" 빙자한 약어 사용 ("XYZ는 ~이라는 뜻인데..." 식 금지 — 처음부터 풀어 쓸 것)
- ❌ 추측 수치 / 출처 없는 비교 / "약·거의·가까이·넘게" 부풀림
- ⚠️ 단, 전문가 대상 글(법령·계약·기술 spec)은 약어 그대로 사용 OK — 도메인 sub가 결정

**AI 말투 7패턴 (blog-writer-naver에서 가져옴):**
1. ❌ 단조로운 종결 반복 (~입니다/~습니다만 무한)
2. ❌ 과도한 접속사 ("따라서, 그러므로, 또한, 게다가")
3. ❌ 기계적 나열 (1위·2위·3위만 반복)
4. ❌ 감정 없는 정보 전달 (스펙만 나열)
5. ❌ 강조어 남발 ("매우, 굉장히, 정말로, 가장, 최고의" 섹션당 2개 이상)
6. ❌ 동일 문장 구조 반복 (모든 문장이 같은 길이·패턴)
7. ❌ 두괄식 일변도 (결론부터만 반복)

**금지 표현 (위 frontmatter `forbidden_phrases` 참조)**

### 9.2 데이터·분석 금지

- ❌ 데이터 윈도우 라벨 사기 ("rolling 7일"을 "이번 주(월~일)"로 바꿔치기)
- ❌ 반올림 부풀림 (35% → "약 40%")
- ❌ 단지명/시공사/세대수 검증 없이 작성 (잠실 르엘 사고 같은 거 재발 금지)
- ❌ 옵시디언 vault를 1차 소스로 사용 (옛날 자료 섞임)

### 9.3 시각·이미지 금지

- ❌ 한 글 안에 여러 비주얼 스타일 섞기
- ❌ 카테고리 자동 매핑만으로 스타일 결정 (본문 톤·감정도 고려)
- ❌ 같은 카테고리 글 3개 연속에 같은 스타일 (다양성 회피)
- ❌ Blueprint 계열(#20~#23)을 부동산·스포츠·세금 글에 자동 적용 (안티 휴리스틱)
- ❌ AI 이미지에 영문 텍스트 생성 ("no text" 강제)
- ❌ 옵시디언 vault에 이미지 직접 저장 (인덱싱 부하 — `/Desktop/류웅수/블로그/images/` 사용)

### 9.4 자동화·시스템 금지

- ❌ Pre-Write Protocol 우회 (CLAUDE.md 최상단 규칙)
- ❌ 형님이 수동으로 할 수 있는 일을 떠넘기기 ("형님이 ~해주세요")
- ❌ 한 번 실패로 "불가능" 결론 (체크리스트 전부 시도 후에만 보고)
- ❌ 같은 SPoE를 여러 곳에 복제 (한 가이드 = 한 위치)

---

## 🛠️ Tooling Notes (우리 자동화 시스템 전용 — 표준 spec 외)

> 이 섹션은 표준 DESIGN.md spec에 없는 우리 시스템 전용 메타데이터.
> Claude Design / Cursor 등 외부 도구는 이 섹션 무시 가능.
> 우리 자동화 (blog-image, running_coach 등)는 이 섹션 적극 활용.

### 도메인 sub 매핑
| 산출물 | 도메인 sub | 기존 자산 (마이그레이션 출처) |
|---|---|---|
| 네이버 블로그 (글+이미지) | `domains/blog-naver.md` | `blog-writer-naver.md` + `blog-image.md` |
| 러닝 코치 멘트 | `domains/coach-voice.md` | `running_coach_agent.py` 프롬프트 |
| 러닝 블로그 | `domains/running-blog.md` | `running_blog_writer.py` 프롬프트 |
| /시각화 HTML | `domains/visualization.md` | `~/.claude/commands/시각화.md` |
| 전자책 (해상도 시리즈) | `domains/ebook.md` | `orchestration-blog-book.md` |
| 러닝 코치 앱 (RN+Expo) | `domains/running-coach-app.md` | `~/alice-github/running-coach-app/` |
| 부동산 콘텐츠 | `domains/realestate.md` | (현재 분산 — 신규 정의 필요) |
| 강의·발표 | `domains/education.md` | (현재 분산 — 신규 정의 필요) |

### 자동화 hook 예정 위치
- `~/.claude/CLAUDE.md` 상단에 `@/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/design/_meta_DESIGN.md` import (Phase 4)
- `agent_registry.py`에 `design/_meta_DESIGN.md`도 인덱싱 (Phase 5)

---

## 🚨 Anti-Heuristics (반복되는 함정 — 우리 시스템 전용)

> 시간이 지나면서 LLM이 자꾸 빠지는 패턴들. 도메인 sub에서 더 구체화.

1. **Blueprint 자동 수렴** — 본문에 표·일정 있다고 #21/#23 자동 선택 (실제 사례: 4/28 5개 글 중 3개) → 카테고리 게이트 우선
2. **약어 풀이 빙자한 약어 사용** — 도메인 sub `forbidden_jargon`에 잡힌 용어를 "친절히 설명" 빙자해 등장시키지 말 것 (처음부터 풀어쓰기)
3. **카테고리 자석** — 형님 본업 부동산으로 모든 분석 자동 수렴 (`feedback_breadth_over_business.md`) → 11개+ 카테고리 골고루
4. **stale 제목 패턴** — "ACWR 248128" 같이 약어+숫자 조합 → 일상어 제목
5. **vault 자료 오염** — 옛날 옵시디언 노트를 최신으로 오인 → 웹 데이터만 1차 소스
6. **단발 실패로 포기 선언** — 한 번 실패로 "불가능" → 체크리스트 끝까지

---

## 변경 로그

- **2026-04-28**: v0.1 초안 작성 (Phase 3) — 기존 흩어진 가이드를 표준 spec 9 sections + 형님 자산 추출로 통합
- 차후 변경 시 형님 검수 → 도메인 sub로 전파
