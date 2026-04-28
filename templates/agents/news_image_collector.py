#!/usr/bin/env python3
"""
뉴스 페이지에서 실제 본문 이미지를 추출/다운로드하는 에이전트.

사용법:
    python3 news_image_collector.py <URL> <저장폴더> [슬러그_프리픽스]
    python3 news_image_collector.py --batch <urls.txt> <저장폴더> <슬러그_프리픽스>

동작:
    1. 뉴스 페이지에 접근 (User-Agent 위장)
    2. og:image meta 우선 → 본문 <img> 태그 fallback
    3. 광고/아이콘/SNS 버튼 등 노이즈 필터
    4. 이미지 다운로드 + 출처 정보 JSON 저장
    5. 가로 400px 이상, 세로 200px 이상만 채택

출력:
    {저장폴더}/{슬러그}-news-1.jpg, {슬러그}-news-2.jpg, ...
    {저장폴더}/{슬러그}-news-sources.json (출처 정보)
"""

import sys
import os
import re
import json
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    from PIL import Image
    from io import BytesIO
except ImportError:
    print("필요 패키지: pip3 install requests beautifulsoup4 Pillow")
    sys.exit(1)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 광고/아이콘/SNS 버튼 등 제외할 패턴
EXCLUDE_PATTERNS = [
    r'logo', r'icon', r'avatar', r'profile', r'banner',
    r'ads?[/_-]', r'advertis', r'sponsor',
    r'facebook', r'twitter', r'kakao', r'instagram', r'youtube',
    r'btn[/_-]', r'button', r'pixel', r'tracker',
    r'1x1', r'spacer', r'blank',
    r'.gif$',  # 대부분 광고/아이콘
]

EXCLUDE_RE = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)


def is_valid_image_url(url: str) -> bool:
    """제외 패턴에 매칭되지 않는 이미지인지 확인"""
    if not url:
        return False
    if EXCLUDE_RE.search(url):
        return False
    if not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', url, re.IGNORECASE):
        return False
    return True


def fetch_page(url: str, timeout: int = 15):
    """뉴스 페이지 HTML 가져오기"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text, resp.url
    except Exception as e:
        return None, None


def extract_image_urls(html: str, base_url: str, max_count: int = 5) -> list:
    """페이지에서 본문 이미지 URL 추출"""
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []

    # 1순위: og:image meta tag (대표 이미지)
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        url = urljoin(base_url, og_img['content'])
        if is_valid_image_url(url):
            candidates.append({'url': url, 'source': 'og:image', 'priority': 1})

    # 2순위: twitter:image
    tw_img = soup.find('meta', attrs={'name': 'twitter:image'})
    if tw_img and tw_img.get('content'):
        url = urljoin(base_url, tw_img['content'])
        if is_valid_image_url(url) and url not in [c['url'] for c in candidates]:
            candidates.append({'url': url, 'source': 'twitter:image', 'priority': 2})

    # 3순위: article 본문 안의 img 태그
    article_areas = soup.find_all(['article', 'main'])
    if not article_areas:
        # article 태그 없으면 클래스/id명으로 추측 (위키, 블로그, 뉴스 등 다양한 구조 대응)
        article_areas = soup.find_all(
            class_=re.compile(r'article|content|news|body|view|entry|post|mw-parser-output', re.I)
        )
    if not article_areas:
        # id로도 시도
        article_areas = soup.find_all(id=re.compile(r'content|article|main|body', re.I))

    for area in article_areas[:3]:
        for img in area.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy-src')
            if not src:
                continue
            url = urljoin(base_url, src)
            if is_valid_image_url(url) and url not in [c['url'] for c in candidates]:
                alt = img.get('alt', '')
                candidates.append({
                    'url': url,
                    'source': 'article-img',
                    'alt': alt,
                    'priority': 3
                })
                if len(candidates) >= max_count * 2:
                    break

    # 4순위 (최종 fallback): 위 단계에서 후보가 부족하면 페이지 전체 img 검색
    if len(candidates) < max_count:
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-original') or img.get('data-lazy-src')
            if not src:
                continue
            url = urljoin(base_url, src)
            if is_valid_image_url(url) and url not in [c['url'] for c in candidates]:
                alt = img.get('alt', '')
                candidates.append({
                    'url': url,
                    'source': 'page-fallback',
                    'alt': alt,
                    'priority': 4
                })
                if len(candidates) >= max_count * 2:
                    break

    return candidates[:max_count * 2]


def download_image(url: str, save_path: Path, min_width: int = 400, min_height: int = 200) -> dict:
    """이미지 다운로드 + 크기 검증"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()

        # 이미지로 로드해서 크기 확인
        img_data = resp.content
        img = Image.open(BytesIO(img_data))
        width, height = img.size

        if width < min_width or height < min_height:
            return {'ok': False, 'reason': f'too small ({width}x{height})'}

        # 저장
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(img_data)

        return {
            'ok': True,
            'path': str(save_path),
            'width': width,
            'height': height,
            'size_kb': len(img_data) // 1024,
        }
    except Exception as e:
        return {'ok': False, 'reason': str(e)[:100]}


def collect_from_url(news_url: str, save_dir: str, slug_prefix: str, max_images: int = 3) -> dict:
    """단일 뉴스 URL에서 이미지 수집"""
    html, final_url = fetch_page(news_url)
    if not html:
        return {'ok': False, 'error': 'fetch failed', 'url': news_url}

    candidates = extract_image_urls(html, final_url or news_url, max_count=max_images)
    if not candidates:
        return {'ok': False, 'error': 'no images found', 'url': news_url}

    save_path = Path(save_dir)
    saved = []
    idx = 1

    for cand in candidates:
        if len(saved) >= max_images:
            break

        # 파일명: 슬러그-news-N.jpg
        ext = re.search(r'\.(jpg|jpeg|png|webp)', cand['url'], re.IGNORECASE)
        ext = ext.group(1).lower() if ext else 'jpg'
        if ext == 'jpeg':
            ext = 'jpg'

        filename = f"{slug_prefix}-news-{idx}.{ext}"
        filepath = save_path / filename

        result = download_image(cand['url'], filepath)
        if result['ok']:
            saved.append({
                'filename': filename,
                'path': result['path'],
                'width': result['width'],
                'height': result['height'],
                'source_url': news_url,
                'image_url': cand['url'],
                'source_type': cand['source'],
                'alt': cand.get('alt', ''),
            })
            idx += 1

    return {
        'ok': len(saved) > 0,
        'saved_count': len(saved),
        'images': saved,
        'source_url': news_url,
    }


def collect_batch(urls: list, save_dir: str, slug_prefix: str, max_per_url: int = 2) -> dict:
    """여러 뉴스 URL에서 일괄 수집"""
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    all_images = []
    failed = []
    counter = 1

    for url in urls:
        html, final_url = fetch_page(url)
        if not html:
            failed.append({'url': url, 'reason': 'fetch failed'})
            continue

        candidates = extract_image_urls(html, final_url or url, max_count=max_per_url)
        if not candidates:
            failed.append({'url': url, 'reason': 'no images'})
            continue

        downloaded_from_this_url = 0
        for cand in candidates:
            if downloaded_from_this_url >= max_per_url:
                break

            ext = re.search(r'\.(jpg|jpeg|png|webp)', cand['url'], re.IGNORECASE)
            ext = ext.group(1).lower() if ext else 'jpg'
            if ext == 'jpeg':
                ext = 'jpg'

            filename = f"{slug_prefix}-news-{counter}.{ext}"
            filepath = save_path / filename

            result = download_image(cand['url'], filepath)
            if result['ok']:
                all_images.append({
                    'filename': filename,
                    'path': result['path'],
                    'width': result['width'],
                    'height': result['height'],
                    'source_url': url,
                    'image_url': cand['url'],
                    'source_type': cand['source'],
                    'alt': cand.get('alt', ''),
                })
                counter += 1
                downloaded_from_this_url += 1

    # 출처 정보 JSON 저장
    sources_path = save_path / f"{slug_prefix}-news-sources.json"
    with open(sources_path, 'w', encoding='utf-8') as f:
        json.dump({
            'images': all_images,
            'failed': failed,
            'total': len(all_images),
        }, f, ensure_ascii=False, indent=2)

    return {
        'ok': len(all_images) > 0,
        'total': len(all_images),
        'failed': len(failed),
        'sources_json': str(sources_path),
    }


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--batch":
        urls_file = sys.argv[2]
        save_dir = sys.argv[3]
        slug = sys.argv[4] if len(sys.argv) > 4 else "news"

        with open(urls_file) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]

        result = collect_batch(urls, save_dir, slug)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        url = sys.argv[1]
        save_dir = sys.argv[2]
        slug = sys.argv[3] if len(sys.argv) > 3 else "news"

        result = collect_from_url(url, save_dir, slug)
        print(json.dumps(result, ensure_ascii=False, indent=2))
