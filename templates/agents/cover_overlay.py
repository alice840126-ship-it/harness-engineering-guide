#!/usr/bin/env python3
"""
블로그 커버 이미지 제목 오버레이 모듈.
blog-image 에이전트에서 import하여 사용.

사용법:
    from cover_overlay import add_cover_title
    add_cover_title("raw.png", "cover.png", "블로그 제목")
"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "Pillow", "-q"], check=True)
    from PIL import Image, ImageDraw, ImageFont


def add_cover_title(image_path: str, output_path: str, title: str) -> str:
    """
    커버 이미지에 제목 텍스트 오버레이를 추가한다.

    - 하단 35%부터 그라디언트 오버레이
    - 제목은 이미지 중앙(50%)에 배치
    - 단어 단위 줄바꿈 (이미지 폭 60% 이내)
    - 브랜드명/날짜 없음 — 제목만

    Args:
        image_path: 원본 이미지 경로 (Imagen 생성물)
        output_path: 오버레이 적용된 최종 이미지 저장 경로
        title: 블로그 제목 (한글)

    Returns:
        저장된 파일 경로
    """
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size

    # 폰트 로드
    font_dir = "/System/Library/Fonts"
    try:
        font_title = ImageFont.truetype(
            os.path.join(font_dir, "AppleSDGothicNeo.ttc"),
            int(H * 0.075),
            index=16  # ExtraBold
        )
    except Exception:
        font_title = ImageFont.load_default()

    # 그라디언트 오버레이 (35%부터 시작)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    gradient_start = int(H * 0.35)
    gradient_range = H - gradient_start
    for i in range(gradient_start, H):
        alpha = int(210 * (i - gradient_start) / gradient_range)
        alpha = min(alpha, 200)
        overlay_draw.line([(0, i), (W, i)], fill=(10, 10, 25, alpha))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 단어 단위 줄바꿈 — 폭 60% (네이버 블로그 썸네일 양쪽 크롭 대비)
    max_width = int(W * 0.60)
    words = title.split(" ")
    lines = []
    current_line = ""
    for word in words:
        test_line = (current_line + " " + word).strip()
        bbox = draw.textbbox((0, 0), test_line, font=font_title)
        if bbox[2] - bbox[0] > max_width and current_line:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # 제목 높이 계산 → 중앙 배치
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        line_heights.append(bbox[3] - bbox[1])
    line_gap = int(H * 0.02)
    total_h = sum(line_heights) + line_gap * (len(lines) - 1)
    title_y = int(H * 0.50) - total_h // 2

    # 제목 렌더링
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        t_tw = bbox[2] - bbox[0]
        tx = (W - t_tw) // 2
        draw.text(
            (tx, title_y), line, fill="white", font=font_title,
            stroke_width=4, stroke_fill="#080820"
        )
        title_y += line_heights[i] + line_gap

    # 저장
    img.convert("RGB").save(output_path, quality=97)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("사용법: python3 cover_overlay.py [원본이미지] [출력경로] [제목]")
        sys.exit(1)
    result = add_cover_title(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"완료: {result}")
