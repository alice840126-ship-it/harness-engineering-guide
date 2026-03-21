#!/usr/bin/env python3
"""
PPTX Style Recommender Agent
내용 분석 → 자동 스타일 추천

Usage:
    from pptx_style_recommender import PPTXStyleRecommender

    recommender = PPTXStyleRecommender()
    style = recommender.recommend("AI 자동화 보고서")
    styles = recommender.recommend_top_n("부동산 투자 제안서", top_n=3)
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pptx_style_database import PPTXStyleDatabase, Style, StyleCategory


@dataclass
class StyleRecommendation:
    """스타일 추천 결과"""
    style: Style
    score: float
    reason: str

    def __str__(self):
        return f"[{self.score:.1f}] {style.name} - {reason}"


class PPTXStyleRecommender:
    """PPTX 스타일 자동 추천 시스템"""

    # 키워드 매핑 (한국어 + 영어)
    KEYWORD_MAPPING = {
        # ===== AI / TECH =====
        "ai": ["ai", "artificial intelligence", "인공지능", "머신러닝", "딥러닝", "automation", "자동화"],
        "tech": ["tech", "technology", "기술", "saas", "software", "소프트웨어", "startup", "스타트업"],
        "cybersecurity": ["cybersecurity", "보안", "security", "해킹"],
        "data": ["data", "데이터", "analytics", "분석", "infrastructure", "인프라"],

        # ===== FINANCE / BUSINESS =====
        "finance": ["finance", "financial", "재무", "금융", "investment", "투자", "investing"],
        "consulting": ["consulting", "컨설팅", "business", "비즈니스", "corporate", "기업"],
        "report": ["report", "보고서", "performance", "실적", "annual report", "연례 보고서"],
        "luxury": ["luxury", "럭셔리", "premium", "프리미엄", "high-end", "고급"],

        # ===== REAL ESTATE =====
        "realestate": ["realestate", "real estate", "부동산", "property", "프로퍼티", "building", "건물"],
        "knowledge_industry": ["knowledge", "지식산업센터", "industrial", "산업"],
        "commercial": ["commercial", "상업", "office", "오피스"],

        # ===== CREATIVE / MARKETING =====
        "creative": ["creative", "크리에이티브", "marketing", "마케팅", "brand", "브랜드", "campaign"],
        "launch": ["launch", "출시", "product", "제품", "feature", "기능"],
        "app": ["app", "앱", "application", "어플리케이션", "ui", "ux"],

        # ===== EDUCATION / CONTENT =====
        "education": ["education", "교육", "learning", "학습", "tutorial", "튜토리얼"],
        "content": ["content", "콘텐츠", "blog", "블로그", "story", "스토리"],

        # ===== ECO / NATURE =====
        "eco": ["eco", "에코", "sustainable", "지속가능", "environment", "환경", "green", "그린"],
        "wellness": ["wellness", "웰니스", "health", "건강", "medical", "의료"],

        # ===== EVENTS / ENTERTAINMENT =====
        "event": ["event", "이벤트", "festival", "페스티벌", "gala", "갈라"],
        "gaming": ["gaming", "게임", "esports", "e스포츠"],
    }

    # 목적별 우선순위 스타일 매핑
    PURPOSE_STYLE_MAP = {
        # AI / Tech
        "ai": ["glassmorphism", "aurora_neon", "cyberpunk"],
        "tech": ["glassmorphism", "bento_grid", "swiss_international"],
        "automation": ["glassmorphism", "swiss_international", "bento_grid"],

        # Finance / Business
        "finance": ["swiss_international", "monochrome_minimal", "editorial_magazine"],
        "consulting": ["swiss_international", "editorial_magazine", "monochrome_minimal"],
        "report": ["swiss_international", "editorial_magazine", "art_deco_luxe"],
        "investment": ["monochrome_minimal", "swiss_international", "art_deco_luxe"],

        # Real Estate
        "realestate": ["swiss_international", "bento_grid", "editorial_magazine"],
        "property": ["monochrome_minimal", "swiss_international", "claymorphism"],
        "commercial": ["bento_grid", "swiss_international", "glassmorphism"],

        # Creative
        "creative": ["neo_brutalism", "gradient_mesh", "bento_grid"],
        "marketing": ["neo_brutalism", "typographic_bold", "gradient_mesh"],
        "brand": ["gradient_mesh", "monochrome_minimal", "editorial_magazine"],
        "launch": ["glassmorphism", "gradient_mesh", "claymorphism"],

        # App / Product
        "app": ["claymorphism", "glassmorphism", "pastel_soft_ui"],
        "product": ["bento_grid", "claymorphism", "glassmorphism"],
        "feature": ["bento_grid", "glassmorphism", "claymorphism"],

        # Education
        "education": ["claymorphism", "nordic_minimalism", "hand_crafted_organic"],
        "tutorial": ["claymorphism", "glassmorphism", "nordic_minimalism"],

        # Eco / Nature
        "eco": ["hand_crafted_organic", "nordic_minimalism", "dark_forest_nature"],
        "sustainable": ["nordic_minimalism", "hand_crafted_organic"],

        # Events
        "event": ["retro_y2k", "dark_neon_miami", "memphis_pop"],
        "gala": ["art_deco_luxe", "monochrome_minimal"],

        # Gaming
        "gaming": ["cyberpunk", "dark_neon_miami", "aurora_neon"],
    }

    def __init__(self):
        """스타일 데이터베이스 로드"""
        self.db = PPTXStyleDatabase()
        self.all_styles = list(self.db.get_all_styles().values())

    def recommend(self, content: str, top_n: int = 1) -> List[StyleRecommendation]:
        """콘텐츠 분석 → 스타일 추천

        Args:
            content: 분석할 텍스트 (제목, 설명, 키워드 등)
            top_n: 반환할 추천 개수 (기본 1개)

        Returns:
            추천 스타일 리스트 (StyleRecommendation 객체)
        """
        recommendations = self._analyze_and_score(content, top_n=top_n)

        if not recommendations:
            # 기본값: Swiss International (안전한 기업용)
            default_style = self.db.get_style("swiss_international")
            return [StyleRecommendation(
                style=default_style,
                score=0.0,
                reason="기본 추천"
            )]

        return recommendations

    def get_top_style(self, content: str) -> Optional[Style]:
        """최고 스타일 1개 반환 (편의 메서드)"""
        recommendations = self.recommend(content, top_n=1)
        return recommendations[0].style if recommendations else None

    def recommend_top_n(self, content: str, top_n: int = 3) -> List[StyleRecommendation]:
        """상위 N개 스타일 추천"""
        return self.recommend(content, top_n=top_n)

    def recommend_by_keywords(self, keywords: List[str], top_n: int = 3) -> List[StyleRecommendation]:
        """키워드 리스트로 직접 추천"""
        keyword_text = " ".join(keywords)
        return self.recommend(keyword_text, top_n=top_n)

    def explain_recommendation(self, content: str) -> str:
        """추천 이유 설명"""
        recommendations = self.recommend(content, top_n=1)
        if not recommendations:
            return "추천할 스타일이 없습니다."

        recommendation = recommendations[0]
        style = recommendation.style

        # 키워드 분석
        detected_keywords = self._extract_keywords(content)

        explanation = f"## 스타일 추천: {style.name}\n\n"
        explanation += f"### 감성\n{', '.join(style.mood)}\n\n"
        explanation += f"### 추천 이유\n"
        explanation += f"감지된 키워드: {', '.join(detected_keywords)}\n\n"
        explanation += f"이 스타일은 {', '.join(style.best_for[:3])}에 최적화되어 있습니다.\n\n"
        explanation += f"### 주요 특징\n"
        for element in style.signature_elements[:3]:
            explanation += f"- {element}\n"

        return explanation

    def _analyze_and_score(self, content: str, top_n: int = 3) -> List[StyleRecommendation]:
        """콘텐츠 분석 → 스타일 점수화"""
        content_lower = content.lower()

        # 1. 키워드 추출
        detected_keywords = self._extract_keywords(content)

        # 2. 각 스타일 점수 계산
        scored_styles = []

        for style in self.all_styles:
            score = 0.0
            reasons = []

            # 방법 1: PURPOSE_STYLE_MAP 직접 매핑 (가중치 높음)
            for keyword, style_ids in self.PURPOSE_STYLE_MAP.items():
                if keyword in content_lower and style.id in style_ids:
                    # 매핑된 순서대로 점수 부여 (1순위 > 2순위 > 3순위)
                    index = style_ids.index(style.id)
                    score += max(3.0 - index, 1.0)
                    reasons.append(f"목적 매핑 ({keyword})")

            # 방법 2: 스타일의 best_for 필드 매칭
            for best_for in style.best_for:
                if any(kw in best_for.lower() for kw in detected_keywords):
                    score += 1.5
                    reasons.append(f"Best For 매칭")

            # 방법 3: 스타일의 keywords 필드 매칭
            for keyword in style.keywords:
                if keyword in content_lower:
                    score += 1.0
                    reasons.append(f"키워드 매칭")

            # 방법 4: mood 필드 매칭
            for mood in style.mood:
                if mood.lower() in content_lower:
                    score += 0.5
                    reasons.append(f"무드 매칭")

            # 점수가 0 이상이면 후보에 추가
            if score > 0:
                reason_str = ", ".join(reasons[:2])  # 상위 2개 이유만
                scored_styles.append(StyleRecommendation(
                    style=style,
                    score=score,
                    reason=reason_str
                ))

        # 점수순 정렬
        scored_styles.sort(key=lambda x: x.score, reverse=True)

        # 상위 N개 반환
        return scored_styles[:top_n]

    def _extract_keywords(self, content: str) -> List[str]:
        """콘텐츠에서 키워드 추출 (한국어 + 영어)"""
        content_lower = content.lower()
        detected = []

        for category, keywords in self.KEYWORD_MAPPING.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    detected.append(category)
                    break  # 카테고리당 1번만

        return list(set(detected))  # 중복 제거


# 테스트 코드
if __name__ == "__main__":
    recommender = PPTXStyleRecommender()

    # 테스트 케이스
    test_cases = [
        "AI 자동화 시스템 보고서",
        "부동산 투자 제안서",
        "구해줘 부동산 월간 실적 보고서",
        "지식산업센터 소개 자료",
        "신규 앱 출시 프레젠테이션",
        "교육 콘텐츠 제작 가이드",
        "친환경 브랜드 소개",
    ]

    print("=" * 60)
    print("PPTX Style Recommender Test")
    print("=" * 60)

    for test in test_cases:
        print(f"\n📝 Input: {test}")

        # 최고 1개 추천
        style = recommender.get_top_style(test)
        if style:
            print(f"✅ Top: {style.name}")
            print(f"   Mood: {', '.join(style.mood[:2])}")
            print(f"   Best For: {', '.join(style.best_for[:2])}")

        # 상위 3개 추천
        print(f"\n   Top 3:")
        for i, rec in enumerate(recommender.recommend_top_n(test, top_n=3), 1):
            print(f"   {i}. {rec.style.name} ({rec.score:.1f}점)")
            print(f"      이유: {rec.reason}")

    # 설명 테스트
    print("\n" + "=" * 60)
    print("설명 테스트")
    print("=" * 60)
    print(recommender.explain_recommendation("AI 자동화 보고서"))
