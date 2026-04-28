#!/usr/bin/env python3
"""주간/월간 러닝 대시보드 분석 블로그 자동 생성기.

흐름:
    1. running_log + training_load에서 대상 기간 데이터 수집
    2. /tmp/healthfit-dashboard/{weekly,monthly}.html 캡처 (카드별 스크린샷)
    3. Claude Code CLI (`claude -p`) 호출해 분석 본문 생성
    4. 이미지 → 데스크탑 `/Users/oungsooryu/Desktop/류웅수/블로그/images/`, md → 옵시디언 `블로그 초안/`에 저장 (2026-04-25 분리)
    5. base64 인라인 HTML 미리보기 생성 → 텔레그램 전송

CLI:
    python3 running_blog_writer.py weekly
    python3 running_blog_writer.py monthly
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

VAULT = Path("/Users/oungsooryu/Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수")
DRAFT_DIR = VAULT / "블로그 초안"
# 2026-04-25: 이미지는 데스크탑으로 분리 (옵시디언 인덱싱 부하 제거)
IMG_DIR = Path("/Users/oungsooryu/Desktop/류웅수/블로그/images")
IMG_URL_BASE = "file:///Users/oungsooryu/Desktop/%EB%A5%98%EC%9B%85%EC%88%98/%EB%B8%94%EB%A1%9C%EA%B7%B8/images"
DASH_DIR = Path("/tmp/healthfit-dashboard")
RUNNING_LOG = Path.home() / ".claude/data/running_log.jsonl"
TRAINING_LOAD = Path.home() / ".claude/data/training_load.jsonl"
CLAUDE_BIN = "/Users/oungsooryu/.npm-global/bin/claude"

# ── 제목 템플릿 (네이버 SEO 최적화, "러닝일기" 시리즈 일관성) ──────────────
# {week_num}/{year}/{month}/{total_km}: 파이프라인이 자동 채움
# {key_signal}: Claude가 데이터에서 핵심 시그널 1개 뽑아 채움 (예: "ACWR 2.41 과부하 신호와 회복주 전환")
WEEKLY_TITLE_TEMPLATE = "{week_num}주차 러닝일기 | 주간 {total_km}km, {key_signal}"
MONTHLY_TITLE_TEMPLATE = "{year}년 {month}월 러닝일기 | 월간 {total_km}km, {key_signal}"


def _load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def extract_week_num(period: str) -> int | None:
    """대시보드 HTML에서 'N주차' 추출. monthly면 None."""
    if period != "weekly":
        return None
    src = DASH_DIR / "weekly.html"
    if not src.exists():
        return None
    m = re.search(r"(\d+)주차", src.read_text(encoding="utf-8"))
    return int(m.group(1)) if m else None


def period_range(period: str, today: date) -> tuple[date, date, str]:
    """기간 (start, end, label) 반환. weekly=이번 월~일, monthly=지난달 1일~말일."""
    if period == "weekly":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        label = f"{monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')}"
        return monday, sunday, label
    if period == "monthly":
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev, last_prev, f"{first_prev.strftime('%Y년 %-m월')}"
    raise ValueError(f"unknown period: {period}")


def collect_data(start: date, end: date) -> dict:
    runs = []
    for s in _load_jsonl(RUNNING_LOG):
        d = s.get("date")
        if not d or s.get("workout_type") != "러닝":
            continue
        try:
            d_obj = date.fromisoformat(d)
        except Exception:
            continue
        if start <= d_obj <= end:
            runs.append(s)
    runs.sort(key=lambda r: r["date"])

    tl = []
    for r in _load_jsonl(TRAINING_LOAD):
        try:
            d_obj = date.fromisoformat(r["date"])
        except Exception:
            continue
        if start <= d_obj <= end:
            tl.append(r)

    return {"runs": runs, "training_load": tl}


def capture_dashboard(period: str, out_dir: Path) -> list[Path]:
    """weekly.html / monthly.html 카드별 스크린샷. Playwright 설치 필요."""
    from playwright.sync_api import sync_playwright

    src = DASH_DIR / f"{period}.html"
    if not src.exists():
        raise FileNotFoundError(src)

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1200, "height": 1600}, device_scale_factor=2
        )
        page = ctx.new_page()
        page.goto(f"file://{src}", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        hero_fp = out_dir / "hero.png"
        page.screenshot(
            path=str(hero_fp), clip={"x": 0, "y": 0, "width": 1200, "height": 700}
        )
        saved.append(hero_fp)

        cards = page.query_selector_all(".card")
        for i, c in enumerate(cards, 1):
            title_el = c.query_selector(".card-title")
            title = (
                title_el.inner_text().strip().split("\n")[0]
                if title_el
                else f"card{i}"
            )
            safe = re.sub(r"[^\w가-힣]+", "_", title)[:30]
            c.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            fp = out_dir / f"{i:02d}-{safe}.png"
            c.screenshot(path=str(fp))
            saved.append(fp)
        browser.close()
    return saved


def compute_stats(data: dict) -> dict:
    runs = data["runs"]
    tl = data["training_load"]
    total_km = sum(r.get("distance_km", 0) for r in runs)
    total_sec = sum(r.get("duration_sec", 0) for r in runs)
    total_trimp = sum(r.get("trimp") or 0 for r in runs)
    zones = {"Z2": 0, "Z3": 0, "Z4": 0, "Z5": 0}
    for r in runs:
        for z, v in (r.get("hr_zones") or {}).items():
            if z in zones:
                zones[z] += v or 0
    zt = sum(zones.values()) or 1
    zone_pct = {z: round(v / zt * 100, 1) for z, v in zones.items()}

    def pace_str(km: float, sec: int) -> str:
        if km <= 0:
            return "-"
        p = sec / km / 60
        mm = int(p)
        ss = int((p - mm) * 60)
        return f"{mm}:{ss:02d}/km"

    sessions = [
        {
            "date": r["date"],
            "km": round(r.get("distance_km", 0), 2),
            "sec": r.get("duration_sec", 0),
            "minutes": round(r.get("duration_sec", 0) / 60, 0),
            "pace": pace_str(r.get("distance_km", 0), r.get("duration_sec", 0)),
            "trimp": r.get("trimp"),
            "hr_zones": r.get("hr_zones"),
        }
        for r in runs
    ]

    tl_start = tl[0] if tl else None
    tl_end = tl[-1] if tl else None

    return {
        "total_km": round(total_km, 2),
        "total_sec": total_sec,
        "total_minutes": round(total_sec / 60, 0),
        "total_trimp": round(total_trimp, 1),
        "session_count": len(runs),
        "sessions": sessions,
        "zone_seconds": zones,
        "zone_pct": zone_pct,
        "low_intensity_pct": round(zone_pct["Z2"], 1),
        "high_intensity_pct": round(zone_pct["Z4"] + zone_pct["Z5"], 1),
        "tl_start": tl_start,
        "tl_end": tl_end,
    }


def build_title_instruction(period: str, start: date, end: date, stats: dict, week_num: int | None) -> str:
    """제목 템플릿 → Claude에게 줄 지시문."""
    total_km = int(round(stats["total_km"]))
    if period == "weekly":
        wn = week_num if week_num else start.isocalendar()[1]
        prefix = WEEKLY_TITLE_TEMPLATE.format(
            week_num=wn, total_km=total_km, key_signal="{key_signal}"
        )
    else:
        prefix = MONTHLY_TITLE_TEMPLATE.format(
            year=start.year, month=start.month, total_km=total_km, key_signal="{key_signal}"
        )
    # {key_signal} 부분만 Claude가 채움 (2026-04-28: 약어 빼고 일상어로)
    example_key = {
        "weekly": "과부하 경고와 회복 전환점",
        "monthly": "체력 성장 궤도와 컨디션 정리",
    }[period]
    filled_example = prefix.replace("{key_signal}", example_key)
    return (
        f"제목은 반드시 다음 형식으로 시작하십시오:\n"
        f"  `# {prefix}`\n"
        f"여기서 {{key_signal}}은 이번 기간 데이터에서 가장 눈에 띄는 지표와 해석을 "
        f"20~35자로 압축한 문구입니다. 예: `{filled_example}`. "
        f"제목에 '분석', '심층', '데이터가 말하는' 같은 딱딱한 단어는 쓰지 마십시오."
    )


def build_prompt(period: str, label: str, start: date, end: date, stats: dict, week_num: int | None = None) -> str:
    style_sample = """\
[문체 — 절대 규칙, 위반 시 재작성]
- **합쇼체(~합니다, ~습니다, ~했습니다) 하나만 사용.** 해라체 혼용 금지.
- 1인칭 경험 서술. 러닝 입문~중급 독자 대상.

[🚫 영문 약어 절대 금지 (최우선 — 위반 시 글 폐기) — 2026-04-28 추가]

독자는 ACWR · TSB · TRIMP · CTL · ATL · VO₂max · Z1~Z5 같은 용어를 **모릅니다**.
약어를 "친절히 설명하는 것"도 금지. 처음부터 일상어로만 쓰십시오.

번역표 (반드시 적용):
- ACWR → "최근 부하 비율" / "몸이 감당하는 속도보다 빨리 달린 정도" / "오버페이스 신호"
- TSB → "회복 잔량" / "몸 컨디션 점수" / "기름탱크 잔량"
- CTL → "장기 체력" / "그동안 쌓아온 기초 체력"
- ATL → "최근 피로" / "이번 주 누적된 부담"
- TRIMP → "운동 부하 점수" / "총 훈련량"
- VO₂max → "유산소 능력" / "심폐 체력"
- Z1·Z2 → "편한 조깅 / 대화되는 속도"
- Z3 → "약간 숨찬 회색 구간"
- Z4·Z5 → "숨차는 강도 / 빡센 인터벌"
- 폴라리즈드 80/20 → "쉬운 80% + 빡센 20% 원칙"
- 부상 위험 → "삐끗 주의" / "무릎·발목 경고"

❌ 금지: "ACWR 2.48이라 위험 구간입니다." / "CTL이 43에서 47로 올라갔습니다."
✅ 허용: "최근 부하가 평소의 2.5배 — 위험 구간이었습니다." / "장기 체력은 43에서 47로, 천천히 쌓이는 중입니다."

숫자는 그대로 써도 OK (32.1km, 7'15"/km, 평균 심박 148bpm). 단 약어 옆에 붙이지 말고 일상어와 함께.

[AI 말투 금지]
1. 단조로운 종결 반복 금지 — "~입니다/~습니다"만 반복 금지. 질문형·짧은 단문 섞기
2. 과도한 접속사 금지 ("따라서, 그러므로, 또한, 게다가, 더불어")
3. 기계적 나열 금지 — 중간에 코멘트·비교 섞기
4. 강조어 남발 금지 ("매우, 굉장히, 정말로, 가장, 최고의" 섹션당 1회 이내)
5. 동일 문장 구조 반복 금지 — 짧은 문장(5~10자)과 긴 문장(30~50자) 섞어 리듬

[금지 표현]
"다양한 측면에서", "종합적으로", "이처럼", "이에 따라", "이를 통해",
"도움이 되셨으면", "활용", "기반으로 한", "뿐만 아니라", "더불어", "나아가",
"제시합니다", "소개합니다", "본 글에서는"

[구체성]
- 숫자는 있는 그대로 (거리·페이스·심박). 추상화 금지.
- 해석은 단호하게.

[이미지 플레이스홀더]
- 각 H2 섹션마다 `![설명](placeholder-N.png)` 1개만. N은 1부터 순서대로.
- 플레이스홀더 1번 = 커버, 2번부터 = 카드 스크린샷.

[목표 맥락]
6/7 하프마라톤 준비. 데이터로 훈련을 조율하는 일지.
"""
    data_block = json.dumps(
        {"period": period, "label": label, "start": str(start), "end": str(end), **stats},
        ensure_ascii=False,
        indent=2,
    )
    task = {
        "weekly": (
            "한 주 훈련 일지를 **짧고 쉽게** 쓰십시오. 구성: "
            "(1) 인트로·이번 주 한 줄 요약 (2) 세션별 짧은 메모 "
            "(3) 회복·피로 흐름 (CTL/ATL/TSB 같은 약어 금지 — 일상어로) "
            "(4) 부상 위험 신호 (ACWR 같은 약어 금지) "
            "(5) 다음 주 계획 (6) 마무리. "
            "**H2 5~6개, 총 1,500~2,200자(공백 제외)** — 짧게. 이미지 플레이스홀더 6개 내외."
        ),
        "monthly": (
            "한 달 훈련 일지를 **짧고 쉽게** 쓰십시오. 구성: "
            "(1) 인트로·이달 한 줄 요약 (2) 주차별 흐름 "
            "(3) 장기 체력 성장 궤적 (4) 부상 리스크 점검 "
            "(5) 회복 패턴 (6) 다음 달 계획 (7) 마무리. "
            "**H2 6~7개, 총 1,800~2,500자** — 짧게. 이미지 플레이스홀더 8개 내외."
        ),
    }[period]

    # 핵심 키워드 (반복 5~7회) — 2026-04-28: 약어 빼고 일상어로
    kw_map = {
        "weekly": ["주간 러닝", "훈련 일지", "마라톤 훈련", "회복", "심박"],
        "monthly": ["월간 러닝", "훈련 일지", "체력 성장", "마라톤 훈련", "회복"],
    }
    keywords = kw_map[period]

    title_instr = build_title_instruction(period, start, end, stats, week_num)

    return f"""{style_sample}

[요청]
{task}

[제목 형식 — 절대 규칙]
{title_instr}

[핵심 키워드 — 본문 전체에서 5~7회 자연스럽게 반복]
{", ".join(keywords)}

[훈련 데이터 JSON]
{data_block}

[출력 형식]
- Markdown 본문만 출력. 제목은 '# '로 시작하는 H1 한 줄로 맨 앞에 쓸 것.
- YAML 프론트매터나 코드블록 감싸기 금지.
- 본문 **1,500~2,500자** (이전보다 짧게 — 디테일보다 핵심).
- **글 맨 마지막 줄에 해시태그 10~15개** 한 줄로 (예: #주간러닝 #마라톤훈련 #회복 #심박 ...). **약어 해시태그(ACWR/TRIMP/CTL) 금지.**
- 설명·서문 없이 글만 출력."""


def call_claude_cli(prompt: str, timeout_sec: int = 420) -> str:
    """Claude Code CLI headless 호출.
    2026-04-27: launchd 환경에 PATH 없어 node 못 찾는 문제 fix — PATH 명시 주입."""
    import os as _os
    env = {**_os.environ}
    env["PATH"] = "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:" + env.get("PATH", "")
    r = subprocess.run(
        [
            CLAUDE_BIN,
            "-p",
            prompt,
            "--output-format",
            "text",
        ],
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        env=env,
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI 실패: {r.stderr.strip()}")
    return r.stdout.strip()


def map_placeholders(md: str, images: list[Path], img_prefix: str) -> tuple[str, list[tuple[Path, str]]]:
    """placeholder-N.png → images/<prefix>-NN-<title>.png 로 교체.
    캡처 이미지는 hero → 01 → 02 → ... 순서. 플레이스홀더 1번이 첫 이미지에 매핑됨.
    부족하면 캡처 이미지를 순환 사용.
    """
    # 플레이스홀더 순서대로 찾기
    placeholders = re.findall(r"!\[([^\]]*)\]\(placeholder-(\d+)\.png\)", md)
    # 이미지 매핑: 플레이스홀더 번호 i → images[i-1] (없으면 순환)
    n_img = len(images)
    renames: list[tuple[Path, str]] = []  # (original_path, new_filename)
    used_map: dict[int, str] = {}
    for _alt, num in placeholders:
        idx = int(num) - 1
        if idx < 0 or n_img == 0:
            continue
        src = images[idx % n_img]
        if int(num) in used_map:
            continue
        new_name = f"{img_prefix}-{int(num):02d}{src.stem[2:] if src.stem[:2].isdigit() else ''}.png"
        new_name = re.sub(r"[^\w가-힣\-\.]+", "-", new_name)
        used_map[int(num)] = new_name
        renames.append((src, new_name))

    def repl(m):
        num = int(m.group(2))
        new_name = used_map.get(num)
        if not new_name:
            return m.group(0)
        # 2026-04-28: vault 내 symlink 사용 → 상대경로(images/...)로 박아 옵시디언 미리보기 가능
        return f"![{m.group(1)}](images/{new_name})"

    new_md = re.sub(r"!\[([^\]]*)\]\(placeholder-(\d+)\.png\)", repl, md)
    return new_md, renames


def md_to_html(md: str, vault_base: Path) -> str:
    """md → 단일 HTML. 이미지는 base64 인라인."""
    if md.startswith("---"):
        parts = md.split("---", 2)
        body = parts[2] if len(parts) >= 3 else md
    else:
        body = md

    def img_to_data(m):
        alt, rel = m.group(1), m.group(2)
        p = vault_base / rel
        if not p.exists():
            return m.group(0)
        data = base64.b64encode(p.read_bytes()).decode()
        return f'<figure><img alt="{alt}" src="data:image/png;base64,{data}"><figcaption>{alt}</figcaption></figure>'

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", img_to_data, body)

    out = []
    in_list = False
    for ln in body.split("\n"):
        s = ln.rstrip()
        hm = re.match(r"^(#{1,4})\s+(.+)$", s)
        if hm:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<h{len(hm.group(1))}>{hm.group(2)}</h{len(hm.group(1))}>")
            continue
        lm = re.match(r"^[-*]\s+(.+)$", s)
        if lm:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{lm.group(1)}</li>")
            continue
        nm = re.match(r"^(\d+)\.\s+(.+)$", s)
        if nm:
            if not in_list:
                out.append("<ol>")
                in_list = True
            out.append(f"<li>{nm.group(2)}</li>")
            continue
        if s.strip() == "---":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("<hr>")
            continue
        if not s.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        if s.lstrip().startswith("<figure") or s.lstrip().startswith("<img"):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(s)
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<p>{s}</p>")
    if in_list:
        out.append("</ul>")

    body_html = "\n".join(out)
    body_html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", body_html)
    body_html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', body_html)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>러닝 분석 미리보기</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Pretendard', 'Apple SD Gothic Neo', sans-serif;
  max-width: 720px; margin: 0 auto; padding: 24px 20px;
  color: #222; line-height: 1.75; background: #fafafa; }}
h1 {{ font-size: 1.6rem; line-height: 1.35; margin: 0 0 24px; }}
h2 {{ font-size: 1.25rem; margin: 40px 0 16px; padding-top: 16px; border-top: 2px solid #111; }}
h3 {{ font-size: 1.1rem; margin: 28px 0 12px; }}
p {{ margin: 0 0 16px; }}
ul, ol {{ margin: 0 0 16px; padding-left: 22px; }}
figure {{ margin: 20px 0; text-align: center; }}
figure img {{ max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
figcaption {{ font-size: 0.85rem; color: #666; margin-top: 6px; }}
strong {{ color: #d63031; font-weight: 700; }}
hr {{ border: none; border-top: 1px solid #ddd; margin: 36px 0; }}
a {{ color: #0984e3; text-decoration: none; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


def apply_cover_title(hero_path: Path, title: str) -> Path:
    """hero.png에 블로그 제목을 오버레이. cover_overlay.py 호출."""
    if not hero_path.exists():
        return hero_path
    out_path = hero_path.with_name("hero-titled.png")
    r = subprocess.run(
        [
            "python3",
            "/Users/oungsooryu/alice-github/harness-engineering-guide/templates/agents/cover_overlay.py",
            str(hero_path),
            str(out_path),
            title,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0 or not out_path.exists():
        # 실패해도 원본으로 fallback
        return hero_path
    return out_path


def validate_pipeline(md: str) -> list[str]:
    """블로그 파이프라인 규정 위반 검사. 경고 리스트 반환."""
    warnings: list[str] = []
    # 1. 합쇼체 검사 — 명확한 해라체 어미만 감지 (~습니다/~입니다는 제외)
    hera_re = r"[가-힣](?:이다|한다|있다|없다|였다|됐다|됐는다|했다|된다|간다|온다|본다|느낀다|나온다|먹는다|올린다|쓴다|넣는다|뺀다)\.(?=\s|$)"
    matches = re.findall(hera_re, md)
    if len(matches) >= 2:
        warnings.append(f"해라체 의심 {len(matches)}회")

    # 2. 해시태그 체크 (마지막 줄)
    tail = md.strip().splitlines()[-5:] if md.strip() else []
    tag_line = next((ln for ln in reversed(tail) if ln.lstrip().startswith("#")), "")
    tags = re.findall(r"#\S+", tag_line)
    if len(tags) < 10:
        warnings.append(f"해시태그 {len(tags)}개 (10~15개 필요)")

    # 3. 글자수
    body_chars = len(re.sub(r"\s+", "", md))
    if body_chars < 2000:
        warnings.append(f"본문 {body_chars}자 (2,000자 이상 필요)")

    # 4. 금지 표현
    bad_phrases = [
        "다양한 측면에서", "종합적으로", "이처럼", "이에 따라", "이를 통해",
        "도움이 되셨으면", "뿐만 아니라", "제시합니다", "본 글에서는",
    ]
    for p in bad_phrases:
        if p in md:
            warnings.append(f"금지 표현 '{p}'")

    return warnings


def send_file_telegram(path: Path) -> None:
    subprocess.run(
        [
            "/Users/oungsooryu/.local/bin/cokacdir",
            "--sendfile",
            str(path),
            "--chat",
            "756219914",
            "--key",
            "2f74e6b1e5f85566",
        ],
        capture_output=True,
        timeout=60,
    )


def generate(period: str, today: date | None = None) -> dict:
    """주 엔트리포인트. {'md_path', 'html_path', 'stats'} 반환."""
    today = today or date.today()
    start, end, label = period_range(period, today)
    data = collect_data(start, end)
    if not data["runs"]:
        raise RuntimeError(f"{period} 기간에 러닝 데이터 없음 ({start}~{end})")
    stats = compute_stats(data)

    tmp_capture = Path(f"/tmp/running-blog-{period}-{end.strftime('%Y%m%d')}")
    tmp_capture.mkdir(parents=True, exist_ok=True)
    images = capture_dashboard(period, tmp_capture)

    week_num = extract_week_num(period)
    prompt = build_prompt(period, label, start, end, stats, week_num)
    md_body = call_claude_cli(prompt)

    # 제목 추출
    title_match = re.search(r"^#\s+(.+)$", md_body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else f"{label} 러닝 분석"

    # 커버(hero.png) 제목 오버레이 → 오버레이된 파일로 교체
    if images and images[0].name == "hero.png":
        titled = apply_cover_title(images[0], title)
        if titled != images[0]:
            images = [titled] + images[1:]

    # 이미지 매핑
    img_prefix = f"{end.strftime('%Y-%m-%d')}-{period}-run"
    md_body, renames = map_placeholders(md_body, images, img_prefix)

    # 파이프라인 검증
    warnings = validate_pipeline(md_body)

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for src, new_name in renames:
        shutil.copy2(src, IMG_DIR / new_name)

    # 프론트매터 추가 (옵시디언 표준)
    frontmatter = f"""---
type: blog
author:
  - "[[류웅수]]"
date created: {end.strftime('%Y-%m-%d')}
date modified: {end.strftime('%Y-%m-%d')}
tags: [러닝, 훈련일지, 마라톤훈련, {period}분석]
---

"""
    full_md = frontmatter + md_body

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^\w가-힣\s\-]", "", title)[:60]
    md_path = DRAFT_DIR / f"{end.strftime('%Y-%m-%d')} {period} {safe_title}.md"
    md_path.write_text(full_md, encoding="utf-8")

    html_path = Path(f"/tmp/running-blog-{period}-preview.html")
    html_path.write_text(md_to_html(full_md, DRAFT_DIR), encoding="utf-8")

    send_file_telegram(md_path)
    send_file_telegram(html_path)

    return {
        "md_path": str(md_path),
        "html_path": str(html_path),
        "title": title,
        "stats": stats,
        "warnings": warnings,
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("weekly", "monthly"):
        print("Usage: running_blog_writer.py {weekly|monthly}")
        sys.exit(1)
    result = generate(sys.argv[1])
    print(f"✅ 블로그 생성 완료: {result['title']}")
    print(f"   md: {result['md_path']}")
    print(f"   html: {result['html_path']}")
    if result.get("warnings"):
        print("⚠️  파이프라인 경고:")
        for w in result["warnings"]:
            print(f"   - {w}")


if __name__ == "__main__":
    main()
