#!/usr/bin/env python3
"""
블로그 아카이브 자동 분석.

3,000개 이상의 마크다운 파일에서:
1. 제목 전체 추출
2. 본문 어휘 빈도 분석
3. 2~4어절 구(句) 추출 (작가 특유 표현 찾기)
4. 제목 기반 테마 클러스터링 (키워드 기반)
5. 개념 공출현 분석
6. 연도별 변화 추적

사용법:
    python3 blog_archive_analyzer.py <폴더경로> [출력JSON]

출력:
    analysis.json — 통계 전체
    titles.txt — 제목 전체 리스트 (연도순)
    top_phrases.txt — 핵심 구절 TOP 100
"""

import sys
import os
import re
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


# 한국어 조사/어미/불용어
STOPWORDS = set([
    # 조사
    '은', '는', '이', '가', '을', '를', '의', '에', '에서', '에게', '한테',
    '로', '으로', '와', '과', '도', '만', '까지', '부터', '처럼', '보다',
    # 어미/동사
    '있다', '없다', '하다', '되다', '이다', '아니다', '것이다', '것은',
    '했다', '된다', '하는', '되는', '있는', '없는', '같은', '많은',
    '위해', '통해', '대한', '대해', '보다', '만큼', '뿐이다',
    # 부사/대명사
    '그리고', '그러나', '하지만', '그래서', '그런데', '그러면', '그러니까',
    '이것', '그것', '저것', '이런', '그런', '저런', '이렇게', '그렇게',
    '이제', '지금', '오늘', '어제', '내일', '매우', '아주', '정말',
    '다시', '또한', '또', '역시', '바로', '이미', '아직', '먼저',
    # 기타
    '때문', '경우', '정도', '수도', '것도', '것이', '것을', '해서',
    '우리', '내가', '나는', '내가', '나의', '내', '너', '당신',
    '그냥', '좀', '더', '덜', '많이', '적게', '크게', '작게',
    '하고', '되고', '이고', '처럼', '같이', '같은', '이런', '그런',
])


def extract_title(filepath: Path) -> str:
    """파일명에서 제목 추출 (구/신 포맷 모두).

    - 구: "{logNo}_{title}"
    - 신: "{YYYY-MM-DD}_{logNo}_{title}"
    """
    name = filepath.stem
    m = re.match(r'(?:\d{4}-\d{2}-\d{2}_)?\d+_(.+)', name)
    return m.group(1).strip() if m else name


def extract_content(filepath: Path) -> dict:
    """마크다운 파일에서 제목·본문·날짜 추출"""
    text = filepath.read_text(encoding='utf-8', errors='ignore')

    # frontmatter 파싱
    date_str = ''
    if text.startswith('---'):
        end = text.find('---', 3)
        if end != -1:
            fm = text[3:end]
            date_m = re.search(r'date:\s*(.+)', fm)
            if date_m:
                date_str = date_m.group(1).strip()
            text = text[end + 3:].lstrip()

    # 제목 (# 시작)
    title = ''
    title_m = re.search(r'^#\s+(.+)', text, flags=re.MULTILINE)
    if title_m:
        title = title_m.group(1).strip()

    # 본문 (제목 이후 ~ 출처 표시 전)
    body = text
    body = re.sub(r'^---[\s\S]*?---', '', body, count=1)  # frontmatter 제거
    body = re.sub(r'^#\s+.+\n', '', body, count=1)  # 제목 제거
    body = re.sub(r'\n?---\n※.*$', '', body, flags=re.DOTALL)  # 출처 푸터 제거
    body = body.strip()

    return {
        'title': title or extract_title(filepath),
        'body': body,
        'date': date_str,
        'filename': filepath.name,
    }


def tokenize(text: str) -> list:
    """한국어 간단 토큰화 — 2글자 이상 명사 후보"""
    # 한글 + 영문 단어
    tokens = re.findall(r'[가-힣]{2,}|[A-Za-z]{2,}', text)
    return [t for t in tokens if t not in STOPWORDS and len(t) >= 2]


def extract_phrases(text: str, min_len: int = 2, max_len: int = 4) -> list:
    """2~4어절 구 추출"""
    # 줄 단위로 자르기
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    phrases = []
    for line in lines:
        # 특수문자 제거
        clean = re.sub(r'[^\w\s가-힣]', ' ', line)
        words = clean.split()
        for i in range(len(words)):
            for n in range(min_len, min(max_len + 1, len(words) - i + 1)):
                phrase = ' '.join(words[i:i+n])
                # 2글자 이상 한글 단어 포함된 것만
                if len(phrase) >= 5 and any(len(w) >= 2 and re.match(r'[가-힣]+', w) for w in phrase.split()):
                    phrases.append(phrase)
    return phrases


def classify_theme(title: str) -> list:
    """제목에서 테마 키워드 매칭"""
    themes = []
    theme_keywords = {
        '투자/시장': ['투자', '주식', '종목', '시장', '매수', '매도', '수익률', '포트폴리오', '리서치', '펀드', 'ETF'],
        '부동산': ['부동산', '아파트', '재건축', '분양', '청약', '전세', '월세', '매매'],
        '경제/거시': ['금리', '환율', '달러', '원화', '인플레', '경제', 'GDP', '성장', '침체', '통화'],
        '기업/산업': ['기업', '회사', '산업', '반도체', '자동차', '바이오', '제약', '에너지'],
        '메타인지/철학': ['생각', '관점', '프레임', '범주', '인지', '해상도', '시각', '의미', '본질'],
        '심리/행동': ['심리', '편향', '감정', '두려움', '탐욕', '습관', '행동'],
        '역사/장기': ['역사', '시대', '세기', '과거', '미래', '장기', '10년', '100년'],
        '기술/AI': ['AI', '인공지능', '기술', '데이터', '디지털', '자동화', '플랫폼'],
        '사회/정치': ['정치', '사회', '정부', '규제', '정책', '제도', '국가'],
        '개인/삶': ['삶', '인생', '일상', '가족', '시간', '선택', '결정'],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in title for kw in keywords):
            themes.append(theme)
    return themes or ['미분류']


def get_year(date_str: str, filename: str) -> str:
    """날짜/파일명에서 연도 추출"""
    # frontmatter date에서
    m = re.search(r'(\d{4})', date_str)
    if m:
        return m.group(1)
    # 신 포맷이면 파일명 앞 YYYY-MM-DD 사용
    m = re.match(r'(\d{4})-\d{2}-\d{2}_', filename)
    if m:
        return m.group(1)
    # logNo에서 (네이버 logNo는 시간순 — 223으로 시작하면 2021, 224는 2022~)
    m = re.match(r'(\d+)_', filename)
    if m:
        log_no = m.group(1)
        # 네이버 블로그 logNo 대략적 연도 매핑
        if log_no.startswith('222'):
            return '2020'
        elif log_no.startswith('222') and log_no[3:6] > '500':
            return '2021'
        elif log_no.startswith('223'):
            return '2022'
        elif log_no.startswith('223') and log_no[3:6] > '500':
            return '2023'
        elif log_no.startswith('224'):
            return '2024'
    return 'unknown'


def analyze_archive(dir_path: Path) -> dict:
    """전체 아카이브 분석"""
    files = sorted(dir_path.glob('*.md'))
    print(f"총 {len(files)}개 파일 분석 시작...", file=sys.stderr)

    all_titles = []
    word_counter = Counter()
    phrase_counter = Counter()
    theme_counter = Counter()
    theme_files = defaultdict(list)
    year_counter = Counter()
    year_words = defaultdict(Counter)
    cooccurrence = defaultdict(Counter)  # 단어 공출현

    for i, filepath in enumerate(files, 1):
        if i % 500 == 0:
            print(f"  {i}/{len(files)} 처리 중...", file=sys.stderr)
        try:
            data = extract_content(filepath)

            # 제목 저장
            all_titles.append({
                'title': data['title'],
                'filename': data['filename'],
                'date': data['date'],
            })

            # 연도 추출
            year = get_year(data['date'], data['filename'])
            year_counter[year] += 1

            # 테마 분류
            themes = classify_theme(data['title'])
            for theme in themes:
                theme_counter[theme] += 1
                if len(theme_files[theme]) < 100:
                    theme_files[theme].append(data['title'])

            # 어휘 토큰화 (제목 + 본문 앞 2000자만)
            text_sample = data['title'] + ' ' + data['body'][:2000]
            tokens = tokenize(text_sample)
            word_counter.update(tokens)
            year_words[year].update(tokens)

            # 구절 추출 (본문 앞 1000자에서만 — 속도 위해)
            phrases = extract_phrases(data['body'][:1000])
            phrase_counter.update(phrases)

            # 공출현 (한 글 내 자주 나온 단어 쌍)
            top_in_doc = [w for w, _ in Counter(tokens).most_common(20)]
            for w1 in top_in_doc:
                for w2 in top_in_doc:
                    if w1 < w2:
                        cooccurrence[w1][w2] += 1

        except Exception as e:
            print(f"  실패 {filepath.name}: {e}", file=sys.stderr)
            continue

    # 결과 정리
    top_words = word_counter.most_common(200)
    top_phrases = [(p, c) for p, c in phrase_counter.most_common(300) if c >= 3]

    # 연도별 top 단어
    year_top = {}
    for year, counter in year_words.items():
        year_top[year] = counter.most_common(30)

    # 공출현 TOP (가중치 높은 페어)
    cooc_pairs = []
    for w1, partners in cooccurrence.items():
        for w2, count in partners.most_common(5):
            if count >= 10:
                cooc_pairs.append((w1, w2, count))
    cooc_pairs.sort(key=lambda x: x[2], reverse=True)

    return {
        'total_files': len(files),
        'all_titles': all_titles,
        'top_words': top_words,
        'top_phrases': top_phrases[:200],
        'themes': theme_counter.most_common(),
        'theme_examples': {k: v[:20] for k, v in theme_files.items()},
        'years': dict(year_counter),
        'year_top_words': {y: w[:20] for y, w in year_top.items()},
        'top_cooccurrence': cooc_pairs[:100],
    }


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 blog_archive_analyzer.py <폴더> [출력경로]")
        sys.exit(1)

    dir_path = Path(sys.argv[1])
    if not dir_path.exists():
        print(f"폴더 없음: {dir_path}")
        sys.exit(1)

    output = Path(sys.argv[2]) if len(sys.argv) >= 3 else dir_path.parent / "analysis.json"

    result = analyze_archive(dir_path)

    # JSON 저장
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 요약 출력
    print(f"\n=== 분석 완료 ===", file=sys.stderr)
    print(f"총 파일: {result['total_files']}", file=sys.stderr)
    print(f"\n상위 어휘 20개:", file=sys.stderr)
    for word, count in result['top_words'][:20]:
        print(f"  {word}: {count}", file=sys.stderr)
    print(f"\n테마 분포:", file=sys.stderr)
    for theme, count in result['themes']:
        print(f"  {theme}: {count}", file=sys.stderr)
    print(f"\n연도별:", file=sys.stderr)
    for year, count in sorted(result['years'].items()):
        print(f"  {year}: {count}", file=sys.stderr)
    print(f"\n저장: {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
