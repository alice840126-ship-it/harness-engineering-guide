#!/usr/bin/env python3
"""
외부 공유용 HTML 배포 모듈.
HTML 파일을 GitHub Pages(html-share 레포)에 올려서 단축 URL을 반환한다.

어디서든 동일하게 사용:
- 터미널 Claude Code: from html_share_deployer import deploy
- 텔레그램 봇: from html_share_deployer import deploy
- 스크립트: python3 html_share_deployer.py "파일.html"

=== 외부 공유 규칙 (필수) ===
1. 도메인: github.io (GitHub Pages) — cdn.jsdelivr.net 절대 사용 금지
2. 파일명: 영문 슬러그만 (한글 파일명 → 자동 변환)
3. 단축 URL: is.gd로 단축 후 반환
4. 결과: https://is.gd/xxxxx (짧은 URL)
=============================
"""
import os
import sys
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path


REPO_DIR = Path.home() / "html-share"
PAGES_BASE = "https://alice840126-ship-it.github.io/html-share"


def to_english_slug(filename: str) -> str:
    """한글 파일명 → 영문 슬러그.
    예: 공인중개사-공시법-학습노트.html → gongsi-study.html
    예: 2026-04-06-korean-law-mcp-설치-사용법.html → 2026-0406-korean-law-mcp.html
    """
    stem = Path(filename).stem

    # 날짜 패턴 추출 (YYYY-MM-DD → YYYY-MMDD)
    date_match = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.*)", stem)
    if date_match:
        year, month, day, rest = date_match.groups()
        date_part = f"{year}-{month}{day}"
    else:
        date_part = ""
        rest = stem

    # 영문+숫자+하이픈만 남기기
    rest = unicodedata.normalize("NFKD", rest)
    rest = re.sub(r"[^\x00-\x7F]", "", rest)  # 비ASCII 제거
    rest = re.sub(r"[^a-zA-Z0-9\-]", "-", rest)
    rest = re.sub(r"-+", "-", rest).strip("-")
    rest = rest[:30].rstrip("-")

    if rest:
        slug = f"{date_part}-{rest}" if date_part else rest
    else:
        slug = date_part if date_part else "post"
    return slug + ".html"


def deploy(html_path: str) -> dict:
    """HTML 파일을 html-share 레포에 배포하고 단축 URL 반환.

    Args:
        html_path: 배포할 HTML 파일 경로

    Returns:
        {"short_url": "https://is.gd/xxx", "pages_url": "https://...github.io/...", "slug": "파일명.html", "ok": True}
        실패 시 {"ok": False, "error": "메시지"}
    """
    if not REPO_DIR.exists():
        return {"ok": False, "error": "~/html-share 폴더 없음"}

    html_file = Path(html_path)
    if not html_file.exists():
        return {"ok": False, "error": f"파일 없음: {html_path}"}

    slug = to_english_slug(html_file.name)
    dest = REPO_DIR / slug

    # 1. 복사
    shutil.copy2(str(html_file), str(dest))

    # 2. git add + commit
    commit_result = subprocess.run(
        f'cd "{REPO_DIR}" && git pull --rebase 2>/dev/null; '
        f'git add "{slug}" && '
        f'(git diff --cached --quiet && echo "NOTHING_NEW" || git commit -m "add {slug}")',
        shell=True, capture_output=True, text=True,
    )
    already = "NOTHING_NEW" in commit_result.stdout or "nothing to commit" in commit_result.stdout
    if commit_result.returncode != 0 and not already:
        return {"ok": False, "error": f"git commit 실패: {commit_result.stderr.strip()[:100]}"}

    # 3. git push (2회 시도)
    for attempt in range(2):
        push = subprocess.run(
            f'cd "{REPO_DIR}" && git push',
            shell=True, capture_output=True, text=True,
        )
        if push.returncode == 0:
            break
        if attempt == 1:
            return {"ok": False, "error": f"git push 실패: {push.stderr.strip()[:100]}"}

    # 4. GitHub Pages URL
    pages_url = f"{PAGES_BASE}/{slug}"

    # 5. is.gd 단축
    try:
        short = subprocess.run(
            ["curl", "-s", f"https://is.gd/create.php?format=simple&url={pages_url}"],
            capture_output=True, text=True, timeout=10,
        )
        short_url = short.stdout.strip()
        if not short_url.startswith("http"):
            short_url = pages_url  # 단축 실패 시 원본 사용
    except Exception:
        short_url = pages_url

    return {
        "ok": True,
        "short_url": short_url,
        "pages_url": pages_url,
        "slug": slug,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 html_share_deployer.py [HTML파일경로]")
        sys.exit(1)

    result = deploy(sys.argv[1])
    if result["ok"]:
        print(f"배포 완료!")
        print(f"  단축 URL: {result['short_url']}")
        print(f"  Pages URL: {result['pages_url']}")
        print(f"  파일명: {result['slug']}")
    else:
        print(f"실패: {result['error']}")
        sys.exit(1)
