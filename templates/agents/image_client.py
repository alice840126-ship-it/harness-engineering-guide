"""image_client — 이미지 생성 API 호출 SPoE (Single Point of Entry).

모든 자동화에서 Gemini/Imagen 이미지 생성을 호출할 때 이 모듈을 경유한다.
모델 우선순위, API key 로딩, fallback, base64 디코드, 파일 저장을 한 곳에 통일.
컨셉 레이어(프롬프트 설계, 스타일 선택)는 호출측 책임 — 이 모듈은 transport만.

정책 (2026-04-23):
1. Primary: gemini-2.5-flash-image (Nano Banana) — 한글 렌더링·편집 일관성 우위
2. Fallback: imagen-4.0-ultra-generate-001 — Nano Banana 빈 응답/실패 시 백업

사용법:
    from image_client import generate
    result = generate(prompt="A cat on a roof at sunset", out_path="/tmp/cat.png", aspect_ratio="16:9")
    # result = {"ok": True, "model": "nano-banana", "path": "/tmp/cat.png"}

호출측:
    - blog-image.md (블로그 섹션 이미지)
    - image-generator.md (범용 30 스타일 이미지)
    - news_thesis_bamboo.py (뉴스레터 섬네일, Claymorphism 강제)
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    import ssl
    _HAS_REQUESTS = False


PRIMARY_MODEL = "gemini-2.5-flash-image"  # Nano Banana
FALLBACK_MODEL = "imagen-4.0-ultra-generate-001"
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
ENV_PATH = Path.home() / ".claude" / ".env"


def _load_api_key() -> Optional[str]:
    """~/.claude/.env에서 GEMINI_API_KEY 로드."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _post_json(url: str, payload: dict, timeout: int = 120) -> Optional[dict]:
    """REST POST. 에러면 None. requests 우선, 없으면 urllib + unverified SSL fallback."""
    if _HAS_REQUESTS:
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            return None
    # urllib fallback — macOS Python은 종종 인증서 누락 → unverified 컨텍스트
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return None


def _try_nano_banana(api_key: str, prompt: str, out_path: Path) -> bool:
    """Primary: Nano Banana (gemini-2.5-flash-image:generateContent). 성공 시 True."""
    url = f"{API_BASE}/{PRIMARY_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    data = _post_json(url, payload)
    if not data:
        return False
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            out_path.write_bytes(base64.b64decode(inline["data"]))
            return out_path.stat().st_size > 1000
    return False


def _try_imagen_ultra(
    api_key: str, prompt: str, out_path: Path, aspect_ratio: str
) -> bool:
    """Fallback: Imagen 4 Ultra (imagen-4.0-ultra-generate-001:predict). 성공 시 True."""
    url = f"{API_BASE}/{FALLBACK_MODEL}:predict?key={api_key}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
            "personGeneration": "allow_adult",
            "safetySetting": "block_low_and_above",
        },
    }
    data = _post_json(url, payload)
    if not data:
        return False
    preds = data.get("predictions") or []
    if not preds:
        return False
    b64 = preds[0].get("bytesBase64Encoded")
    if not b64:
        return False
    out_path.write_bytes(base64.b64decode(b64))
    return out_path.stat().st_size > 1000


def generate(
    prompt: str,
    out_path: str | Path,
    aspect_ratio: str = "16:9",
) -> dict:
    """이미지 생성 SPoE. Nano Banana 시도 → 실패 시 Imagen Ultra fallback.

    Args:
        prompt: 영어 프롬프트 (호출측에서 스타일 프리픽스 포함해 완성본으로 전달)
        out_path: 저장 경로 (str or Path)
        aspect_ratio: "1:1" | "3:4" | "4:3" | "9:16" | "16:9" (Imagen fallback 시에만 적용;
                      Nano Banana는 프롬프트에 내재시켜야 함)

    Returns:
        {"ok": bool, "model": "nano-banana"|"imagen-ultra"|None,
         "path": str, "error": str|None}
    """
    result = {"ok": False, "model": None, "path": str(out_path), "error": None}

    api_key = _load_api_key()
    if not api_key:
        result["error"] = "GEMINI_API_KEY not found in ~/.claude/.env"
        return result

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Primary
    if _try_nano_banana(api_key, prompt, out):
        result.update(ok=True, model="nano-banana")
        return result

    # Fallback
    if _try_imagen_ultra(api_key, prompt, out, aspect_ratio):
        result.update(ok=True, model="imagen-ultra")
        return result

    result["error"] = "Both Nano Banana and Imagen Ultra failed (empty response or API error)"
    return result


if __name__ == "__main__":
    # Selftest
    import sys
    import tempfile

    test_prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "Minimalist line art of a cat on a roof at sunset, warm palette, no text"
    )
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name
    r = generate(test_prompt, tmp_path)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if r["ok"]:
        print(f"✅ Image saved to {tmp_path} ({Path(tmp_path).stat().st_size} bytes)")
    else:
        sys.exit(1)
