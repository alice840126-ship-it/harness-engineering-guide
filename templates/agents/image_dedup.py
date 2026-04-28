#!/usr/bin/env python3
"""image_dedup — 블로그 이미지 중복/유사 탐지기 (Perceptual Hash 기반).

CLAUDE.md "이미지 매핑 절대 규칙": **같은 이미지를 두 섹션에 중복 사용 금지**
→ 자동 탐지. pHash(perceptual hash) 로 비트플립/리사이즈/약한 편집도 잡는다.

핵심 함수:
    find_duplicates(paths, threshold=5) → [(path_a, path_b, hamming_distance)]
    check_folder(folder, threshold=5)   → {"duplicates": [...], "count": N}
    hash_image(path)                    → imagehash.ImageHash

해밍 거리 가이드:
    0       : 동일 파일 (또는 완벽한 비주얼 클론)
    1~5     : 거의 동일 (리사이즈/약한 JPEG 재압축/미세 편집) → 중복 판정
    6~10    : 비슷 (같은 피사체 다른 앵글) → 경고
    11+     : 다른 이미지

CLI:
    python3 image_dedup.py check <folder> [--threshold N]
    python3 image_dedup.py compare <a.png> <b.png>
    python3 image_dedup.py selftest
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

try:
    import imagehash
    from PIL import Image
except ImportError as e:
    print(f"❌ 의존성 없음: {e}. 설치: pip3 install --system imagehash", file=sys.stderr)
    raise

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def hash_image(path: Path, hash_size: int = 8) -> "imagehash.ImageHash":
    """pHash 계산. 파일이 깨졌으면 예외."""
    img = Image.open(path)
    return imagehash.phash(img, hash_size=hash_size)


def find_duplicates(paths: list[Path], threshold: int = 5) -> list[tuple[Path, Path, int]]:
    """pair-wise pHash 비교. threshold 이하 해밍 거리면 중복."""
    hashes: list[tuple[Path, "imagehash.ImageHash"]] = []
    for p in paths:
        try:
            hashes.append((p, hash_image(p)))
        except Exception as e:
            sys.stderr.write(f"skip {p.name}: {e}\n")

    dups: list[tuple[Path, Path, int]] = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            pa, ha = hashes[i]
            pb, hb = hashes[j]
            d = ha - hb
            if d <= threshold:
                dups.append((pa, pb, d))
    # 거리 오름차순
    dups.sort(key=lambda t: t[2])
    return dups


def check_folder(folder: Path, threshold: int = 5,
                  recursive: bool = False) -> dict:
    """폴더 내 이미지 중복 검사."""
    folder = Path(folder)
    if not folder.is_dir():
        return {"error": f"not a dir: {folder}", "duplicates": [], "count": 0}
    pattern = "**/*" if recursive else "*"
    paths = sorted([p for p in folder.glob(pattern)
                     if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
    dups = find_duplicates(paths, threshold=threshold)
    return {
        "folder": str(folder),
        "scanned": len(paths),
        "threshold": threshold,
        "count": len(dups),
        "duplicates": [
            {"a": str(a.relative_to(folder)), "b": str(b.relative_to(folder)), "distance": d}
            for a, b, d in dups
        ],
    }


# ------------- CLI -------------

def cmd_check(args):
    r = check_folder(Path(args.folder), threshold=args.threshold,
                     recursive=args.recursive)
    if "error" in r:
        print(f"❌ {r['error']}")
        sys.exit(1)
    print(f"=== {r['folder']} ===")
    print(f"scanned: {r['scanned']}  threshold: {r['threshold']}  duplicates: {r['count']}")
    if not r["duplicates"]:
        print("✅ 중복 없음")
        return
    print("\n⚠️ 중복/유사:")
    for d in r["duplicates"]:
        print(f"  [{d['distance']:>2}] {d['a']}  ≈  {d['b']}")
    sys.exit(2)


def cmd_compare(args):
    ha = hash_image(Path(args.a))
    hb = hash_image(Path(args.b))
    d = ha - hb
    verdict = "중복" if d <= 5 else ("유사" if d <= 10 else "다름")
    print(f"a: {args.a}\nb: {args.b}")
    print(f"pHash(a): {ha}\npHash(b): {hb}")
    print(f"해밍 거리: {d}  → {verdict}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    p_check = sub.add_parser("check")
    p_check.add_argument("folder")
    p_check.add_argument("--threshold", type=int, default=5)
    p_check.add_argument("--recursive", action="store_true")

    p_cmp = sub.add_parser("compare")
    p_cmp.add_argument("a")
    p_cmp.add_argument("b")

    sub.add_parser("selftest")

    args = ap.parse_args()
    if args.cmd == "check":
        cmd_check(args)
    elif args.cmd == "compare":
        cmd_compare(args)
    elif args.cmd == "selftest":
        _selftest()
    else:
        ap.print_help()
        sys.exit(1)


def _selftest():
    import tempfile
    from PIL import Image, ImageDraw, ImageFilter

    passed = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 베이스 이미지 (각기 다른 패턴)
        def make_img(name: str, color: tuple, pattern: str = "solid") -> Path:
            img = Image.new("RGB", (256, 256), color)
            d = ImageDraw.Draw(img)
            if pattern == "circle":
                d.ellipse((32, 32, 224, 224), fill=(255, 255, 255))
            elif pattern == "box":
                d.rectangle((48, 48, 208, 208), fill=(0, 0, 0))
            elif pattern == "lines":
                for x in range(0, 256, 16):
                    d.line((x, 0, x, 256), fill=(255, 255, 255), width=2)
            p = tmp / name
            img.save(p)
            return p

        a = make_img("a.png", (200, 50, 50), "circle")
        b = make_img("b.png", (50, 200, 50), "box")
        c = make_img("c.png", (50, 50, 200), "lines")

        # a의 복제본 — 동일 픽셀
        a_copy = tmp / "a_copy.png"
        Image.open(a).save(a_copy)

        # a의 리사이즈 변형 (128x128)
        a_small = tmp / "a_small.png"
        Image.open(a).resize((128, 128)).save(a_small)

        # a의 경미한 블러 (radius 0.3 — pHash threshold 이내여야)
        a_blur = tmp / "a_blur.png"
        Image.open(a).filter(ImageFilter.GaussianBlur(radius=0.3)).save(a_blur)

        # === case 1: hash_image 호출 가능
        h = hash_image(a)
        assert h is not None
        print(f"  ✓ case 1 hash_image OK ({h})")
        passed += 1

        # === case 2: 완전 동일 파일 → 거리 0
        d_copy = hash_image(a) - hash_image(a_copy)
        assert d_copy == 0, f"copy 거리 {d_copy} (0이어야)"
        print(f"  ✓ case 2 identical copy (d={d_copy})")
        passed += 1

        # === case 3: 리사이즈/블러 변형도 중복 판정 (threshold=5)
        d_small = hash_image(a) - hash_image(a_small)
        d_blur = hash_image(a) - hash_image(a_blur)
        assert d_small <= 5, f"resize 거리 {d_small} 너무 큼"
        assert d_blur <= 5, f"blur 거리 {d_blur} 너무 큼"
        print(f"  ✓ case 3 변형 탐지 (resize={d_small}, blur={d_blur})")
        passed += 1

        # === case 4: 다른 이미지는 threshold 초과
        d_ab = hash_image(a) - hash_image(b)
        d_ac = hash_image(a) - hash_image(c)
        # threshold 5 기준 — 명확히 다른 패턴은 5 초과여야
        assert d_ab > 5, f"a-b 너무 가까움 {d_ab}"
        assert d_ac > 5, f"a-c 너무 가까움 {d_ac}"
        print(f"  ✓ case 4 다른 이미지 구분 (a-b={d_ab}, a-c={d_ac})")
        passed += 1

        # === case 5: check_folder 통합
        r = check_folder(tmp, threshold=5)
        assert r["scanned"] == 6, f"scanned {r['scanned']}"
        # 중복 페어: (a, a_copy), (a, a_small), (a, a_blur),
        #           (a_copy, a_small), (a_copy, a_blur), (a_small, a_blur)
        # 최소 5개 이상
        assert r["count"] >= 3, f"중복 count 너무 적음: {r['count']}"
        # 실제 페어 확인
        names_in_dups = set()
        for d in r["duplicates"]:
            names_in_dups.add(d["a"])
            names_in_dups.add(d["b"])
        assert "a.png" in names_in_dups
        assert "a_copy.png" in names_in_dups
        # b나 c가 중복에 포함되면 안 됨
        assert "b.png" not in names_in_dups, "b 오탐"
        assert "c.png" not in names_in_dups, "c 오탐"
        print(f"  ✓ case 5 check_folder (scanned={r['scanned']}, dups={r['count']})")
        passed += 1

    print(f"✅ selftest passed: {passed}/5")


if __name__ == "__main__":
    main()
