#!/usr/bin/env python3
"""
뉴스 사진 후처리 — AI 이미지 톤에 맞춰 동적 프레임 적용.

AI 생성 이미지의 색상 팔레트를 자동 추출해서, 같은 톤의 프레임으로 사진을 감싼다.
이렇게 하면 어떤 AI 스타일(watercolor, cyberpunk, minimal 등)이든 사진과 일러스트가
시각적으로 통일된다.

사용법:
    python3 news_image_processor.py <input> <output> ["출처"] [--ref AI이미지경로] [--style frame|simple] [--source-url URL]

옵션:
    --source-url URL    출처 URL을 주면 자동으로 도메인에서 매체명 추출
                        (한경, 머니투데이, 헤럴드경제 등 자동 매핑)
                        이안이 출처 이름을 잘못 만드는 것 방지

동작 (frame 모드, 기본값):
    1. 16:9 비율로 크롭
    2. AI 참조 이미지에서 색상 팔레트 추출 (있으면)
    3. 추출된 톤으로 매트 + 내부 선 색상 결정
    4. 사진 영역에 살짝 그림자 (인셋 효과)
    5. 캡션은 하단 매트 영역에 작은 글씨로

색상 매칭 로직:
    - 참조 이미지의 가장 밝은 톤 → 매트 배경
    - 참조 이미지의 중간 어두운 톤 → 내부 선
    - 참조 이미지의 가장 어두운 톤 → 캡션 텍스트
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("필요 패키지: pip3 install Pillow")
    sys.exit(1)


# 출력 사이즈 (16:9, AI 생성 이미지와 동일)
OUTPUT_WIDTH = 1408
OUTPUT_HEIGHT = 768

# === Frame 스타일 (액자) — watercolor 일러스트 톤과 매칭 ===
FRAME_OUTER_PADDING = 60         # 외부 매트 두께 (사진 주변 베이지 영역)
FRAME_BOTTOM_EXTRA = 30          # 하단 캡션을 위한 추가 공간
FRAME_MAT_COLOR = (242, 232, 213)  # #F2E8D5 — 따뜻한 베이지 매트
FRAME_INNER_LINE_COLOR = (184, 149, 106)  # #B8956A — 우드 톤 선
FRAME_INNER_LINE_WIDTH = 4
FRAME_INNER_LINE_GAP = 18        # 우드 선과 사진 사이 간격
FRAME_OUTER_RADIUS = 16          # 외곽 둥근 모서리

# 사진 영역 그림자 (인셋 느낌)
PHOTO_SHADOW_COLOR = (60, 40, 20, 100)
PHOTO_SHADOW_OFFSET = 4

# Frame 스타일 캡션 (매트 위에 작은 글씨)
FRAME_CAPTION_COLOR = (120, 90, 50, 220)  # 진한 우드 톤
FRAME_CAPTION_FONT_SIZE = 22
FRAME_CAPTION_BOTTOM_OFFSET = 32  # 하단에서부터 거리

# === Simple 스타일 (기존 방식) ===
CORNER_RADIUS = 12
BORDER_COLOR = (220, 220, 220, 255)
BORDER_WIDTH = 1

CAPTION_HEIGHT = 56
CAPTION_BG = (0, 0, 0, 140)
CAPTION_TEXT_COLOR = (255, 255, 255, 230)
CAPTION_PADDING = 18
CAPTION_FONT_SIZE = 20

# 폰트 경로 (macOS)
FONT_PATHS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
]

# 도메인 → 매체명 자동 매핑 (이안이 출처 잘못 만드는 거 방지)
DOMAIN_TO_MEDIA = {
    "mt.co.kr": "머니투데이",
    "news.mt.co.kr": "머니투데이",
    "hankyung.com": "한국경제",
    "www.hankyung.com": "한국경제",
    "heraldcorp.com": "헤럴드경제",
    "biz.heraldcorp.com": "헤럴드경제",
    "wimg.heraldcorp.com": "헤럴드경제",
    "sedaily.com": "서울경제",
    "www.sedaily.com": "서울경제",
    "seoul.co.kr": "서울신문",
    "www.seoul.co.kr": "서울신문",
    "etoday.co.kr": "이투데이",
    "www.etoday.co.kr": "이투데이",
    "munhwa.com": "문화일보",
    "www.munhwa.com": "문화일보",
    "newspim.com": "뉴스핌",
    "www.newspim.com": "뉴스핌",
    "newscj.com": "천지일보",
    "www.newscj.com": "천지일보",
    "sisajournal-e.com": "시사저널e",
    "www.sisajournal-e.com": "시사저널e",
    "housingherald.co.kr": "하우징헤럴드",
    "www.housingherald.co.kr": "하우징헤럴드",
    "fnnews.com": "파이낸셜뉴스",
    "www.fnnews.com": "파이낸셜뉴스",
    "asiae.co.kr": "아시아경제",
    "www.asiae.co.kr": "아시아경제",
    "joongang.co.kr": "중앙일보",
    "www.joongang.co.kr": "중앙일보",
    "chosun.com": "조선일보",
    "www.chosun.com": "조선일보",
    "donga.com": "동아일보",
    "www.donga.com": "동아일보",
    "yna.co.kr": "연합뉴스",
    "www.yna.co.kr": "연합뉴스",
    "newsis.com": "뉴시스",
    "www.newsis.com": "뉴시스",
    "kr.trip.com": "트립닷컴",
    "blog.idbins.com": "아이디빈스",
    "biz.newdaily.co.kr": "뉴데일리",
    "newdaily.co.kr": "뉴데일리",
    "gungsireong.com": "포커스경제",
    "www.gungsireong.com": "포커스경제",
    "opinionnews.co.kr": "오피니언뉴스",
    "www.opinionnews.co.kr": "오피니언뉴스",
    "peoplenews.kr": "국민문화신문",
    "www.peoplenews.kr": "국민문화신문",
    "bloter.net": "블로터",
    "www.bloter.net": "블로터",
    "greened.kr": "녹색경제신문",
    "www.greened.kr": "녹색경제신문",
    "imaeil.com": "매일신문",
    "www.imaeil.com": "매일신문",
    "seoul.go.kr": "서울시",
    "www.seoul.go.kr": "서울시",
    "mediahub.seoul.go.kr": "서울시",
    "molit.go.kr": "국토교통부",
    "www.molit.go.kr": "국토교통부",
    "kosis.kr": "통계청",
    "www.kosis.kr": "통계청",
    "kbland.kr": "KB부동산",
    "hogangnono.com": "호갱노노",
}


def url_to_caption(url: str) -> str:
    """URL에서 도메인을 추출해 매체명 캡션 생성"""
    if not url:
        return ""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        # 정확 매칭 시도
        if host in DOMAIN_TO_MEDIA:
            return f"※ 자료: {DOMAIN_TO_MEDIA[host]}"
        # 서브도메인 무시하고 매칭
        for domain, media in DOMAIN_TO_MEDIA.items():
            if host.endswith(domain):
                return f"※ 자료: {media}"
        # 매핑 없으면 도메인 그대로
        return f"※ 자료: {host}"
    except Exception:
        return ""


def get_font(size: int, bold: bool = False):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size, index=2 if bold else 0)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def extract_palette(reference_path: str) -> dict:
    """AI 참조 이미지에서 색상 팔레트 추출.

    Returns:
        {
            'mat': (R, G, B) — 가장 밝은 톤 (매트 배경용),
            'line': (R, G, B) — 중간 톤 (내부 선용),
            'caption': (R, G, B) — 어두운 톤 (캡션 텍스트용),
        }
    """
    try:
        img = Image.open(reference_path).convert("RGB")
        # 작게 리사이즈해서 빠르게 처리
        img.thumbnail((150, 150))
        # 16색으로 양자화
        quantized = img.quantize(colors=16, method=2)
        palette = quantized.getpalette()[:48]  # 16색 * RGB

        # (R, G, B) 튜플 리스트로 변환
        colors = [(palette[i], palette[i+1], palette[i+2]) for i in range(0, 48, 3)]

        # 각 색상의 픽셀 수 카운트
        color_counts = quantized.getcolors()  # [(count, index), ...]
        if not color_counts:
            return None

        # 빈도순 정렬
        color_counts.sort(reverse=True)
        sorted_colors = [colors[idx] for _, idx in color_counts]

        # 명도(brightness) 계산: 0.299*R + 0.587*G + 0.114*B
        def brightness(c):
            return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]

        # 명도 순 정렬
        by_brightness = sorted(sorted_colors[:10], key=brightness, reverse=True)

        # 매트: 상위 50% 중 가장 빈도 높은 밝은 색
        bright_half = by_brightness[:5]
        mid = by_brightness[len(by_brightness)//2] if len(by_brightness) > 1 else by_brightness[0]
        dark = by_brightness[-1]

        # 매트는 너무 강하면 안 되니 살짝 라이트닝
        mat = bright_half[0]
        # 너무 어두우면 (60% 미만) 밝게 보정
        if brightness(mat) < 150:
            mat = tuple(min(255, int(c * 1.4 + 30)) for c in mat)

        # 라인은 중간 톤 (너무 밝으면 안 보이니까 살짝 어둡게)
        line = mid
        if brightness(line) > 180:
            line = tuple(int(c * 0.7) for c in line)

        # 캡션은 가장 어두운 톤
        caption = dark
        if brightness(caption) > 130:
            caption = tuple(int(c * 0.5) for c in caption)

        return {
            'mat': mat,
            'line': line,
            'caption': caption,
        }
    except Exception as e:
        print(f"⚠️ 색상 추출 실패: {e}", file=sys.stderr)
        return None


def fit_to_aspect(
    img: Image.Image,
    target_w: int,
    target_h: int,
    mode: str = "auto",
    mat_color: tuple = (255, 255, 255),
) -> Image.Image:
    """이미지를 16:9 비율로 맞춤.

    Args:
        mode: 'crop' (중앙 크롭, 잘림 가능),
              'letterbox' (매트 배경에 전체 보존),
              'auto' (비율 차이가 크면 letterbox, 작으면 crop)
        mat_color: letterbox 모드에서 사용할 배경색
    """
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    if mode == "auto":
        # 원본 비율과 타겟 비율 차이로 모드 자동 결정.
        # 2026-04-25 수정: Nano Banana 정사각형(1024x1024) 출력이 letterbox로 가서
        # 좌우에 시안 여백이 크게 뜨던 문제 해결. 임계값 0.08 → 0.50 으로 완화.
        # - 1:1 (33% 차이) → crop (위아래 17%씩 잘림, 가로 꽉 참)
        # - 4:3 (11% 차이) → crop
        # - 16:9 (0% 차이) → crop
        # - 9:16 같은 극단 세로 (66% 차이) → letterbox (정보 보존)
        ratio_diff = abs(src_ratio - target_ratio) / target_ratio
        mode = "letterbox" if ratio_diff > 0.50 else "crop"

    if mode == "crop":
        # 기존 크롭 방식
        if src_ratio > target_ratio:
            new_w = int(src_h * target_ratio)
            offset = (src_w - new_w) // 2
            img = img.crop((offset, 0, offset + new_w, src_h))
        else:
            new_h = int(src_w / target_ratio)
            offset = (src_h - new_h) // 2
            img = img.crop((0, offset, src_w, offset + new_h))
        return img.resize((target_w, target_h), Image.LANCZOS)

    else:  # letterbox
        # 비율 유지 + 매트 배경
        if src_ratio > target_ratio:
            # 가로가 더 길다 → 위아래에 매트
            new_w = target_w
            new_h = int(target_w / src_ratio)
        else:
            # 세로가 더 길다 → 좌우에 매트
            new_h = target_h
            new_w = int(target_h * src_ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (target_w, target_h), mat_color)
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y))
        return canvas


def add_warm_frame(photo: Image.Image, caption: str = "", palette: dict = None) -> Image.Image:
    """액자 프레임 추가 — palette가 주어지면 그 색상으로, 없으면 기본 베이지"""
    photo = photo.convert("RGB")
    pw, ph = photo.size

    # 색상 결정 (palette 우선, 없으면 기본값)
    mat_color = palette['mat'] if palette else FRAME_MAT_COLOR
    line_color = palette['line'] if palette else FRAME_INNER_LINE_COLOR
    caption_color = palette['caption'] if palette else FRAME_CAPTION_COLOR[:3]

    # 전체 캔버스 크기 (사진 + 외부 매트 + 하단 캡션 영역)
    total_w = pw + FRAME_OUTER_PADDING * 2
    total_h = ph + FRAME_OUTER_PADDING * 2 + FRAME_BOTTOM_EXTRA

    # 1. 매트 배경
    canvas = Image.new("RGBA", (total_w, total_h), mat_color + (255,))

    # 2. 외곽 둥근 모서리 마스킹
    mask = Image.new("L", (total_w, total_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        (0, 0, total_w, total_h),
        radius=FRAME_OUTER_RADIUS,
        fill=255,
    )
    canvas.putalpha(mask)

    # 3. 사진을 매트 위에 배치 (중앙)
    photo_x = FRAME_OUTER_PADDING
    photo_y = FRAME_OUTER_PADDING

    # 사진 그림자 (인셋 느낌)
    shadow = Image.new("RGBA", (pw + PHOTO_SHADOW_OFFSET * 2, ph + PHOTO_SHADOW_OFFSET * 2), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rectangle(
        (PHOTO_SHADOW_OFFSET, PHOTO_SHADOW_OFFSET, pw + PHOTO_SHADOW_OFFSET, ph + PHOTO_SHADOW_OFFSET),
        fill=PHOTO_SHADOW_COLOR,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))
    canvas.alpha_composite(shadow, (photo_x - PHOTO_SHADOW_OFFSET, photo_y - PHOTO_SHADOW_OFFSET))

    # 사진 붙이기
    canvas.paste(photo, (photo_x, photo_y))

    # 4. 내부 선 (사진 주변) — palette 색상 사용
    line_inset = FRAME_INNER_LINE_GAP
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(
        (
            photo_x - line_inset,
            photo_y - line_inset,
            photo_x + pw + line_inset - 1,
            photo_y + ph + line_inset - 1,
        ),
        outline=line_color,
        width=FRAME_INNER_LINE_WIDTH,
    )

    # 5. 캡션 (하단 매트 영역) — palette 캡션 색상 사용
    if caption:
        font = get_font(FRAME_CAPTION_FONT_SIZE, bold=False)
        bbox = draw.textbbox((0, 0), caption, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = (total_w - text_w) // 2
        text_y = total_h - FRAME_CAPTION_BOTTOM_OFFSET - FRAME_CAPTION_FONT_SIZE
        draw.text((text_x, text_y), caption, fill=caption_color + (220,), font=font)

    return canvas


def add_simple_frame(img: Image.Image, caption: str = "") -> Image.Image:
    """기존 방식 — 둥근 모서리 + 검은 반투명 캡션바"""
    img = img.convert("RGBA")
    w, h = img.size

    # 둥근 모서리
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, w, h), radius=CORNER_RADIUS, fill=255)
    img.putalpha(mask)

    # 테두리
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (0, 0, w - 1, h - 1),
        radius=CORNER_RADIUS,
        outline=BORDER_COLOR,
        width=BORDER_WIDTH,
    )
    img = Image.alpha_composite(img, overlay)

    # 캡션바
    if caption:
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        bar_top = h - CAPTION_HEIGHT
        draw.rounded_rectangle(
            (0, bar_top, w, h),
            radius=CORNER_RADIUS,
            fill=CAPTION_BG,
        )
        draw.rectangle((0, bar_top, w, bar_top + CORNER_RADIUS), fill=CAPTION_BG)

        font = get_font(CAPTION_FONT_SIZE, bold=True)
        text_y = bar_top + (CAPTION_HEIGHT - CAPTION_FONT_SIZE) // 2 - 2
        draw.text((CAPTION_PADDING, text_y), caption, fill=CAPTION_TEXT_COLOR, font=font)

        img = Image.alpha_composite(img, overlay)

    return img


def process(input_path: str, output_path: str, caption: str = "", style: str = "frame", reference_path: str = None, fit_mode: str = "auto", source_url: str = None) -> dict:
    """뉴스 사진을 후처리하여 일러스트와 어울리는 프레임으로 변환.

    Args:
        input_path: 원본 사진 경로
        output_path: 출력 경로
        caption: 출처 캡션 텍스트 (source_url이 있으면 자동 생성)
        style: 'frame' (액자) 또는 'simple' (둥근모서리+검은바)
        reference_path: AI 참조 이미지 경로 — 색상 팔레트 자동 추출용
        fit_mode: 'auto' (자동), 'crop' (강제 크롭), 'letterbox' (강제 매트)
        source_url: 출처 URL (있으면 도메인에서 매체명 자동 생성, caption보다 우선)
    """
    # source_url이 있으면 자동 매핑된 캡션 사용 (잘못 적힌 caption 무시)
    if source_url:
        auto_caption = url_to_caption(source_url)
        if auto_caption:
            caption = auto_caption

    src = Path(input_path)
    if not src.exists():
        return {"ok": False, "error": f"파일 없음: {input_path}"}

    # 1. palette 먼저 추출 (letterbox에서 매트 색상으로 사용)
    palette = None
    if reference_path and Path(reference_path).exists():
        palette = extract_palette(reference_path)

    mat_color_for_letterbox = palette["mat"] if palette else FRAME_MAT_COLOR

    # 2. 이미지 로드 + 비율 맞춤 (letterbox 시 매트 색상 사용)
    img = Image.open(src).convert("RGB")
    img = fit_to_aspect(img, OUTPUT_WIDTH, OUTPUT_HEIGHT, mode=fit_mode, mat_color=mat_color_for_letterbox)

    # 3. 프레임 처리
    if style == "frame":
        result_img = add_warm_frame(img, caption, palette)
    else:
        result_img = add_simple_frame(img, caption)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result_img.save(out, "PNG", optimize=True)

    return {
        "ok": True,
        "path": str(out),
        "width": result_img.size[0],
        "height": result_img.size[1],
        "style": style,
        "fit_mode": fit_mode,
        "palette": palette,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python3 news_image_processor.py <입력> <출력> [캡션] [--style frame|simple]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    caption = ""
    style = "frame"
    reference_path = None
    fit_mode = "auto"
    source_url = None

    args = sys.argv[3:]
    i = 0
    while i < len(args):
        if args[i] == "--style" and i + 1 < len(args):
            style = args[i + 1]
            i += 2
        elif args[i] == "--ref" and i + 1 < len(args):
            reference_path = args[i + 1]
            i += 2
        elif args[i] == "--fit" and i + 1 < len(args):
            fit_mode = args[i + 1]
            i += 2
        elif args[i] == "--source-url" and i + 1 < len(args):
            source_url = args[i + 1]
            i += 2
        else:
            caption = args[i]
            i += 1

    result = process(input_path, output_path, caption, style, reference_path, fit_mode, source_url)
    if result["ok"]:
        print(f"✅ 후처리 완료 ({result['style']}, fit={result['fit_mode']}): {result['path']} ({result['width']}x{result['height']})")
    else:
        print(f"❌ {result['error']}")
        sys.exit(1)
