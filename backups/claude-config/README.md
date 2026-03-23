# Claude Config Backup

`~/.claude/settings.json` 과 `~/.claude/scripts/` 백업

## 복구 방법

```bash
# 1. 스크립트 복사
cp scripts/*.py ~/.claude/scripts/

# 2. settings.json 복사
cp settings.json ~/.claude/settings.json

# 3. .env 파일 생성 (실제 키 값 입력)
cp .env.example ~/.claude/.env
# 편집기로 ~/.claude/.env 열어서 실제 값 입력

# 4. python-dotenv 설치
pip3 install python-dotenv
```

## 파일 구조

- `settings.json` - MCP 서버 설정
- `scripts/` - 자동화 스크립트 14개
- `.env.example` - 환경변수 템플릿 (실제 키 없음)

## 스크립트 목록

| 파일 | 실행시간 | 역할 |
|------|---------|------|
| create_daily_note.py | 07:00 | 옵시디언 데일리 노트 생성 |
| morning_news.py | 07:00 | 아침 뉴스 텔레그램 전송 |
| morning_schedule.py | 07:00 | 오늘 구글 캘린더 일정 |
| daily_news_to_obsidian.py | 07:00 | 뉴스 → 옵시디언 저장 |
| daily_message_summary.py | 17:00 | 문자 요약 텔레그램 전송 |
| evening_briefing.py | 17:50 | 저녁 뉴스 브리핑 |
| evening_schedule.py | 18:00 | 내일 구글 캘린더 일정 |
| daily_summary.py | 23:00 | 오늘 작업 요약 |
| daily_work_summary.py | 23:00 | 작업 로그 요약 |
| exam_quiz_notebooklm.py | 09:00~17:00 (7회) | 공인중개사 퀴즈 |
| interest_curator_v6.py | 09:00~19:00 (6회) | 관심사 뉴스 큐레이션 |
| monitor_itcen_btc.py | 매시간 | 아이티센글로벌 + BTC 모니터링 |
| news_scraper_refactored.py | 일요일/1일 09:00 | 주간/월간 뉴스 분석 |
| config.py | - | 공통 설정 로더 |
