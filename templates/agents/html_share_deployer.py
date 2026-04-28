#!/usr/bin/env python3
"""
외부 공유용 HTML 배포 모듈.
Vercel CLI로 HTML 파일을 배포하고 단축 URL을 반환한다.

어디서든 동일하게 사용:
- 터미널 Claude Code: from html_share_deployer import deploy
- 텔레그램 봇: from html_share_deployer import deploy
- 스크립트: python3 html_share_deployer.py "파일.html"

=== 외부 공유 규칙 (필수) ===
1. 배포: Vercel CLI (배포마다 고유 프로젝트명 → 고유 URL)
2. 파일명: 영문 슬러그 (한글 → 자동 변환)
3. 단축 URL: is.gd로 단축 후 반환
4. cdn.jsdelivr.net / github.com blob URL 절대 사용 금지

=== 2026-04-18 Netlify → Vercel 전환 ===
Netlify 무료 계정이 disabled 처리되어 Vercel로 이관.
Vercel은 프로젝트마다 고유 도메인을 부여하므로 배포가 서로 덮어쓰지 않는다.
=============================
"""
import os
import sys
import re
import shutil
import unicodedata
import tempfile
import time
from pathlib import Path

# SPoE — 모든 Vercel 호출은 vercel_adapter 경유 (HARNESS_DOMAIN_REGISTRY.md)
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from vercel_adapter import deploy_dir as _vercel_deploy_dir, shorten_url as _vercel_shorten


def to_english_slug(filename: str) -> str:
    """한글 파일명 → 영문 슬러그.
    예: 공인중개사-공시법-학습노트.html → gongsi-study
    예: 2026-04-06-korean-law-mcp-설치-사용법.html → 2026-0406-korean-law-mcp
    """
    stem = Path(filename).stem

    date_match = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.*)", stem)
    if date_match:
        year, month, day, rest = date_match.groups()
        date_part = f"{year}-{month}{day}"
    else:
        date_part = ""
        rest = stem

    rest = unicodedata.normalize("NFKD", rest)
    rest = re.sub(r"[^\x00-\x7F]", "", rest)
    rest = re.sub(r"[^a-zA-Z0-9\-]", "-", rest)
    rest = re.sub(r"-+", "-", rest).strip("-")
    rest = rest[:30].rstrip("-")

    if rest:
        slug = f"{date_part}-{rest}" if date_part else rest
    else:
        slug = date_part if date_part else "post"
    return slug.lower()


def _shorten(url: str) -> str:
    """is.gd 단축 — vercel_adapter.shorten_url 래퍼 (실패 시 원본 반환)."""
    return _vercel_shorten(url)


def deploy(html_path: str, project_name: str = None) -> dict:
    """HTML 파일을 Vercel에 배포하고 단축 URL 반환.

    Args:
        html_path: 배포할 HTML 파일 경로. 디렉터리를 넘기면 해당 디렉터리 전체 배포.
        project_name: Vercel 프로젝트명 (생략 시 슬러그 + 타임스탬프 자동 생성)

    Returns:
        {"short_url": "https://is.gd/xxx", "site_url": "https://<proj>.vercel.app",
         "slug": "파일명", "ok": True}
        실패 시 {"ok": False, "error": "메시지"}
    """
    html_file = Path(html_path)
    if not html_file.exists():
        return {"ok": False, "error": f"경로 없음: {html_path}"}

    if html_file.is_dir():
        slug = to_english_slug(html_file.name)
        deploy_dir = str(html_file)
        owns_tmp = False
    else:
        slug = to_english_slug(html_file.name)
        tmp_dir = tempfile.mkdtemp(prefix="vercel-deploy-")
        shutil.copy2(str(html_file), os.path.join(tmp_dir, "index.html"))
        deploy_dir = tmp_dir
        owns_tmp = True

    if not project_name:
        ts = time.strftime("%m%d%H%M")
        project_name = f"{slug}-{ts}"[:50].rstrip("-") or f"share-{ts}"

    try:
        r = _vercel_deploy_dir(deploy_dir, project_name=project_name, timeout=180)
        if not r["ok"]:
            err = r.get("stderr_tail") or r.get("error", "")
            return {"ok": False, "error": f"{r.get('error', 'Vercel 배포 실패')}: {err[:400]}"}
        site_url = r["site_url"]
    finally:
        if owns_tmp:
            shutil.rmtree(deploy_dir, ignore_errors=True)

    return {
        "ok": True,
        "short_url": _shorten(site_url),
        "site_url": site_url,
        "slug": slug,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 html_share_deployer.py [HTML파일 또는 디렉터리] [프로젝트명(옵션)]")
        sys.exit(1)

    name = sys.argv[2] if len(sys.argv) >= 3 else None
    result = deploy(sys.argv[1], project_name=name)
    if result["ok"]:
        print(f"배포 완료!")
        print(f"  단축 URL: {result['short_url']}")
        print(f"  사이트 URL: {result['site_url']}")
        print(f"  슬러그: {result['slug']}")
    else:
        print(f"실패: {result['error']}")
        sys.exit(1)
