#!/usr/bin/env python3
"""
Phase 2 — 추출 데이터 집계 + Opus 패턴 분류.

입력: extracted_notes.json (Phase 1 결과)
출력: aggregated_patterns.json + draft_thoughts.md

작업:
    1. 자동 집계 (Python):
       - 멘탈모델 빈도 (TOP 50)
       - 재정의 문장 전체 수집
       - 독특한 표현 빈도 (TOP 100)
       - 주제별 분류 + 대표작
       - 키워드 빈도
       - 감성 분포
       - 시기별 변화 (logNo 기준)
    2. Opus 호출 (1회):
       - 멘탈모델 → 핵심 30개 통합·정제
       - 재정의 문장 → 패턴 10가지 분류
       - 독특한 어휘 → 사전 30개
       - 사고의 구조 → 작가의 알고리즘 추출
"""

import sys
import os
import re
import json
import subprocess
from pathlib import Path
from collections import Counter, defaultdict


# CLI 인자 필수. 아래 기본값은 사용되지 않음 (brain_stealer가 항상 인자 전달)
INPUT_PATH = None
OUTPUT_PATTERNS = None
OUTPUT_DRAFT = None


def auto_aggregate(notes: dict) -> dict:
    """자동 집계 (Python만 사용)"""
    print(f"자동 집계 시작: {len(notes)}개 글", file=sys.stderr)

    mental_models = Counter()
    redefinitions = []  # (log_no, title, sentence)
    unique_phrases = Counter()
    keywords = Counter()
    topics = Counter()
    sentiments = Counter()
    insights = []  # (log_no, title, insight)

    by_topic = defaultdict(list)  # 주제별 글 모음

    for log_no, data in notes.items():
        title = data.get('title', '')

        # 멘탈모델
        for m in data.get('멘탈모델', []) or []:
            if m and isinstance(m, str):
                mental_models[m.strip()] += 1

        # 재정의 문장
        rd = data.get('재정의_문장', '')
        if rd and isinstance(rd, str) and len(rd) > 5:
            redefinitions.append({
                'log_no': log_no,
                'title': title,
                'sentence': rd.strip(),
            })

        # 독특한 표현
        for p in data.get('독특한_표현', []) or []:
            if p and isinstance(p, str):
                unique_phrases[p.strip()] += 1

        # 키워드
        for k in data.get('키워드', []) or []:
            if k and isinstance(k, str):
                keywords[k.strip()] += 1

        # 주제분류
        topic = data.get('주제분류', '기타')
        if isinstance(topic, str):
            topics[topic] += 1
            by_topic[topic].append({
                'log_no': log_no,
                'title': title,
                'insight': data.get('통찰_한줄', ''),
            })

        # 감성
        sentiment = data.get('감성', '중립')
        if isinstance(sentiment, str):
            sentiments[sentiment] += 1

        # 통찰 한줄
        insight = data.get('통찰_한줄', '')
        if insight and isinstance(insight, str) and len(insight) > 5:
            insights.append({
                'log_no': log_no,
                'title': title,
                'insight': insight.strip(),
            })

    # 주제별 대표작 (5개씩)
    topic_top = {topic: items[:5] for topic, items in by_topic.items()}

    return {
        'total_notes': len(notes),
        'mental_models_top': mental_models.most_common(100),
        'mental_models_unique': len(mental_models),
        'redefinitions': redefinitions,
        'redefinitions_count': len(redefinitions),
        'unique_phrases_top': unique_phrases.most_common(150),
        'unique_phrases_total': len(unique_phrases),
        'keywords_top': keywords.most_common(80),
        'topics': dict(topics),
        'topic_examples': topic_top,
        'sentiments': dict(sentiments),
        'insights_count': len(insights),
        'insights_sample': insights[:30],
    }


def call_llm(prompt: str, model: str = "opus", timeout: int = 600) -> str:
    """Claude CLI 호출"""
    try:
        result = subprocess.run(
            ["claude", "--print", "--model", model, "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            print(f"  {model} 호출 실패: {result.stderr[:300]}", file=sys.stderr)
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"  {model} 타임아웃", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"  {model} 예외: {e}", file=sys.stderr)
        return ""


def opus_synthesize(agg: dict, author_name: str = "작가", model: str = "opus") -> dict:
    """Opus로 패턴 합성·분류"""
    print(f"Opus 합성 시작...", file=sys.stderr)

    # 합성에 보낼 데이터 준비 (양 줄이기)
    top_models = agg['mental_models_top'][:80]
    top_phrases = agg['unique_phrases_top'][:80]
    sample_redefs = agg['redefinitions'][:60]
    sample_insights = agg['insights_sample'][:30]

    # f-string 밖에서 미리 직렬화 (f-string 안 {{}} escape 회피)
    top_models_json = json.dumps(top_models, ensure_ascii=False, indent=1)
    top_phrases_json = json.dumps(top_phrases, ensure_ascii=False, indent=1)
    redefs_simplified = [{'제목': r['title'], '문장': r['sentence']} for r in sample_redefs]
    redefs_json = json.dumps(redefs_simplified, ensure_ascii=False, indent=1)
    insights_simplified = [{'제목': i['title'], '통찰': i['insight']} for i in sample_insights]
    insights_json = json.dumps(insights_simplified, ensure_ascii=False, indent=1)
    topics_json = json.dumps(agg['topics'], ensure_ascii=False)
    sentiments_json = json.dumps(agg['sentiments'], ensure_ascii=False)

    # 주제 동적 생성 (TOP 4)
    top_topics = sorted(agg.get('topics', {}).items(), key=lambda x: -x[1])[:4]
    topic_names = [t[0] for t in top_topics] if top_topics else ["주제1", "주제2", "주제3", "주제4"]
    topic_schema_lines = ",\n    ".join([f'"{t}": "{t}을 보는 관점 한 문단"' for t in topic_names])

    prompt = f"""{author_name} 블로그 {agg['total_notes']}개 글에서 추출한 데이터다. 작가의 사고 구조를 분석해서 다음 4가지를 합성해라.

응답은 JSON 객체 1개. 코드블록 금지. 설명 금지.

스키마:
{{
  "핵심_멘탈모델_30": [
    {{"이름": "string", "설명": "2-3줄 설명", "출현빈도": int, "관련_원본_표현": ["원본 멘탈모델 표현 2-3개"]}}
  ],
  "재정의_패턴_10": [
    {{"패턴_이름": "string", "설명": "2-3줄", "예시": ["원문 인용 2-3개"]}}
  ],
  "독특한_어휘_사전_30": [
    {{"어휘": "string", "의미": "1-2줄 의미 추정", "출현빈도": int}}
  ],
  "사고의_구조": {{
    "관찰_방식": "작가가 현상을 처음 어떻게 보는가 (3-5줄)",
    "재정의_방식": "관찰 후 어떻게 범주를 다시 그리는가 (3-5줄)",
    "통찰_도출_방식": "재정의에서 어떻게 결론을 끌어내는가 (3-5줄)",
    "전형적_글_구조": "한 글의 전형적 흐름을 단계로 (5-7단계)"
  }},
  "작가_정체성": "이 작가가 어떤 사람인지 5-7줄 평가 (단순 직업 아니라 사고 방식 측면)",
  "주제_지도": {{
    {topic_schema_lines}
  }}
}}

== 데이터 ==

[멘탈모델 TOP 80 (이름:빈도)]
{top_models_json}

[독특한 표현 TOP 80 (표현:빈도)]
{top_phrases_json}

[재정의 문장 샘플 60개]
{redefs_json}

[통찰 한 줄 샘플 30개]
{insights_json}

[주제 분포]
{topics_json}

[감성 분포]
{sentiments_json}

총 글: {agg['total_notes']}
재정의 문장 총 수: {agg['redefinitions_count']}
독특 표현 총 수: {agg['unique_phrases_total']}

다시: JSON 객체 1개만 출력. 다른 텍스트 금지."""

    response = call_llm(prompt, model=model)
    if not response:
        return None

    # JSON 파싱
    response = re.sub(r'^```(?:json)?\s*', '', response.strip())
    response = re.sub(r'\s*```$', '', response.strip())

    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"  JSON 파싱 실패: {e}", file=sys.stderr)
        # 디버그
        debug = BASE_DIR / "phase2_opus_response_debug.txt"
        debug.write_text(response[:5000], encoding='utf-8')
        print(f"  디버그 응답 저장: {debug}", file=sys.stderr)
        return None


def write_draft(agg: dict, synth: dict, author_name: str = "작가", draft_path: Path = None) -> Path:
    """draft_thoughts.md 생성 (Phase 3 입력)"""
    if draft_path is None:
        raise ValueError("draft_path 필수")
    lines = []
    lines.append(f"# {author_name} 작가 사고 분석 - Draft (Phase 2)\n")
    lines.append(f"\n총 분석: {agg['total_notes']}개 글\n\n")

    # 자동 집계
    lines.append("## 자동 집계\n\n")
    lines.append(f"- 멘탈모델 unique: {agg['mental_models_unique']}개\n")
    lines.append(f"- 재정의 문장: {agg['redefinitions_count']}개\n")
    lines.append(f"- 독특 표현 unique: {agg['unique_phrases_total']}개\n")
    lines.append(f"- 통찰 한 줄: {agg['insights_count']}개\n\n")

    lines.append("### 주제 분포\n\n")
    for t, c in sorted(agg['topics'].items(), key=lambda x: -x[1]):
        lines.append(f"- {t}: {c}\n")
    lines.append("\n")

    lines.append("### 감성 분포\n\n")
    for s, c in sorted(agg['sentiments'].items(), key=lambda x: -x[1]):
        lines.append(f"- {s}: {c}\n")
    lines.append("\n")

    # Opus 합성 결과
    if synth:
        lines.append("## Opus 합성 결과\n\n")
        lines.append("```json\n")
        lines.append(json.dumps(synth, ensure_ascii=False, indent=2))
        lines.append("\n```\n")

    draft_path.write_text("".join(lines), encoding='utf-8')
    return draft_path


def main():
    # CLI 인자: <input> <output> [--author 작가명] [--model 모델]
    author_name = "작가"
    model = "opus"
    args = []
    skip_next = False
    for i, a in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if a == '--author' and i + 2 <= len(sys.argv) - 1:
            author_name = sys.argv[i + 2]
            skip_next = True
            continue
        if a == '--model' and i + 2 <= len(sys.argv) - 1:
            model = sys.argv[i + 2]
            skip_next = True
            continue
        args.append(a)

    if len(args) < 2:
        print("사용법: python3 phase2_aggregator.py <extracted.json> <patterns.json> [--author 작가명]", file=sys.stderr)
        sys.exit(1)
    input_path = Path(args[0])
    output_path = Path(args[1])
    draft_path = output_path.parent / "draft_thoughts.md"

    if not input_path.exists():
        print(f"입력 파일 없음: {input_path}")
        sys.exit(1)

    print(f"=== Phase 2 시작 ({author_name}) ===", file=sys.stderr)
    print(f"입력: {input_path}", file=sys.stderr)
    print(f"모델: {model}", file=sys.stderr)

    with open(input_path, 'r', encoding='utf-8') as f:
        notes = json.load(f)
    print(f"로드: {len(notes)}개 노트", file=sys.stderr)

    # 1. 자동 집계
    agg = auto_aggregate(notes)
    print(f"\n자동 집계 완료", file=sys.stderr)
    print(f"  - 멘탈모델 unique: {agg['mental_models_unique']}", file=sys.stderr)
    print(f"  - 재정의 문장: {agg['redefinitions_count']}", file=sys.stderr)
    print(f"  - 독특 표현 unique: {agg['unique_phrases_total']}", file=sys.stderr)

    # 2. LLM 합성
    print(f"\n{model} 합성 시작 (5-10분 소요)...", file=sys.stderr)
    synth = opus_synthesize(agg, author_name=author_name, model=model)
    if not synth:
        print(f"{model} 합성 실패. Phase 2 중단 (exit 1).", file=sys.stderr)
        sys.exit(1)
    print(f"{model} 합성 완료", file=sys.stderr)

    # 3. 결과 저장
    output = {
        'auto_aggregation': agg,
        'opus_synthesis': synth,
        'author_name': author_name,
    }
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"\n저장: {output_path}", file=sys.stderr)

    # 4. Draft 노트
    dp = write_draft(agg, synth, author_name=author_name, draft_path=draft_path)
    print(f"Draft: {dp}", file=sys.stderr)

    print(f"\n=== Phase 2 완료 ===", file=sys.stderr)


if __name__ == "__main__":
    main()
