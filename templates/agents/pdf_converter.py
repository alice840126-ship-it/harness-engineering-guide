#!/usr/bin/env python3
"""
PDF → Markdown 변환 에이전트

의사결정 트리:
1. 디지털 PDF (텍스트 추출 가능) → PyMuPDF4LLM (빠르고 정확)
2. CID 폰트 / 깨진 텍스트 → fitz raw + pdfplumber fallback
3. 스캔/이미지 PDF → OCR (macOS Vision framework)

사용법:
    python3 pdf_converter.py "input.pdf"
    python3 pdf_converter.py "input.pdf" "output.md"
    python3 pdf_converter.py "input.pdf" --save-obsidian
"""

import sys
import os
import re
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def detect_pdf_type(pdf_path: str) -> str:
    """PDF 유형 판별: digital / cid_broken / scanned"""
    import fitz
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    text_pages = 0
    garbled_pages = 0

    for page in doc:
        text = page.get_text()
        if len(text.strip()) > 50:
            text_pages += 1
            # CID 폰트 깨짐 감지: (cid:XX) 패턴이나 연속 특수문자
            cid_pattern = re.findall(r'\(cid:\d+\)', text)
            junk_ratio = sum(1 for c in text if ord(c) > 0xFFF0) / max(len(text), 1)
            if len(cid_pattern) > 5 or junk_ratio > 0.1:
                garbled_pages += 1

    doc.close()

    if text_pages < total_pages * 0.3:
        return "scanned"
    elif garbled_pages > total_pages * 0.3:
        return "cid_broken"
    else:
        return "digital"


def convert_digital(pdf_path: str) -> str:
    """디지털 PDF → Markdown (PyMuPDF4LLM)"""
    import pymupdf4llm
    md = pymupdf4llm.to_markdown(pdf_path)
    return _clean_markdown(md)


def convert_cid_broken(pdf_path: str) -> str:
    """CID 폰트 깨진 PDF → Markdown (pdfplumber fallback)"""
    import pdfplumber
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and len(text.strip()) > 10:
                lines.append(text)
            else:
                # pdfplumber도 실패하면 OCR fallback
                ocr_text = _ocr_page(pdf_path, i)
                if ocr_text:
                    lines.append(ocr_text)
            lines.append("")  # 페이지 구분

    return _clean_markdown("\n".join(lines))


def convert_scanned(pdf_path: str) -> str:
    """스캔/이미지 PDF → Markdown (macOS Vision OCR)"""
    import fitz
    doc = fitz.open(pdf_path)
    lines = []

    for i in range(len(doc)):
        ocr_text = _ocr_page(pdf_path, i)
        if ocr_text:
            lines.append(ocr_text)
        lines.append("")

    doc.close()
    return _clean_markdown("\n".join(lines))


def _ensure_ocr_binary():
    """macOS Vision OCR Swift 바이너리 컴파일 (최초 1회)"""
    binary = "/tmp/ocr_vision"
    if os.path.exists(binary):
        return binary

    swift_src = "/tmp/ocr_vision.swift"
    with open(swift_src, "w") as f:
        f.write("""import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count > 1 else { exit(1) }
guard let image = NSImage(contentsOfFile: args[1]),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { exit(1) }

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ko-KR", "en-US"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try! handler.perform([request])

guard let observations = request.results else { exit(0) }
for observation in observations {
    if let candidate = observation.topCandidates(1).first {
        print(candidate.string)
    }
}
""")
    subprocess.run(
        ["swiftc", swift_src, "-o", binary, "-framework", "Vision", "-framework", "AppKit"],
        capture_output=True, timeout=30
    )
    return binary if os.path.exists(binary) else None


def _ocr_page(pdf_path: str, page_num: int) -> str:
    """단일 페이지를 이미지로 렌더링 후 macOS Vision OCR"""
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    # 300 DPI로 렌더링
    mat = fitz.Matrix(300 / 72, 300 / 72)
    pix = page.get_pixmap(matrix=mat)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        pix.save(tmp.name)
        tmp_path = tmp.name

    doc.close()

    try:
        # macOS Vision framework (compiled Swift binary)
        ocr_bin = _ensure_ocr_binary()
        if ocr_bin:
            result = subprocess.run(
                [ocr_bin, tmp_path],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

        # fallback: tesseract if available
        result = subprocess.run(
            ["tesseract", tmp_path, "stdout", "-l", "kor+eng"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    finally:
        os.unlink(tmp_path)

    return ""


def _clean_markdown(md: str) -> str:
    """마크다운 정리: 과도한 빈줄 제거, 불필요한 이스케이프 정리"""
    # 3줄 이상 빈줄 → 2줄로
    md = re.sub(r'\n{4,}', '\n\n\n', md)
    # 페이지 넘김 표시 정리
    md = re.sub(r'-{3,}', '---', md)
    # 앞뒤 공백 정리
    md = md.strip()
    return md


def convert(pdf_path: str, output_path: str = None, save_obsidian: bool = False) -> dict:
    """메인 변환 함수.

    Returns:
        {"ok": True, "type": "digital|cid_broken|scanned",
         "markdown": "...", "output_path": "...", "pages": N}
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return {"ok": False, "error": f"파일 없음: {pdf_path}"}

    import fitz
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    # 1. PDF 유형 판별
    pdf_type = detect_pdf_type(pdf_path)

    # 2. 유형별 변환
    converters = {
        "digital": convert_digital,
        "cid_broken": convert_cid_broken,
        "scanned": convert_scanned,
    }
    markdown = converters[pdf_type](pdf_path)

    if not markdown or len(markdown.strip()) < 50:
        return {"ok": False, "error": "변환 결과가 너무 짧습니다. PDF 내용을 확인해주세요."}

    # 3. 저장
    if output_path:
        out = Path(output_path)
    elif save_obsidian:
        from obsidian_writer import save_note
        vault = os.path.expanduser(
            "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수"
        )
        stem = pdf_file.stem
        out = Path(vault) / f"{stem}.md"
        # obsidian_writer의 build_yaml 사용
        from obsidian_writer import build_yaml
        yaml = build_yaml("note", tags=["PDF변환", stem])
        markdown = yaml + "\n" + markdown
    else:
        out = pdf_file.with_suffix(".md")

    out.write_text(markdown, encoding="utf-8")

    return {
        "ok": True,
        "type": pdf_type,
        "markdown": markdown,
        "output_path": str(out),
        "pages": total_pages,
        "chars": len(markdown),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 pdf_converter.py <PDF파일> [출력파일.md] [--save-obsidian]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_path = None
    save_obsidian = False

    for arg in sys.argv[2:]:
        if arg == "--save-obsidian":
            save_obsidian = True
        else:
            output_path = arg

    result = convert(pdf_path, output_path, save_obsidian)

    if result["ok"]:
        print(f"변환 완료! ({result['type']})")
        print(f"  페이지: {result['pages']}p")
        print(f"  글자수: {result['chars']:,}자")
        print(f"  저장: {result['output_path']}")
    else:
        print(f"실패: {result['error']}")
        sys.exit(1)
