#!/usr/bin/env python3
"""
블로그 글 자동 검증 스크립트.

작성된 마크다운을 검사해서 다음을 확인:
- 글자수 (최소 권장)
- H2 섹션 개수
- 합쇼체 통일 (해라체/해요체 혼용 금지)
- 금지어 사용
- AI 말투 패턴
- 출처 없는 수치 (정확한 숫자 + 원/억/% 등)
- 이미지 플레이스홀더 중복

사용법:
    python3 blog_validator.py <블로그.md> [--min-chars 4000] [--min-h2 6]

종료 코드:
    0: 모두 통과
    1: 검증 실패 (재작성 필요)
"""

import sys
import re
import json
from pathlib import Path

# 금지어
BANNED_WORDS = [
    "다양한 측면에서",
    "종합적으로 살펴보면",
    "종합적으로",
    "이처럼",
    "이에 따라",
    "이를 통해",
    "도움이 되셨으면 좋겠습니다",
    "도움이 되셨으면",
    "기반으로 한",
    "뿐만 아니라",
    "더불어",
    "나아가",
    "본 글에서는",
    "제시합니다",
    "소개합니다",
]

# 해요체 패턴 (FAQ 답변 등 일부 허용 가능, 본문은 금지)
HAEYO_PATTERNS = [
    r'~?세요\.',
    r'예요\.',
    r'에요\.',
    r'거든요',
    r'더라고요',
    r'잖아요',
]

# 해라체 패턴 (합쇼체 전용 블로그에서 금지)
HAERA_PATTERNS = [
    r'[가-힣]+한다\.',
    r'[가-힣]+된다\.',
    r'[가-힣]+이다\.',
    r'[가-힣]+없다\.',
    r'[가-힣]+않다\.',
    r'[가-힣]+있다\.',
    r'[가-힣]+어렵다\.',
    r'[가-힣]+좋다\.',
    r'[가-힣]+많다\.',
    r'[가-힣]+크다\.',
    r'[가-힣]+낫다\.',
    r'[가-힣]+보자\.',
    r'[가-힣]+하자\.',
    r'[가-힣]+뛰게 된다\.',
    r'[가-힣]+넘긴다\.',
    r'[가-힣]+쌓인다\.',
    r'[가-힣]+돌려준다\.',
    r'[가-힣]+읽는다\.',
    r'[가-힣]+뿐이다\.',
    r'[가-힣]+인 셈이다\.',
    r'[가-힣]+는 점이다\.',
    r'[가-힣]+는 것이다\.',
    r'[가-힣]+뿐이다\.',
]

# 잘못된 용어 (정정 필요)
WRONG_TERMS = {
    "아이파트": "아이파크",
    "드릿거리": "(의미 불명 — 정확한 용어로 교체 필요)",
    "선분양 조합원": "조합원 (재건축은 조합원 분양)",
}


def count_chars_no_spaces(text: str) -> int:
    """공백 제외 글자수"""
    return len(re.sub(r'\s', '', text))


def extract_body(md_text: str) -> str:
    """frontmatter 제거 후 본문만"""
    if md_text.startswith("---"):
        end = md_text.find("---", 3)
        if end != -1:
            return md_text[end + 3:].lstrip("\n")
    return md_text


def check_h2_count(text: str) -> int:
    """H2 섹션 개수"""
    return len(re.findall(r'^## ', text, flags=re.MULTILINE))


def check_banned_words(text: str) -> list:
    """금지어 검색"""
    found = []
    for word in BANNED_WORDS:
        if word in text:
            found.append(word)
    return found


def check_haeyo_mixed(text: str) -> list:
    """해요체 혼용 검사"""
    found = []
    for pat in HAEYO_PATTERNS:
        matches = re.findall(pat, text)
        if matches:
            found.extend(matches[:3])
    return found


def check_haera_mixed(text: str) -> list:
    """해라체 혼용 검사 — 합쇼체 전용 블로그에서 해라체 사용 시 실패"""
    found = []
    for pat in HAERA_PATTERNS:
        matches = re.findall(pat, text)
        if matches:
            found.extend(matches[:3])
    return found


def check_wrong_terms(text: str) -> dict:
    """잘못된 용어"""
    found = {}
    for wrong, correct in WRONG_TERMS.items():
        if wrong in text:
            found[wrong] = correct
    return found


def check_unsourced_numbers(text: str) -> list:
    """출처 없는 구체 수치 의심 패턴"""
    # "약 6,104만원", "16억~18억원대" 같은 패턴
    suspicious = []

    # 패턴 1: 구체적 금액 (천만원/억원 단위)
    pattern1 = r'(약\s*)?[\d,]+(만원|억원|원)'
    for match in re.finditer(pattern1, text):
        # 같은 줄에 "출처", "확인 필요", "기준" 등이 있는지 확인
        line_start = text.rfind('\n', 0, match.start()) + 1
        line_end = text.find('\n', match.end())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        if not any(w in line for w in ['출처', '확인 필요', '기준', '※', '자료']):
            suspicious.append(match.group(0))

    # 패턴 2: 구체적 비율
    pattern2 = r'\d+(\.\d+)?%'
    for match in re.finditer(pattern2, text):
        line_start = text.rfind('\n', 0, match.start()) + 1
        line_end = text.find('\n', match.end())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        if not any(w in line for w in ['출처', '확인 필요', '기준', '※', '자료']):
            suspicious.append(match.group(0))

    return suspicious[:10]  # 너무 많으면 처음 10개만


def check_image_placeholders(text: str) -> dict:
    """이미지 플레이스홀더 검사"""
    h2_sections = re.split(r'^## ', text, flags=re.MULTILINE)[1:]  # 첫 번째는 H2 이전
    sections_with_multiple_images = []
    for i, section in enumerate(h2_sections):
        title = section.split('\n', 1)[0]
        # [이미지] 또는 ![](images/...) 패턴 카운트
        placeholder_count = len(re.findall(r'\[이미지[^\]]*\]', section))
        actual_image_count = len(re.findall(r'!\[[^\]]*\]\(images/[^)]+\)', section))
        total = placeholder_count + actual_image_count
        if total > 1:
            sections_with_multiple_images.append({
                'section': i + 1,
                'title': title.strip(),
                'count': total,
            })
    return {
        'multiple_images': sections_with_multiple_images,
        'total_h2': len(h2_sections),
    }


def check_hashtags(text: str) -> int:
    """해시태그 개수 (마지막 줄 기준)"""
    tags = re.findall(r'#\S+', text)
    return len(tags)


def validate(md_path: str, min_chars: int = 4000, min_h2: int = 6) -> dict:
    md_file = Path(md_path)
    if not md_file.exists():
        return {"ok": False, "error": f"파일 없음: {md_path}"}

    full_text = md_file.read_text(encoding="utf-8")
    body = extract_body(full_text)

    # 검사 실행
    char_count = count_chars_no_spaces(body)
    h2_count = check_h2_count(body)
    banned = check_banned_words(body)
    haeyo = check_haeyo_mixed(body)
    haera = check_haera_mixed(body)
    wrong = check_wrong_terms(body)
    unsourced = check_unsourced_numbers(body)
    image_check = check_image_placeholders(body)
    hashtag_count = check_hashtags(body)

    # 통과 여부
    issues = []

    if char_count < min_chars:
        issues.append(f"❌ 글자수 부족: {char_count}자 (최소 {min_chars}자)")

    if h2_count < min_h2:
        issues.append(f"❌ H2 부족: {h2_count}개 (최소 {min_h2}개)")

    if banned:
        issues.append(f"❌ 금지어 발견: {', '.join(banned)}")

    if haeyo:
        issues.append(f"⚠️ 해요체 혼용 의심 (FAQ는 허용): {len(haeyo)}건 — {haeyo[:3]}")

    if haera:
        issues.append(f"❌ 해라체 사용 금지 (합쇼체만 허용): {len(haera)}건 — {haera[:5]}")

    if wrong:
        issues.append(f"❌ 잘못된 용어: {wrong}")

    if unsourced:
        issues.append(f"⚠️ 출처 없는 수치 의심: {unsourced[:5]}{' ...' if len(unsourced) > 5 else ''}")

    if image_check['multiple_images']:
        issues.append(f"❌ 이미지 중복: {image_check['multiple_images']}")

    if hashtag_count < 10:
        issues.append(f"❌ 해시태그 부족: {hashtag_count}개 (최소 10개)")

    passed = not any(i.startswith("❌") for i in issues)

    return {
        "ok": passed,
        "passed": passed,
        "char_count": char_count,
        "h2_count": h2_count,
        "hashtag_count": hashtag_count,
        "issues": issues,
        "metrics": {
            "banned_words": banned,
            "haeyo_mixed": haeyo,
            "wrong_terms": wrong,
            "unsourced_numbers": unsourced,
            "image_check": image_check,
        }
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 blog_validator.py <블로그.md> [--min-chars N] [--min-h2 N]")
        sys.exit(1)

    md_path = sys.argv[1]
    min_chars = 4000
    min_h2 = 6

    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--min-chars" and i + 1 < len(args):
            min_chars = int(args[i + 1])
            i += 2
        elif args[i] == "--min-h2" and i + 1 < len(args):
            min_h2 = int(args[i + 1])
            i += 2
        else:
            i += 1

    result = validate(md_path, min_chars, min_h2)

    print(f"=== 블로그 검증 결과 ===")
    print(f"파일: {md_path}")
    print(f"글자수: {result['char_count']}자 (최소 {min_chars}자)")
    print(f"H2 섹션: {result['h2_count']}개 (최소 {min_h2}개)")
    print(f"해시태그: {result['hashtag_count']}개")
    print()

    if result["passed"]:
        print("✅ 모든 검증 통과")
        if result["issues"]:
            print()
            print("⚠️ 경고 (재작성 권장 안 함):")
            for issue in result["issues"]:
                print(f"  {issue}")
        sys.exit(0)
    else:
        print("❌ 검증 실패 — 재작성 필요")
        print()
        for issue in result["issues"]:
            print(f"  {issue}")
        sys.exit(1)
