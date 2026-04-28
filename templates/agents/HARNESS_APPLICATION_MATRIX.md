# 하네스 도구 × 기존 자동화 적용 매트릭스

**작성:** 2026-04-20
**목적:** 구축한 하네스 도구 8개를 형님 자동화 전반에 자동 적용하기 위한 인벤토리 + 매핑.
형님이 직접 쓰지 않음 — Claude가 해당 자동화를 건드릴 때마다 이 매트릭스 참조해서 자동으로 꽂음.

---

## 1. 하네스 원본 재스캔 — 우리가 적용한 것 vs 놓친 것

### ✅ 이미 적용 (8개 도구)
| 원본 Part | 우리 도구 |
|---|---|
| Part IV 프롬프트 캐싱 | `cache_hit_tracker.py`, `prompt_cache_hints.py` |
| Part VI 고급 하위시스템 (VERDICT) | `blog_verdict_agent.py`, `blog_rewrite_loop.py` |
| Part VII 교훈 (회로차단, 관찰성) | `pipeline_observer.py`, `session_checkpoint.py` |
| 범용 에이전트 디스커버리 | `agent_registry.py`, `image_dedup.py` |

### 🕳 놓친 원본 영역 — 다음 후보
| Part | 원리 | 후보 도구 | 우선순위 |
|---|---|---|---|
| **Part I** 아키텍처 (에이전트 루프) | loop 패턴 표준화 | `agent_loop_runner.py` — BaseAgent 확장 | 🟡 중 |
| **Part II** 시스템 프롬프트 = 제어 평면 | CLAUDE.md/서브에이전트 .md linter | `subagent_linter.py` — 섹션/금지어/토큰길이 체크 | 🟡 중 |
| **Part III** 컨텍스트 관리 (자동 압축, 토큰 예산) | `token_budget_tracker.py` — 세션 토큰 카운터 + 경고 | 🟢 하 |
| **Part V** 보안 (프롬프트 인젝션 방어, YOLO 분류기) | `injection_shield.py` — 외부 데이터 sanitize (web_data_scraper, 뉴스 본문 입력 전) | 🔴 **상** — 형님 자동화 중 외부 크롤링 많음 |
| Part VII 교훈 (서브에이전트 vs 오케스트레이션) | 이미 orchestrators/ 디렉토리로 반영됨 | — |

**결론:** 당장 진짜 구멍은 **Part V 주입 방어** 1건. 나머지는 nice-to-have.

---

## 2. 현재 자동화 전수 인벤토리

### 2-1. launchd 정기 실행 (7개)
```
brain-daily         (일일)   → brain_daily_monitor.py
brain-monthly-delta (월간)   → brain_monthly_delta.py
brain-stealer       (N/A)    → 슈퍼뇌 체인
marathon-watcher    (N/A)    → marathon_registration_watcher.py
news-thesis-bamboo-monthly   → news_thesis_bamboo.py --monthly
news-thesis-bamboo-weekly    → news_thesis_bamboo.py --weekly
teje-monitor                 → teje_monitor.sh
```

### 2-2. 오케스트레이터 (3개)
```
orchestrators/daily_news_pipeline.py
orchestrators/market_analysis_pipeline.py
orchestrators/blog_rewrite_loop.py   ← 방금 만든 것
```

### 2-3. 주요 스크립트 (규모순 TOP 10)
```
trend_hunter.py           (47K) — 트렌드 수집
news_thesis_bamboo.py     (35K) — 논문 파이프라인
meta_agent.py             (29K) — 아침 종합 브리핑 (루틴)
running_dashboard.py      (25K) — 마라톤 대시보드
news_scraper_refactored   (13K)
thinker_collector.py      (14K)
running_tracker.py        (14K)
weekly_report.py          (12K)
morning_news.py           (11K)
insight_generator.py      (10K)
```

### 2-4. 슬래시 커맨드 (12개)
```
/블로그 /시각화 /슈퍼뇌 /뇌훔치기 /법령
/pdf /quiz /brief /dashboard /news /record /today
```

---

## 3. 적용 매트릭스 (어디에 뭘 꽂을지)

**✅ = 적용 권장**, **🟡 = 상황 따라**, **—** = 불필요

| 자동화 | observer | checkpoint | verdict | img_dedup | cache_tracker | registry | hints | 이유 |
|---|---|---|---|---|---|---|---|---|
| **orchestrators/daily_news_pipeline** | ✅ | ✅ | — | — | 🟡 | — | — | 파이프라인 정의상 최적 타겟 |
| **orchestrators/market_analysis_pipeline** | ✅ | ✅ | — | — | 🟡 | — | — | 동일 |
| **trend_hunter.py** | ✅ | ✅ | — | 🟡 | — | — | — | N개 트렌드 반복 + 외부 크롤 |
| **news_thesis_bamboo.py** | ✅ | ✅ | — | — | 🟡 | — | — | 주간/월간 장기 배치 |
| **meta_agent.py** (아침 브리핑) | ✅ | — | — | — | 🟡 | — | — | 스테이지 많음(뉴스+일정+미리알림) |
| **running_dashboard.py** | ✅ | — | — | 🟡 | — | — | — | OCR+생성 스테이지 |
| **thinker_collector.py** (슈퍼뇌 수집) | ✅ | ✅ | — | — | 🟡 | — | — | 긴 수집 |
| **brain_monthly_delta.py** | ✅ | — | — | — | — | — | — | 월간 리포트 |
| **morning_news.py** | ✅ | — | — | — | — | — | — | 스테이지별 시간측정 |
| **weekly_report.py** | ✅ | — | — | — | — | — | — | 동일 |
| **marathon_registration_watcher.py** | 🟡 | — | — | — | — | — | — | 단일 작업, 가벼움 |
| **monitor_itcen_btc.py** | — | — | — | — | — | — | — | 단순 핑 |
| **/블로그 slash** | ✅ | — | ✅ | ✅ | — | — | ✅ | 이미 연결 설계됨 |
| **/슈퍼뇌 slash** | ✅ | ✅ | — | — | — | — | — | 긴 collection 작업 |
| **/뇌훔치기 slash** | ✅ | ✅ | — | — | — | — | — | 동일 |
| **/시각화 slash** | — | — | — | — | — | — | — | 단발 HTML 생성 |
| **서브에이전트 .md 신규 작성 시** | — | — | — | — | — | — | ✅ | 캐시 최적화 |
| **"비슷한 거 없나?" 질문** | — | — | — | — | — | ✅ | — | 수동 ls+Grep 금지 |
| **모든 Anthropic API 직접 호출** | — | — | — | — | ✅ | — | — | usage 기록 |

---

## 4. 실제 패치 우선순위 (형님 의사결정용)

### 🥇 1티어 — 즉시 패치 가치 큼
1. **orchestrators/daily_news_pipeline.py** — PipelineObserver 삽입 (30분 작업, 데모로도 좋음)
2. **orchestrators/market_analysis_pipeline.py** — 동일
3. **/블로그 slash** — blog_rewrite_loop + image_dedup + observer 자동 연결 (다음 블로그 1건 돌릴 때 같이 검증)

### 🥈 2티어 — 체크포인트 절감 큼
4. **trend_hunter.py** — 크고 중단 잦음 → Checkpoint
5. **news_thesis_bamboo.py** (주간/월간) — 동일
6. **thinker_collector.py** — 동일

### 🥉 3티어 — 관찰성만
7. meta_agent, running_dashboard, morning_news — observer만 30초짜리 삽입

### 🚧 신규 구축 후보 (놓친 구멍)
8. ✅ **`injection_shield.py`** (Part V) — 2026-04-20 구축 완료 (6/6 selftest, 5회 루프 통과)
9. **`subagent_linter.py`** (Part II) — 서브에이전트 .md 작성 시 섹션/금지어/토큰길이 체크 (미구축)

### 📌 2026-04-20 1티어 패치 완료
- `pipeline_agent.py` — `observe=True` 플래그 추가 (모든 PipelineAgent 사용자 자동 혜택)
- `orchestrators/daily_news_pipeline.py` — observe=True 연결
- `orchestrators/market_analysis_pipeline.py` — 외부 observer 래핑
- `orchestration-blog-naver.md` — Stage 5 Post-write 훅 섹션 추가 (verdict + rewrite_loop + image_dedup)
- `injection_shield.py` — 신규 구축
- `pipeline_agent_smoke.py` — 통합 smoke test
- 전체 통합: 10 agents × 5 loops = 50 selftests GREEN

---

## 5. Claude 자동 적용 규칙 (CLAUDE.md에 이미 반영됨)

형님이 명령 안 해도, Claude가 다음 조건 만족하면 이 매트릭스 참조해서 자동으로 도구를 끼워넣는다:
- 기존 자동화 **수정** 작업을 받았을 때 → 이 파일 먼저 열고 해당 자동화 행 확인
- **새 자동화 작성** 시 → "observer/checkpoint 가치있나?" 자문
- 서브에이전트 **.md 신규 작성** 시 → prompt_cache_hints 구조 따름
- 형님이 **"비슷한 에이전트 없나"** 질문 시 → `agent_registry find` 우선

**이 파일 자체가 Claude의 "하네스 적용 체크리스트"로 동작한다.**
