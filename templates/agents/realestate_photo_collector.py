#!/usr/bin/env python3
"""
부동산(아파트/오피스텔/지식산업센터 등) 단지명으로 실제 건물 외관 사진을 수집하는 에이전트.

사용 목적:
    시세·정보성 부동산 블로그는 AI 생성 이미지 대신 실제 건물 사진을 써야 신뢰도가 높다.
    단, 놀이터·평면도·인테리어·모델하우스 등 엉뚱한 사진이 섞이면 안 된다.

동작:
    1. Naver Image Search API로 "{단지명} 외관/전경/조감도" 검색
    2. 파일명·URL·썸네일 경로에서 금지 키워드(놀이터, 평면도, 인테리어 등) 필터
    3. 최소 크기(가로 500px, 세로 300px) 통과한 상위 N장 다운로드
    4. 가로가 세로보다 넓은 이미지(건물 전경에 가까움) 우선

사용법:
    # 단일 단지
    python3 realestate_photo_collector.py "DMC자이더리버" ./images 3

    # 여러 단지 일괄 (JSON 입력)
    python3 realestate_photo_collector.py --batch complexes.json ./images

    # Python import
    from realestate_photo_collector import collect_complex_photos
    result = collect_complex_photos("DMC자이더리버", "./images", count=3)

환경변수:
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET (~/.claude/.env 또는 ~/.env)
"""

import os
import re
import sys
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from PIL import Image
except ImportError:
    print("필요 패키지: pip3 install requests Pillow")
    sys.exit(1)

# .env 자동 로드
try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / ".env")
    load_dotenv(Path.home() / ".claude/.env")
except ImportError:
    pass

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

HEADERS_IMG = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
}

# 금지 패턴 — 파일명·URL·썸네일 경로·제목 어디든 하나라도 걸리면 제외
FORBIDDEN_PATTERNS = [
    r"놀이터", r"playground",
    r"평면도", r"도면", r"floorplan", r"floor[_-]?plan",
    r"인테리어", r"interior",
    r"모델하우스", r"model[_-]?house",
    r"조경", r"정원",                  # 정원/화단 사진
    r"로비", r"lobby",
    r"커뮤니티", r"헬스", r"스크린",     # 내부 시설
    r"주방", r"욕실", r"화장실",
    r"거실", r"침실", r"안방",
    r"엘리베이터", r"지하주차장",
    r"입주청소", r"이사",
    r"아파트키즈", r"kids",
    r"광고", r"banner", r"ad[s_-]",
    r"logo", r"icon",
    r"노선도", r"노선", r"지하철", r"광역버스", r"버스 시간표", r"교통 노선",
    r"지도", r"map[_-]", r"구역도", r"배치도",
    r"청약공고", r"분양 광고", r"전단",
    r"착공식", r"기공식",               # 행사 사진 (건물 외관 아님)
    r"blog\.kakaocdn",                 # 개인 블로그 이미지 지양 (저작권 리스크)
]
FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_PATTERNS), re.IGNORECASE)

# 선호 패턴 — 파일명/URL에 포함되면 가중치 ↑
PREFERRED_PATTERNS = [
    r"외관", r"전경", r"조감도", r"투시도", r"준공",
    r"exterior", r"view", r"aerial", r"building", r"perspective",
]
PREFERRED_RE = re.compile("|".join(PREFERRED_PATTERNS), re.IGNORECASE)


def _score_candidate(item: dict) -> int:
    """Naver 이미지 검색 결과 1건의 신뢰도 점수."""
    url = (item.get("link") or "").lower()
    thumb = (item.get("thumbnail") or "").lower()
    title = (item.get("title") or "").lower()
    combined = " ".join([url, thumb, title])

    if FORBIDDEN_RE.search(combined):
        return -1  # 즉시 탈락

    score = 0
    # 선호 키워드 포함 시 +2
    if PREFERRED_RE.search(combined):
        score += 2

    # 가로가 세로보다 긴 이미지 우선 (건물 전경은 가로가 넓음)
    try:
        w = int(item.get("sizewidth") or 0)
        h = int(item.get("sizeheight") or 0)
        if w >= 500 and h >= 300 and w > h:
            score += 3
        elif w >= 500 and h >= 300:
            score += 1
        else:
            score -= 1
    except Exception:
        pass

    # 공식 사이트(건설사/시공사 도메인) 가산점
    host = urlparse(url).netloc
    if any(k in host for k in ["hogangnono", "daum", "naver", "kbland", "zigbang", "dabangapp"]):
        score += 1

    # 호갱노노 outside(외관) 플래그 강력 가산
    if "t=outside" in url or "t%3Doutside" in url:
        score += 5
    # 호갱노노 review 경로는 사용자 업로드 → 노선도/광고 섞임, 감점
    elif "/review/" in url and "hogangnono" in host:
        score -= 2

    return score


def _naver_image_search(query: str, display: int = 20) -> list:
    """Naver 이미지 검색 API 호출."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수 없음")
    url = "https://openapi.naver.com/v1/search/image"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "sim", "filter": "large"}
    r = requests.get(url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("items", [])


def _download(url: str, save_path: Path, min_w: int = 500, min_h: int = 300) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS_IMG, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))
        w, h = img.size
        if w < min_w or h < min_h:
            return {"ok": False, "reason": f"too small {w}x{h}"}
        save_path.parent.mkdir(parents=True, exist_ok=True)
        # 통일된 포맷으로 저장 (JPEG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(save_path, "JPEG", quality=90)
        return {"ok": True, "path": str(save_path), "width": w, "height": h}
    except Exception as e:
        return {"ok": False, "reason": str(e)[:120]}


def collect_complex_photos(
    complex_name: str,
    save_dir: str,
    count: int = 3,
    slug: str = None,
) -> dict:
    """단일 단지 사진 수집.

    Args:
        complex_name: 단지명 (예: "DMC자이더리버")
        save_dir: 저장 폴더
        count: 다운로드 목표 장수
        slug: 파일명 접두사 (없으면 complex_name을 slug로 변환)

    Returns:
        {"ok": bool, "saved": [...], "sources_json": path}
    """
    if not slug:
        slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", complex_name).strip("-")

    # 쿼리 변형: 외관/전경 위주
    queries = [
        f"{complex_name} 외관",
        f"{complex_name} 전경",
        f"{complex_name} 아파트",
    ]

    all_items = []
    seen = set()
    for q in queries:
        try:
            items = _naver_image_search(q, display=20)
        except Exception as e:
            continue
        for it in items:
            link = it.get("link")
            if not link or link in seen:
                continue
            seen.add(link)
            it["_score"] = _score_candidate(it)
            it["_query"] = q
            all_items.append(it)

    # 점수 높은 순 정렬, -1(금지)은 제외
    ranked = sorted(
        [x for x in all_items if x.get("_score", -1) >= 0],
        key=lambda x: x["_score"],
        reverse=True,
    )

    saved = []
    idx = 1
    save_path = Path(save_dir)
    for it in ranked:
        if len(saved) >= count:
            break
        filename = f"{slug}-building-{idx}.jpg"
        filepath = save_path / filename
        result = _download(it["link"], filepath)
        if result["ok"]:
            saved.append({
                "filename": filename,
                "path": result["path"],
                "width": result["width"],
                "height": result["height"],
                "source_url": it.get("link"),
                "thumbnail": it.get("thumbnail"),
                "title": it.get("title"),
                "query": it.get("_query"),
                "score": it.get("_score"),
            })
            idx += 1

    # 출처 JSON 저장
    if saved:
        sources_path = save_path / f"{slug}-building-sources.json"
        save_path.mkdir(parents=True, exist_ok=True)
        with open(sources_path, "w", encoding="utf-8") as f:
            json.dump({"complex": complex_name, "images": saved}, f, ensure_ascii=False, indent=2)
    else:
        sources_path = None

    return {
        "ok": len(saved) > 0,
        "complex": complex_name,
        "saved_count": len(saved),
        "saved": saved,
        "sources_json": str(sources_path) if sources_path else None,
    }


def collect_batch(complexes: list, save_dir: str, count_each: int = 2) -> dict:
    """여러 단지 일괄 수집.

    Args:
        complexes: [{"name": "DMC자이더리버", "slug": "jari"}, ...] 또는 ["DMC자이더리버", ...]
    """
    results = []
    for entry in complexes:
        if isinstance(entry, str):
            name, slug = entry, None
        else:
            name, slug = entry.get("name"), entry.get("slug")
        r = collect_complex_photos(name, save_dir, count=count_each, slug=slug)
        results.append(r)
    total = sum(r["saved_count"] for r in results)
    return {"ok": total > 0, "total": total, "results": results}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "--batch":
        complexes_file = sys.argv[2]
        save_dir = sys.argv[3] if len(sys.argv) > 3 else "./images"
        with open(complexes_file) as f:
            complexes = json.load(f)
        out = collect_batch(complexes, save_dir)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        name = sys.argv[1]
        save_dir = sys.argv[2] if len(sys.argv) > 2 else "./images"
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        out = collect_complex_photos(name, save_dir, count=count)
        print(json.dumps(out, ensure_ascii=False, indent=2))
