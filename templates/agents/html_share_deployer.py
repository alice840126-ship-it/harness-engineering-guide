#!/usr/bin/env python3
"""
외부 공유용 HTML 배포 모듈.
Netlify CLI로 HTML 파일을 배포하고 단축 URL을 반환한다.

어디서든 동일하게 사용:
- 터미널 Claude Code: from html_share_deployer import deploy
- 텔레그램 봇: from html_share_deployer import deploy
- 스크립트: python3 html_share_deployer.py "파일.html"

=== 외부 공유 규칙 (필수) ===
1. 배포: Netlify CLI (alice-share.netlify.app)
2. 파일명: 영문 슬러그 (한글 → 자동 변환)
3. 단축 URL: is.gd로 단축 후 반환
4. cdn.jsdelivr.net / github.com blob URL 절대 사용 금지
=============================
"""
import os
import sys
import re
import shutil
import subprocess
import unicodedata
import tempfile
from pathlib import Path


NETLIFY_SITE_ID = "9d8e40ce-a066-40ed-86c4-a7220f481a23"
NETLIFY_BASE = "https://alice-share.netlify.app"


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
    return slug


def deploy(html_path: str) -> dict:
    """HTML 파일을 Netlify에 배포하고 단축 URL 반환.

    Args:
        html_path: 배포할 HTML 파일 경로

    Returns:
        {"short_url": "https://is.gd/xxx", "site_url": "https://alice-share.netlify.app", "slug": "파일명", "ok": True}
        실패 시 {"ok": False, "error": "메시지"}
    """
    html_file = Path(html_path)
    if not html_file.exists():
        return {"ok": False, "error": f"파일 없음: {html_path}"}

    slug = to_english_slug(html_file.name)

    # 임시 폴더에 index.html로 복사 (Netlify는 index.html을 루트로 서빙)
    with tempfile.TemporaryDirectory() as tmp_dir:
        shutil.copy2(str(html_file), os.path.join(tmp_dir, "index.html"))

        # Netlify CLI로 배포
        result = subprocess.run(
            ["netlify", "deploy", f"--dir={tmp_dir}", "--prod",
             f"--site={NETLIFY_SITE_ID}"],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            return {"ok": False, "error": f"Netlify 배포 실패: {result.stderr.strip()[:200]}"}

    # 사이트 URL
    site_url = NETLIFY_BASE

    # is.gd 단축
    try:
        short = subprocess.run(
            ["curl", "-s", f"https://is.gd/create.php?format=simple&url={site_url}"],
            capture_output=True, text=True, timeout=10,
        )
        short_url = short.stdout.strip()
        if not short_url.startswith("http"):
            short_url = site_url
    except Exception:
        short_url = site_url

    return {
        "ok": True,
        "short_url": short_url,
        "site_url": site_url,
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
        print(f"  사이트 URL: {result['site_url']}")
        print(f"  파일명: {result['slug']}")
    else:
        print(f"실패: {result['error']}")
        sys.exit(1)
