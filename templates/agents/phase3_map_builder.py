#!/usr/bin/env python3
"""
Phase 3 — 작가의 사고 지도 노트 작성 (Opus).

입력: aggregated_patterns.json (Phase 2 결과)
출력: 00_사고 지도/{작가명}.md

사용법: python3 phase3_map_builder.py <patterns.json> <출력경로.md> [blog_id]
작가명은 출력 파일명에서 자동 추출됨.
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from datetime import date


MAP_DIR = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/류웅수/해상도 프로젝트/00_사고 지도"
# CLI 인자 필수. 아래 기본값은 사용되지 않음 (brain_stealer가 항상 인자 전달)
INPUT_PATH = None
OUTPUT_PATH = MAP_DIR / "output.md"


def call_llm(prompt: str, model: str = "opus", timeout: int = 900) -> tuple:
    """Claude CLI 호출. (stdout, err_msg) 반환. err_msg 있으면 실패."""
    try:
        result = subprocess.run(
            ["claude", "--print", "--model", model, "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return "", f"returncode={result.returncode} stderr={result.stderr[:300]}"
        return result.stdout.strip(), ""
    except subprocess.TimeoutExpired:
        return "", "timeout"
    except Exception as e:
        return "", f"exception={e}"


def build_map(patterns: dict, author_name: str = "작가", model: str = "opus") -> tuple:
    """Opus로 최종 사고 지도 작성. (content, err_msg) 반환."""

    synth = patterns.get('opus_synthesis')
    agg = patterns.get('auto_aggregation', {})

    if not synth:
        return "", "Phase 2 synth 없음 — Phase 2를 먼저 재실행하세요"

    # 주제 TOP 4 동적
    top_topics = sorted(agg.get('topics', {}).items(), key=lambda x: -x[1])[:4]
    topic_str = "/".join([t[0] for t in top_topics]) if top_topics else "주요 주제들"

    prompt = f"""당신은 작가 사고 구조 분석가다. 파일 시스템 접근 권한 없음. 도구 호출 없음. **오직 마크다운 본문 텍스트만 생성해서 반환한다.**

대상 작가: {author_name} ({agg.get('total_notes', 0)}개 자료 분석 기반)

당신의 임무: 아래 데이터를 바탕으로 **마크다운 본문 자체**를 응답한다. "작성했다", "저장했다", "완료했다" 같은 메타 보고 금지. 본문 그대로만 출력.

**엄격한 출력 규칙 (위반 시 실패):**
1. 응답 첫 글자는 반드시 "# " (H1 마크다운)
2. 응답 마지막 글자는 본문의 마지막 문장 (보고·요약·마무리 메타 멘트 금지)
3. 최소 분량 5,000자 (한국어 공백 포함)
4. "옵시디언" / "저장" / "파일" / "노트를 만들었" / "작성 완료" 같은 메타 단어 금지
5. 본문 전체를 한 번에 출력 (생략·요약·"이런 식으로 계속됩니다" 금지)

**필수 섹션 7개 (모두 H2로):**
1. ## 1. 작가 정체성 — 한 문장 핵심 + 풀어쓴 설명 (300자+)
2. ## 2. 핵심 멘탈모델 TOP 30 — 각 이름 + 2-3줄 설명 + 작가 원문 표현 (표로)
3. ## 3. 재정의 패턴 10가지 — 각 패턴 이름 + 설명 + 원문 인용 2-3개
4. ## 4. 독특한 어휘 사전 — 반복 사용 용어 20-30개 (표로)
5. ## 5. 작가의 사고 알고리즘 — 관찰→재정의→통찰 흐름
6. ## 6. 주제별 관점 — {topic_str}
7. ## 7. 형님 실천 가이드 5 — 사고 훈련법

**스타일:**
- 명료한 한국어. 합쇼체 또는 평어체 일관
- 작가 원문 인용을 풍부하게 > blockquote로
- 표 자유 사용
- 코드블록 금지

== Phase 2 합성 데이터 ==

{json.dumps(synth, ensure_ascii=False, indent=2)}

== 자동 집계 ==

총 글: {agg.get('total_notes', 0)}
주제 분포: {json.dumps(agg.get('topics', {}), ensure_ascii=False)}
감성 분포: {json.dumps(agg.get('sentiments', {}), ensure_ascii=False)}
재정의 문장 총수: {agg.get('redefinitions_count', 0)}

== 원문 샘플 (최대 활용) ==

[통찰 한 줄 30개]
{json.dumps(agg.get('insights_sample', [])[:30], ensure_ascii=False, indent=1)}

[재정의 문장 30개]
{json.dumps(agg.get('redefinitions', [])[:30], ensure_ascii=False, indent=1)}

---

**지금 응답 시작. 첫 글자는 "# ". 메타 멘트 없이 본문 5,000자 이상 바로.**"""

    print(f"{model}에 사고 지도 작성 요청 (10-15분 소요)...", file=sys.stderr)
    response, err = call_llm(prompt, model=model)

    if err or not response:
        return "", err or "빈 응답"

    # ======== 품질 검증 ========
    # 1. 최소 길이
    if len(response) < 3000:
        return "", f"응답이 너무 짧음 ({len(response)}자, 최소 3000자 필요)"

    # 2. 메타 응답 감지 (Opus가 "저장했다"고 거짓말하는 경우)
    first_500 = response[:500]
    meta_phrases = ["옵시디언에 저장", "저장 완료", "파일을 만들", "파일을 생성",
                    "노트를 만들", "작성 완료", "작성했다", "분량으로 정리했다"]
    for phrase in meta_phrases:
        if phrase in first_500:
            return "", f"메타 응답 감지 ('{phrase}' 포함). 본문이 아님"

    # 3. 첫 글자 "# " 검증
    if not response.lstrip().startswith("# "):
        return "", f"응답이 '# '로 시작하지 않음. 시작: {response[:100]!r}"

    return response, ""


def main():
    # CLI 인자: <input> <output> [blog_id] [--model 모델]
    model = "opus"
    if '--model' in sys.argv:
        idx = sys.argv.index('--model')
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]
    positional = [a for i, a in enumerate(sys.argv[1:]) if a != '--model' and sys.argv[i] != '--model']

    if len(positional) < 2:
        print("사용법: python3 phase3_map_builder.py <patterns.json> <output.md> [blog_id] [--model 모델]", file=sys.stderr)
        sys.exit(1)
    input_path = Path(positional[0])
    output_path = Path(positional[1])

    if not input_path.exists():
        print(f"입력 파일 없음: {input_path}", file=sys.stderr)
        sys.exit(1)

    # author_name은 output_path 파일명에서 추출 (예: "메르의 세상읽기.md" → "메르의 세상읽기")
    author_name = output_path.stem
    print(f"=== Phase 3 시작 ({author_name}) ===", file=sys.stderr)
    print(f"모델: {model}", file=sys.stderr)

    with open(input_path, 'r', encoding='utf-8') as f:
        patterns = json.load(f)

    print(f"입력 로드 완료", file=sys.stderr)

    # 사고 지도 작성
    content, err = build_map(patterns, author_name=author_name, model=model)

    if not content:
        print(f"지도 작성 실패: {err}", file=sys.stderr)
        sys.exit(1)

    # 헤더 추가 (frontmatter — CLAUDE.md 표준 5필드 + 원본 메타)
    today = date.today().isoformat()
    blog_id = positional[2] if len(positional) >= 3 else ""
    total = patterns.get('auto_aggregation', {}).get('total_notes', 0)
    header = f"""---
type: analysis
author:
  - "[[류웅수]]"
date created: {today}
date modified: {today}
tags: [뇌훔치기, {author_name}, 사고지도, 메타인지]
original_author: {author_name}
source_blog: {blog_id}
total_notes_analyzed: {total}
generated_by: claude-opus
---

"""

    full = header + content

    output_path.write_text(full, encoding='utf-8')

    print(f"\n저장 완료: {output_path}", file=sys.stderr)
    print(f"분량: {len(full)}자", file=sys.stderr)
    print(f"\n=== Phase 3 완료 ===", file=sys.stderr)


if __name__ == "__main__":
    main()
