# 하네스 도메인 레지스트리 (Single Point of Entry)

> **목적:** 각 도메인별로 "반드시 이 모듈만 써라"를 한눈에. 새 파일 만들기 전 여기부터 확인.
>
> **규칙:** 아래 도메인의 일을 할 때는 **반드시 SPoE 모듈을 import해서 사용**한다.
> 새로 만들거나, subprocess로 직접 CLI를 호출하는 건 **금지**. 예외가 필요하면 SPoE 모듈 자체를 확장한다.
>
> **업데이트:** 새 도메인이 생기거나 SPoE가 바뀌면 이 파일을 먼저 갱신하고 CLAUDE.md에서 참조.

---

## 🗺️ 도메인 → SPoE 매핑

| 도메인 | Single Point of Entry | 대체 모듈/패턴 | 금지 사항 |
|--------|----------------------|----------------|-----------|
| **Vercel 배포** | `agents/vercel_adapter.py` (`deploy_dir`, `shorten_url`) | — | `subprocess(["vercel", ...])` 직접 호출 금지 |
| **외부 공유 HTML** | `agents/html_share_deployer.py` (`deploy(path)`) | — | Vercel/Netlify 직접 호출, GitHub Pages, jsdelivr 사용 금지 |
| **러닝 대시보드 배포** | `scripts/healthfit_deploy.py` (`regenerate_deploy_single(period)`) | `running_summary.py`가 호출 | 직접 HTML 생성→배포 복제 금지 |
| **텔레그램 알림** | `agents/telegram_sender.py` (`send_telegram_html`, `send_alert`) | — | 봇 토큰 하드코딩, requests 직접 호출 금지 |
| **옵시디언 저장** | `agents/obsidian_writer.py` (`save_note`, `build_yaml`) | — | YAML 직접 작성, 표준 필드 외 사용 금지 |
| **뉴스 수집** | `agents/news_scraper.py` (`NewsScraper`) | — | requests·bs4 직접 호출 금지, 반드시 이 래퍼 경유 |
| **웹 데이터 수집(동적)** | `agents/web_data_scraper.py` | — | Playwright 직접 세팅 금지 |
| **텍스트 요약** | `agents/summarizer.py` (`Summarizer`) | — | Anthropic API 직접 호출 금지 (캐시 로깅 누락 방지) |
| **외부 텍스트 방어** | `agents/injection_shield.py` (`scan`, `wrap_external`) | — | LLM 입력 전 방어 없이 넣기 금지 |
| **파이프라인 관찰** | `agents/pipeline_observer.py` 또는 `harness_integration.harnessed()` | — | 다단계 작업에 관찰 빠뜨리기 금지 |
| **배치 체크포인트** | `agents/session_checkpoint.py` (`Checkpoint`) | — | N≥20 배치에 체크포인트 없이 진행 금지 |
| **블로그 글 검증** | `agents/blog_verdict_agent.py` (`verdict(md_path, keyword)`) | — | 작성 후 검증 스킵 금지 |
| **블로그 재작성 루프** | `agents/orchestrators/blog_rewrite_loop.py` | — | FAIL/PARTIAL 후 그대로 두기 금지 |
| **이미지 생성 API 호출** | `agents/image_client.py` (`generate(prompt, out_path, aspect_ratio)`) | — | Nano Banana primary + Imagen 4 Ultra fallback transport. curl/requests 직접 호출 복제 금지. 컨셉(스타일 프롬프트·H2 매핑·Claymorphism)은 호출측 책임 |
| **이미지 중복 검사** | `agents/image_dedup.py` (`check_folder`) | — | 이미지 폴더 생성 후 중복 체크 스킵 금지 |
| **커버 이미지 오버레이** | `agents/cover_overlay.py` | — | PIL 직접 오버레이 복제 금지 |
| **뉴스 이미지 후처리** | `agents/news_image_processor.py` | — | 톤 통일 스킵 금지 |
| **블로그 이미지 삽입** | `agents/blog_image_inserter.py` | — | 수동 마크다운 이미지 삽입 복제 금지 |
| **PDF ↔ 마크다운** | `agents/pdf_converter.py` | — | pypdf 직접 호출 복제 금지 |
| **Anthropic API 직접 호출** | `agents/cache_hit_tracker.py` (`record(usage)`) | — | usage 로깅 스킵 금지 |
| **에이전트 검색** | `agents/agent_registry.py` (`find <키워드>`) | — | ls + Grep 수동 탐색 금지 |
| **새 자동화/에이전트 뼈대 생성** | `agents/scaffold.py` (`automation\|agent <name>`) | — | run_as_automation/selftest 없이 새 스크립트·에이전트 작성 금지 |
| **신발 마일리지** | `scripts/shoe_tracker.py` | — | 별도 신발 DB 복제 금지 |
| **훈련 부하 계산** | `agents/training_load.py` (CTL/ATL/TSB/ACWR) | — | 자체 부하 계산 복제 금지 |
| **러닝 코치 조언 기록/비교** | `agents/advice_log.py` (`save_advice`, `get_last_advice`, `check_compliance`) | `running_coach_agent.py`가 저장·조회, `healthfit_cards.py`는 텍스트만 | 조언 jsonl 직접 append 금지, compliance 비교 규칙 복제 금지 |
| **Apple Health 일별 지표 (VO2max/HRV/안정시 심박)** | `agents/health_metrics_pull.py` (`update_from_text`, `latest_metric`, `recent_avg`, `trend_30d`) | `~/.claude/data/health_metrics_log.jsonl` 캐시, `healthfit_dashboard_gen.py`에서 import → `render_health_card`에 dict 주입, `/데일리 러닝` Step 0에서 ingest | Drive 시트 직접 파싱 복제 금지, JSONL 직접 append 금지, FIT 워크아웃 흐름(`running_log.jsonl`)에 헬스 지표 섞기 금지 (소스가 다름 — 이건 일 단위, 저건 워크아웃 단위) |
| **Pre-Write Protocol 강제** | `~/.claude/hooks/pre_write_harness_check.py` | `settings.json` PreToolUse:Write 매처 | hook 무력화/정책 우회 금지. 우회는 키워드/`HARNESS_HOOK_OFF=1`/해제 파일만 허용 |
| **AOS 운영 대시보드** | `agents/aos_dashboard.py` (`build`, `deploy`) | — | pipeline 로그 직접 집계 복제 금지 |
| **SPoE Drift 주기 탐지** | `agents/aos_drift_check.py` (`scan`, `run`) | launchd `com.oungsooryu.aos-drift-check` (03:00 daily) | 금지 패턴 수동 grep 복제 금지 |
| **자동 핸드오프 (세션 맥락 보존)** | `~/.claude/scripts/auto_handoff.py` | launchd `com.user.auto-handoff` (05·08·11·14·17·20·23시), 수면 00~05시 블랙아웃 | `work_log.json`(파일명 나열) 기반 핸드오프 복제 금지 — 반드시 session jsonl transcript 경유 |
| **블로그 키워드 수집 (SNS 선행)** | `agents/searchers/` 디렉토리 (`youtube_search`, `instagram_chrome`, `datalab_gap`, `reddit_trends`) | `~/.claude/scripts/blog_keyword_hunter.py` (일일 07:30), `blog_keyword_weekly.py` (월 07:45) | 블로그 키워드 수집 로직을 trend_hunter.py에 섞기 금지 (trend_hunter는 뉴스 소비용), 각 소스별 래퍼 없이 API 직접 호출 금지 |
| **네이버 블로그 작성** | `agents/orchestration-blog-naver.md` | `~/.claude/commands/블로그.md` 엔트리 | 서브에이전트(blog-writer-naver/blog-image/obsidian-blog-saver)를 직접 호출하지 말고 orchestration 경유 |
| **블로그 서평 (해상도 렌즈)** | `agents/orchestration-blog-book.md` | `~/.claude/commands/블로그 도서.md` 엔트리, 렌즈 소스: `블로그 도서 Vault/해상도 프로젝트/` | 서평 전용 렌즈 선정·A해부+B평가 구조를 blog-naver에 섞기 금지, 책 정보 추측 금지 (WebSearch 확인 필수) |
| **내 블로그 조회수 통계** | `agents/my_blog_stats.py` (`fetch_all_periods`, `analyze_shifts`, `extract_keywords`) | `~/.claude/data/naver_session.json` 세션 필요, `blog_keyword_hunter.py`에서 import | Playwright storage_state 직접 세팅 복제 금지, shifts 분석 로직 중복 작성 금지 |
| **DESIGN.md / 브랜드 voice 시스템** | `agents/design/_meta_DESIGN.md` (마스터) + `agents/design/domains/*.md` (도메인 sub) | `~/.claude/CLAUDE.md` `@import` (Phase 4 후), claude.ai/design 업로드, Cursor/v0/Lovable 프로젝트 root symlink. 표준 spec: google-labs-code/design.md | 디자인·voice·금지어·tone 가이드를 자동화 파일(blog-image/blog-writer 등)에 직접 박지 말고 `design/`을 reference. 마이그레이션은 점진적으로 (한 번에 갈아엎기 금지). 자세히는 `agents/design/README.md` |

---

## 🔍 도메인 키워드 → SPoE 역인덱스 (검색용)

> 새 파일명에 아래 키워드가 들어간다 → 해당 SPoE 먼저 확인.

| 키워드 | 해당 도메인 |
|--------|-------------|
| `deploy`, `vercel`, `netlify`, `share`, `publish` | Vercel 배포 / 외부 공유 HTML |
| `telegram`, `notify`, `alert`, `bot` | 텔레그램 알림 |
| `obsidian`, `note`, `vault`, `markdown_save` | 옵시디언 저장 |
| `news`, `scrape`, `feed` | 뉴스 수집 |
| `summarize`, `summary`, `tldr` | 텍스트 요약 |
| `shield`, `sanitize`, `injection`, `prompt_guard` | 외부 텍스트 방어 |
| `observe`, `pipeline`, `stage`, `harness` | 파이프라인 관찰 |
| `checkpoint`, `resume`, `batch_state` | 배치 체크포인트 |
| `verdict`, `validate`, `quality_check` | 블로그 글 검증 |
| `rewrite`, `retry_loop` | 블로그 재작성 루프 |
| `imagen`, `nano_banana`, `gemini_image`, `generate_image`, `image_api` | 이미지 생성 API 호출 |
| `dedup`, `dedupe`, `duplicate_image` | 이미지 중복 검사 |
| `cover`, `overlay`, `title_image` | 커버 이미지 오버레이 |
| `image_proc`, `tone_match` | 뉴스 이미지 후처리 |
| `pdf`, `converter` | PDF ↔ 마크다운 |
| `cache_track`, `usage_log`, `anthropic_usage` | Anthropic API 사용량 |
| `registry`, `find_agent`, `list_agent` | 에이전트 검색 |
| `shoe`, `mileage` | 신발 마일리지 |
| `load`, `ctl`, `atl`, `tsb`, `acwr`, `training_load` | 훈련 부하 계산 |
| `advice`, `coach_log`, `compliance`, `조언`, `prior_advice`, `last_advice` | 러닝 코치 조언 기록/비교 |
| `blog_keyword`, `keyword_hunt`, `sns_trend`, `youtube_trend`, `instagram_trend`, `datalab_gap` | 블로그 키워드 수집 (SNS 선행) |
| `blog`, `naver_blog`, `blog_post`, `orchestration_blog` | 네이버 블로그 작성 |
| `book_review`, `서평`, `도서`, `해상도`, `렌즈`, `mental_model_lens` | 블로그 서평 (해상도 렌즈) |
| `my_blog`, `blog_stats`, `blog_views`, `view_shifts` | 내 블로그 조회수 통계 |
| `design`, `DESIGN.md`, `brand`, `voice`, `tone`, `style_guide`, `브랜드`, `톤`, `voice_guide`, `색상`, `typography`, `palette`, `cheatsheet`, `forbidden`, `금지어`, `donts` | DESIGN.md / 브랜드 voice 시스템 |

---

## 📋 새 파일 만들기 전 Pre-Write Protocol

새 `.py`/`.md`/`.sh`를 만들거나 기존 파일을 크게 갈아엎기 전:

### Step 1 — agent_registry 쿼리 (필수)
```bash
python3 /Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/agent_registry.py find <키워드>
```
키워드는 파일명 주요 단어 또는 도메인 키워드(위 역인덱스 참조).

### Step 2 — 도메인 레지스트리 확인 (필수)
위의 "도메인 → SPoE 매핑" 표에서 일치하는 도메인이 있는지 확인.

### Step 3 — 결정 기록 (응답에 명시)
세 가지 중 하나:
- **[A] SPoE 있음 → import해서 쓴다** (기본값, 95% 경우)
- **[B] SPoE 있지만 부족함 → SPoE 모듈 자체를 확장한다** (이유 명시)
- **[C] SPoE 없음 → 새로 만든다** (형님에게 확인 필수. 새로 만들 거면 이 레지스트리도 함께 갱신)

**위 3단계 결과를 응답에 명시하지 않은 상태에서 Write tool 호출 금지.**

---

## ✍️ 이 레지스트리 유지보수

- 새 SPoE 모듈 추가 시: "도메인 → SPoE 매핑" 표에 행 추가, 역인덱스에 키워드 추가
- SPoE 이름/경로 변경 시: 이 파일 먼저 갱신 → CLAUDE.md 참조 확인 → 실제 import 경로 변경
- SPoE 폐기 시: "금지 사항" 열에 "(폐기됨 — 대체: X)" 표기

`subagent_linter.py`가 이 레지스트리를 읽어 정적 검증(금지 패턴 감지)에 사용.
