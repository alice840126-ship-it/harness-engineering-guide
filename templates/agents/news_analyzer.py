#!/usr/bin/env python3
"""
뉴스 분석 에이전트

뉴스 기사들을 분석해서 키워드 추출, 테마 그룹핑, 인사이트 도출
- 단일 책임: 뉴스 분석만 담당 (스크래핑, 발송은 다른 에이전트)
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime


class NewsAnalyzer:
    """뉴스 분석 에이전트"""

    def __init__(self):
        """초기화"""
        # 투자 키워드 사전
        self.investment_keywords = {
            'AI': ['AI', '인공지능', 'LLM', 'GPT', 'Claude', '삼성전자', 'SK하이닉스', 'HBM', '반도체'],
            '에너지': ['유가', '석유', '전력', '희토류', '원자력', '에너지', '발전'],
            '부동산': ['아파트', '분양', '청약', '재건축', '집값', '전세', '매매', '건설'],
            '금융': ['금리', '코스피', '코스닥', '주식', '주주', '펀드', '채권', '연준', '인플레'],
            '지정학': ['이란', '중동', '미국', '중국', '러시아', '무역', '지정학', '공급망'],
            '테마': ['테마', '섹터', '소재', '대표', '우량', '성장', '상승', '하락', '변동성'],
        }

        # 전망/예측 키워드
        self.outlook_keywords = [
            '전망', '예상', '예측', '전망됨', '시나리오',
            '목표가', '투자의견', '매수', '매도', '홀드'
        ]

    def extract_keywords(
        self,
        text: str,
        max_keywords: int = 10
    ) -> List[tuple]:
        """
        텍스트에서 키워드 추출

        Args:
            text: 분석할 텍스트
            max_keywords: 최대 키워드 수

        Returns:
            (카테고리, 키워드) 튜플 리스트
        """
        found_keywords = []

        for category, keywords in self.investment_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append((category, keyword))

        # 빈도 수로 상위 N개 선택
        from collections import Counter
        keyword_counts = Counter(found_keywords)
        top_keywords = keyword_counts.most_common(max_keywords)

        return [kw[0] for kw in top_keywords]  # (category, keyword) 튜플 반환

    def group_by_theme(
        self,
        articles: List[Dict[str, Any]],
        min_articles: int = 2
    ) -> Dict[str, Dict]:
        """
        기사들을 테마별로 그룹핑

        Args:
            articles: 기사 리스트
            min_articles: 최소 기사 수 (이하면 무시)

        Returns:
            테마별 그룹 딕셔너리
        """
        theme_groups = {}

        for article in articles:
            # 제목 + 내용 합치기
            text = article.get('title', '') + ' ' + article.get('content', '')

            # 키워드 추출
            keywords = self.extract_keywords(text)

            # 키워드별로 그룹핑
            for category, keyword in keywords:
                theme_key = f"{category}:{keyword}"

                if theme_key not in theme_groups:
                    theme_groups[theme_key] = {
                        'category': category,
                        'keyword': keyword,
                        'articles': [],
                        'count': 0
                    }

                theme_groups[theme_key]['articles'].append(article)
                theme_groups[theme_key]['count'] += 1

        # 최소 기사 수 필터링
        significant_themes = {
            k: v for k, v in theme_groups.items()
            if v['count'] >= min_articles
        }

        return significant_themes

    def derive_insights(
        self,
        themes: Dict[str, Dict],
        date_range: str
    ) -> List[Dict[str, Any]]:
        """
        테마들에서 구조적 통찰 도출

        Args:
            themes: 테마 그룹 딕셔너리
            date_range: 분석 기간

        Returns:
            인사이트 리스트
        """
        insights = []

        if not themes:
            return [{
                "type": "데이터 부족",
                "insight": "분석할 만한 데이터가 부족합니다.",
                "evidence": []
            }]

        # 빈도순 정렬
        sorted_themes = sorted(
            themes.values(),
            key=lambda x: x['count'],
            reverse=True
        )

        # 1차 테마 분석
        if sorted_themes:
            top_theme = sorted_themes[0]
            insights.append({
                "type": "주요 테마",
                "insight": f"'{top_theme['keyword']}'(이)가 가장 활발한 키워드입니다. {top_theme['count']}개 기사에서 언급되었습니다.",
                "evidence": [a['title'][:30] for a in top_theme['articles'][:3]]
            })

        # 2차 테마 분석
        if len(sorted_themes) >= 2:
            second_theme = sorted_themes[1]
            insights.append({
                "type": "2차 테마",
                "insight": f"'{second_theme['keyword']}'(과) 관련된 움직임도 있습니다. {second_theme['count']}개 기사로 확인됩니다.",
                "evidence": [a['title'][:30] for a in second_theme['articles'][:2]]
            })

        # 카테고리별 분석
        category_summary = {}
        for theme in sorted_themes:
            cat = theme['category']
            category_summary[cat] = category_summary.get(cat, 0) + 1

        if category_summary:
            dominant_category = max(category_summary, key=category_summary.get)
            category_count = len(category_summary)

            insights.append({
                "type": "주요 섹터",
                "insight": f"이번 기간에는 '{dominant_category}' 섹터가 가장 주목받고 있습니다. {category_count}개 카테고리에서 관련 기사가 보고되었습니다.",
                "evidence": list(category_summary.keys())
            })

        return insights

    def analyze_outlook(
        self,
        text: str
    ) -> Optional[str]:
        """
        텍스트에서 전망/예측 추출

        Args:
            text: 분석할 텍스트

        Returns:
            전망 문장 (없으면 None)
        """
        sentences = re.split(r'(?<=[.!?])', text)

        for sentence in sentences:
            # 전망 키워드 포함 문장 찾기
            if any(keyword in sentence for keyword in self.outlook_keywords):
                # 문장 정제
                clean_sentence = sentence.strip()
                if len(clean_sentence) > 20:
                    return clean_sentence

        return None

    def calculate_sentiment(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        텍스트 감성 분석 (간단 버전)

        Args:
            text: 분석할 텍스트

        Returns:
            감성 점수 딕셔너리
        """
        # 긍정 키워드
        positive_keywords = [
            '상승', '성장', '호조', '개선', '증가', '확대',
            '최고', '신고', '돌파', '달성', '성공'
        ]

        # 부정 키워드
        negative_keywords = [
            '하락', '위축', '악화', '감소', '축소', '위기',
            '우려', '부진', '약세', '하락세', '타격'
        ]

        positive_count = sum(1 for kw in positive_keywords if kw in text)
        negative_count = sum(1 for kw in negative_keywords if kw in text)

        total = positive_count + negative_count

        if total == 0:
            return {
                'score': 0,
                'label': '중립',
                'positive': 0,
                'negative': 0
            }

        score = (positive_count - negative_count) / total

        if score > 0.3:
            label = '긍정'
        elif score < -0.3:
            label = '부정'
        else:
            label = '중립'

        return {
            'score': score,
            'label': label,
            'positive': positive_count,
            'negative': negative_count
        }

    def generate_summary(
        self,
        articles: List[Dict[str, Any]],
        max_sentences: int = 5
    ) -> str:
        """
        기사들을 종합해서 요약 생성

        Args:
            articles: 기사 리스트
            max_sentences: 최대 문장 수

        Returns:
            요약 텍스트
        """
        if not articles:
            return "분석할 기사가 없습니다."

        # 모든 기사 제목 추출
        titles = [a.get('title', '') for a in articles[:10]]

        # 문장 분리
        all_sentences = []
        for title in titles:
            sentences = re.split(r'(?<=[.!?])', title)
            all_sentences.extend([s.strip() for s in sentences if s.strip()])

        # 상위 N개 선택
        top_sentences = all_sentences[:max_sentences]

        return ' '.join(top_sentences)

    def analyze_trend(
        self,
        articles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        기사들의 트렌드 분석

        Args:
            articles: 기사 리스트

        Returns:
            트렌드 분석 결과
        """
        if not articles:
            return {'trend': '없음', 'strength': 0}

        # 키워드 빈도 분석
        keyword_counts = {}

        for article in articles:
            keywords = self.extract_keywords(
                article.get('title', '') + ' ' + article.get('content', '')
            )

            for category, keyword in keywords:
                key = f"{category}:{keyword}"
                keyword_counts[key] = keyword_counts.get(key, 0) + 1

        if not keyword_counts:
            return {'trend': '없음', 'strength': 0}

        # 가장 빈도 높은 키워드
        top_keyword = max(keyword_counts.items(), key=lambda x: x[1])

        # 강도 계산 (0~1)
        strength = min(top_keyword[1] / len(articles), 1.0)

        return {
            'trend': top_keyword[0],
            'strength': strength,
            'article_count': top_keyword[1]
        }


# 편의 함수
def analyze_news_themes(articles: List[Dict]) -> Dict:
    """뉴스 테마 분석 (편의 함수)"""
    return NewsAnalyzer().group_by_theme(articles)


def derive_insights(themes: Dict, date_range: str) -> List:
    """인사이트 도출 (편의 함수)"""
    return NewsAnalyzer().derive_insights(themes, date_range)
