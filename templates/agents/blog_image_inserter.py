#!/usr/bin/env python3
"""
블로그 마크다운에 이미지를 삽입하는 스크립트.

사용법:
    python3 blog_image_inserter.py "블로그.md" "이미지슬러그"

예시:
    python3 blog_image_inserter.py "2026-04-10-부모님-어버이날-선물-추천.md" "2026-04-10-부모님선물"

동작:
    1. [이미지] 플레이스홀더 전부 삭제
    2. H1 제목 위에 커버 이미지 삽입
    3. 각 H2 제목 아래에 섹션 이미지 삽입 (파일 존재 시에만)
    4. 결과를 같은 파일에 덮어쓰기
"""

import sys
import re
import urllib.parse
from pathlib import Path

# 2026-04-25 마이그레이션: 이미지를 데스크탑으로 분리 + symlink로 vault에서 접근
# 2026-04-28 fix: file:// 절대경로 → vault 내 상대경로 (symlink 통해 옵시디언이 미리보기 인식)
# - 실제 저장: /Users/oungsooryu/Desktop/류웅수/블로그/images
# - vault symlink: 블로그 초안/images → 위 경로
# - md 경로: images/FILENAME (한글 그대로, 옵시디언이 vault 내부 인식)
IMAGES_DIR = Path("/Users/oungsooryu/Desktop/류웅수/블로그/images")


def _img_url(filename: str) -> str:
    """md에 박을 이미지 경로 — 옵시디언 vault 기준 상대경로 (symlink 통해 데스크탑 실제 파일 가리킴)."""
    return f"images/{filename}"


def insert_images(md_path: str, slug: str) -> dict:
    md_file = Path(md_path)
    if not md_file.exists():
        return {"ok": False, "error": f"파일 없음: {md_path}"}

    images_dir = IMAGES_DIR
    text = md_file.read_text(encoding="utf-8")

    # 1. [이미지] 플레이스홀더 전부 삭제
    before_count = len(re.findall(r'^\[이미지[^\]]*\]\s*$', text, flags=re.MULTILINE))
    text = re.sub(r'^\[이미지[^\]]*\]\s*\n?', '', text, flags=re.MULTILINE)

    # 2. 커버 이미지 삽입 (H1 제목 위에, 이미 있으면 스킵)
    cover_file = images_dir / f"{slug}-cover.png"
    cover_md = f"![표지]({_img_url(f'{slug}-cover.png')})"
    if cover_file.exists() and cover_md not in text:
        text = re.sub(
            r'^(# .+)$',
            f'{cover_md}\n\n\\1',
            text,
            count=1,
            flags=re.MULTILINE
        )

    # 3. 각 H2 제목 아래에 섹션 이미지 삽입
    h2_pattern = re.compile(r'^(## .+)$', re.MULTILINE)
    h2_matches = list(h2_pattern.finditer(text))
    inserted = 0

    # 뒤에서부터 삽입 (인덱스 깨짐 방지)
    for i, match in reversed(list(enumerate(h2_matches))):
        section_num = i + 1
        section_file = images_dir / f"{slug}-section-{section_num}.png"
        section_md = f"![섹션{section_num}]({_img_url(f'{slug}-section-{section_num}.png')})"

        if section_file.exists() and section_md not in text:
            insert_pos = match.end()
            text = text[:insert_pos] + f"\n\n{section_md}" + text[insert_pos:]
            inserted += 1

    # 4. 저장
    md_file.write_text(text, encoding="utf-8")

    # 5. 검증
    remaining = len(re.findall(r'\[이미지', text))

    return {
        "ok": True,
        "placeholders_removed": before_count,
        "cover_inserted": cover_file.exists(),
        "sections_inserted": inserted,
        "remaining_placeholders": remaining,
        "path": str(md_file),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python3 blog_image_inserter.py <MD파일> <이미지슬러그>")
        print("예시: python3 blog_image_inserter.py blog.md 2026-04-10-부모님선물")
        sys.exit(1)

    result = insert_images(sys.argv[1], sys.argv[2])

    if result["ok"]:
        print(f"✅ 이미지 삽입 완료!")
        print(f"   [이미지] 삭제: {result['placeholders_removed']}개")
        print(f"   커버 삽입: {'✓' if result['cover_inserted'] else '✗ (파일 없음)'}")
        print(f"   섹션 삽입: {result['sections_inserted']}개")
        print(f"   남은 플레이스홀더: {result['remaining_placeholders']}개")
    else:
        print(f"❌ {result['error']}")
        sys.exit(1)
