#!/usr/bin/env python3
"""
네이버 블로그 전체 글 크롤러.

사용법:
    python3 naver_blog_scraper.py <blogId> [저장폴더]

예시:
    python3 naver_blog_scraper.py bambooinvesting

동작:
    1. 전체 글 logNo 목록 수집 (PostTitleListAsync)
    2. 각 글 본문 크롤링 (m.blog.naver.com 모바일 페이지)
    3. 옵시디언 마크다운 형식으로 저장
    4. 진행 상황 표시
"""

import sys
import re
import json
import time
from datetime import datetime, date as date_cls
from pathlib import Path
from urllib.parse import unquote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("필요 패키지: pip3 install requests beautifulsoup4")
    sys.exit(1)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def get_all_post_list(blog_id: str, max_pages: int = 200):
    """전체 글 logNo 목록 수집"""
    all_logs = []
    page = 1
    headers = {**HEADERS, "Referer": f"https://blog.naver.com/{blog_id}"}

    while page <= max_pages:
        url = f"https://blog.naver.com/PostTitleListAsync.naver?blogId={blog_id}&countPerPage=30&currentPage={page}"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            text = r.text
            log_nos = re.findall(r'"logNo"\s*:\s*"?(\d+)"?', text)
            titles = re.findall(r'"title"\s*:\s*"([^"]*)"', text)
            add_dates = re.findall(r'"addDate"\s*:\s*"?(\d+)"?', text)

            if not log_nos:
                break

            for i, log in enumerate(log_nos):
                # URL 디코드 및 JSON 이스케이프 정리
                title = titles[i] if i < len(titles) else ''
                try:
                    title = title.encode().decode('unicode_escape')
                    title = unquote(title)
                except Exception:
                    pass
                all_logs.append({
                    'logNo': log,
                    'title': title,
                    'addDate': add_dates[i] if i < len(add_dates) else '',
                })

            print(f"  페이지 {page}: {len(log_nos)}개 (누적 {len(all_logs)}개)", file=sys.stderr)
            page += 1
            time.sleep(0.2)
        except Exception as e:
            print(f"  페이지 {page} 실패: {e}", file=sys.stderr)
            break

    return all_logs


# ---- 파일명/날짜 유틸 (다른 파이프라인에서도 import해서 사용) -------------
LOGNO_PATTERN = re.compile(r'(?:(\d{4}-\d{2}-\d{2})_)?(\d+)_(.+?)\.md$')


def extract_log_no(filename: str) -> str:
    """파일명에서 logNo만 추출 (구/신 포맷 둘 다).

    - 구 포맷: "{logNo}_{title}.md"
    - 신 포맷: "{YYYY-MM-DD}_{logNo}_{title}.md"
    """
    m = LOGNO_PATTERN.search(filename)
    return m.group(2) if m else ""


def extract_pub_date_from_name(filename: str) -> str:
    """파일명에서 발행일(YYYY-MM-DD) 추출. 구 포맷이면 빈 문자열."""
    m = LOGNO_PATTERN.search(filename)
    return m.group(1) if (m and m.group(1)) else ""


def extract_title_from_name(filename: str) -> str:
    """파일명에서 제목 부분 추출."""
    m = LOGNO_PATTERN.search(filename)
    return m.group(3) if m else ""


def normalize_date(date_str: str) -> str:
    """다양한 네이버 블로그 날짜 표현 → YYYY-MM-DD.

    처리 대상:
    - ISO 8601: 2026-04-12T09:00:00+09:00
    - RSS pubDate: "Mon, 12 Apr 2026 20:30:00 +0900"
    - 한글: "2026. 4. 12.", "2026.4.12"
    - addDate (YYYYMMDDHHMM 14자리 등)
    """
    if not date_str:
        return ""
    s = str(date_str).strip()

    # ISO 8601
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # 한글 2026. 4. 12.
    m = re.match(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # RSS pubDate
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # addDate: YYYYMMDD... (최소 8자리 숫자)
    m = re.match(r'^(\d{4})(\d{2})(\d{2})', s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    return ""


def find_existing_post(save_dir: Path, log_no: str):
    """save_dir에서 해당 logNo의 기존 파일 찾기 (구/신 포맷 모두)."""
    if not save_dir.exists():
        return None
    for f in save_dir.glob("*.md"):
        if extract_log_no(f.name) == str(log_no):
            return f
    return None


def fetch_post(blog_id: str, log_no: str) -> dict:
    """단일 글 본문 추출 (모바일 페이지 사용)"""
    url = f"https://m.blog.naver.com/{blog_id}/{log_no}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')

    # 제목
    title_el = soup.find('meta', property='og:title')
    title = title_el['content'] if title_el and title_el.get('content') else ''

    # 본문
    content_div = (
        soup.find('div', class_='se-main-container')
        or soup.find('div', id='post_1')
        or soup.find('div', class_='post_ct')
    )
    content = content_div.get_text(separator='\n', strip=True) if content_div else ''

    # 날짜
    date = ''
    date_el = soup.find('span', class_='se_publishDate')
    if date_el:
        date = date_el.get_text(strip=True)
    else:
        # 모바일 형식 시도
        meta_date = soup.find('meta', property='article:published_time')
        if meta_date:
            date = meta_date.get('content', '')

    return {
        'title': title.strip(),
        'content': content,
        'date': date,
        'url': url,
    }


def sanitize_filename(text: str, max_len: int = 50) -> str:
    """파일명에 쓸 수 있게 정리"""
    text = re.sub(r'[/\\:*?"<>|]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


def save_to_obsidian(
    post_data: dict,
    log_no: str,
    save_dir: Path,
    blog_id: str,
    original_author: str = None,
    extra_tags: list = None,
) -> Path:
    """옵시디언 마크다운 형식으로 저장.

    파일명: {YYYY-MM-DD}_{logNo}_{title}.md
    (발행일 파싱 실패 시: {logNo}_{title}.md — 구 포맷)

    YAML: 표준 5필드(type/author/date created/date modified/tags) +
          블로그 원본 메타(source_blog/original_author/url/date_published/logNo/post_title)

    Returns: 저장된 파일 경로 (Path)
    """
    save_dir.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize_filename(post_data['title'])
    pub_date = normalize_date(post_data.get('date', ''))
    today = date_cls.today().isoformat()

    if pub_date:
        filename = f"{pub_date}_{log_no}_{safe_title}.md"
    else:
        filename = f"{log_no}_{safe_title}.md"

    tags = ["뇌훔치기", "원본"]
    if original_author:
        tags.append(original_author)
    if extra_tags:
        tags.extend(extra_tags)
    tags_str = "[" + ", ".join(tags) + "]"

    title_escaped = post_data['title'].replace('"', '\\"')
    author_line = f'  - "[[{original_author}]]"\n' if original_author else ""

    frontmatter = f"""---
type: analysis
author:
  - "[[류웅수]]"
{author_line}date created: {today}
date modified: {today}
tags: {tags_str}
source_blog: {blog_id}
original_author: {original_author or ""}
url: {post_data['url']}
date_published: {pub_date}
logNo: {log_no}
post_title: "{title_escaped}"
---

# {post_data['title']}

{post_data['content']}

---
※ 출처: [블로그 원본]({post_data['url']})
"""
    file_path = save_dir / filename
    file_path.write_text(frontmatter, encoding='utf-8')
    return file_path


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 naver_blog_scraper.py <blogId> [저장폴더] [--author 작가명]")
        sys.exit(1)

    args = sys.argv[1:]
    author_name = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--author" and i + 1 < len(args):
            author_name = args[i + 1]
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if not positional:
        print("사용법: python3 naver_blog_scraper.py <blogId> [저장폴더] [--author 작가명]")
        sys.exit(1)

    blog_id = positional[0]
    blog_name_map = {
        "bambooinvesting": "모소밤부",
        "ranto28": "메르의 세상읽기",
    }
    if len(positional) >= 2:
        save_dir = Path(positional[1])
    else:
        blog_folder = blog_name_map.get(blog_id, blog_id)
        save_dir = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수/해상도 프로젝트" / blog_folder / "원본"
    if not author_name:
        author_name = blog_name_map.get(blog_id, blog_id)

    print(f"=== 블로그 크롤러 시작 ===")
    print(f"blogId: {blog_id}")
    print(f"저장 폴더: {save_dir}")
    print()

    # 1단계: 전체 글 목록
    print("1단계: 전체 글 목록 수집 중...")
    posts = get_all_post_list(blog_id)
    print(f"→ 총 {len(posts)}개 글 발견\n")

    if not posts:
        print("글 목록 수집 실패")
        sys.exit(1)

    # 2단계: 본문 크롤링
    print("2단계: 각 글 본문 크롤링 + 옵시디언 저장...")
    success = 0
    failed = []

    for i, post in enumerate(posts, 1):
        log_no = post['logNo']
        try:
            # 이미 저장된 파일은 스킵 (구/신 포맷 모두)
            if find_existing_post(save_dir, log_no):
                success += 1
                if i % 50 == 0:
                    print(f"[{i}/{len(posts)}] 스킵(기존): {post.get('title', '')[:40]}")
                continue

            data = fetch_post(blog_id, log_no)
            if not data['content']:
                raise ValueError("본문 추출 실패")
            save_to_obsidian(data, log_no, save_dir, blog_id, original_author=author_name)
            success += 1
            title_short = data['title'][:40] if data['title'] else post.get('title', '')[:40]
            if i % 20 == 0 or i == 1:
                print(f"[{i}/{len(posts)}] {title_short}")
        except Exception as e:
            failed.append({'logNo': log_no, 'error': str(e)[:80]})
            print(f"[{i}/{len(posts)}] 실패 {log_no}: {e}", file=sys.stderr)

        time.sleep(0.3)  # 부하 방지

    # 3단계: 요약
    print(f"\n=== 크롤링 완료 ===")
    print(f"성공: {success}/{len(posts)}")
    print(f"실패: {len(failed)}")
    print(f"저장 폴더: {save_dir}")

    if failed:
        failed_path = save_dir / "_failed.json"
        with open(failed_path, 'w', encoding='utf-8') as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"실패 로그: {failed_path}")


if __name__ == "__main__":
    main()
