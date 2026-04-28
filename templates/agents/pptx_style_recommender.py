#!/usr/bin/env python3
"""
PPTX Style Recommender v2 (BaseAgent 기반)

내용 분석 → 자동 스타일 추천
- 단일 책임: 스타일 추천만 담당
- BaseAgent 상속으로 표준 인터페이스
"""

import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from base_agent import BaseAgent

from pptx_style_database import Style, StyleCategory


@dataclass
class StyleRecommendation:
    """스타일 추천 결과"""
    style: Style
    score: float
    reason: str

    def __str__(self):
        return f"[{self.score:.1f}] {self.style.name} - {self.reason}"


class PPTXStyleRecommender(BaseAgent):
    """PPTX 스타일 자동 추천 시스템 v2"""

    # 키워드 매핑
    KEYWORD_MAPPING = {
        "ai": ["ai", "인공지능", "머신러닝", "딥러닝", "automation"],
        "tech": ["tech", "기술", "saas", "소프트웨어", "startup"],
        "finance": ["finance", "재무", "금융", "investment", "투자"],
        "realestate": ["realestate", "부동산", "property", "프로퍼티"],
        "creative": ["creative", "크리에이티브", "marketing", "마케팅"],
        "education": ["education", "교육", "learning", "학습"],
    }

    # 목적별 우선순위 스타일
    PURPOSE_STYLE_MAP = {
        "ai": ["glassmorphism", "aurora_neon", "cyberpunk"],
        "tech": ["glassmorphism", "bento_grid", "swiss_international"],
        "finance": ["swiss_international", "monochrome_minimal"],
        "realestate": ["editorial_magazine", "minimalist_clean"],
        "creative": ["neo_brutalism", "vibrant_gradient"],
        "education": ["clean_academic", "modern_typography"],
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 에이전트 설정
        """
        super().__init__("pptx_style_recommender", config)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        return "content" in data

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        스타일 추천 처리

        Args:
            data: {
                "content": str,        # 분석할 내용
                "top_n": int,          # 상위 N개 추천 (선택)
                "operation": str       # "recommend" (기본)
            }

        Returns:
            {"recommendations": list, "top_pick": dict}
        """
        content = data["content"]
        top_n = data.get("top_n", 1)

        recommendations = self.recommend_top_n(content, top_n)

        return {
            "recommendations": [str(r) for r in recommendations],
            "top_pick": str(recommendations[0]) if recommendations else None,
            "count": len(recommendations),
            "operation": "recommend"
        }

    def recommend(self, content: str) -> Optional[Style]:
        """최고 스타일 하나 추천"""
        recommendations = self.recommend_top_n(content, 1)
        return recommendations[0].style if recommendations else None

    def recommend_top_n(self, content: str, top_n: int = 3) -> List[StyleRecommendation]:
        """상위 N개 스타일 추천"""
        # 카테고리 분석
        categories = self._analyze_categories(content)

        # 스타일 점수 계산
        style_scores = self._calculate_style_scores(categories)

        # 정렬
        sorted_styles = sorted(style_scores, key=lambda x: x.score, reverse=True)

        return sorted_styles[:top_n]

    def _analyze_categories(self, content: str) -> List[str]:
        """내용에서 카테고리 분석"""
        content_lower = content.lower()
        found_categories = []

        for category, keywords in self.KEYWORD_MAPPING.items():
            for keyword in keywords:
                if keyword.lower() in content_lower:
                    found_categories.append(category)
                    break

        return found_categories

    def _calculate_style_scores(self, categories: List[str]) -> List[StyleRecommendation]:
        """스타일 점수 계산"""
        style_scores = {}

        # 모든 스타일 기본 점수 0.5
        all_styles = PPTXStyleDatabase.get_all_styles()
        for style in all_styles:
            style_scores[style.name] = {"style": style, "score": 0.5, "reasons": []}

        # 카테고리별 점수 추가
        for category in categories:
            priority_styles = self.PURPOSE_STYLE_MAP.get(category, [])
            for style_name in priority_styles:
                if style_name in style_scores:
                    style_scores[style_name]["score"] += 0.3
                    style_scores[style_name]["reasons"].append(f"{category} 관련")

        # StyleRecommendation 변환
        recommendations = []
        for name, data in style_scores.items():
            reason = ", ".join(data["reasons"]) if data["reasons"] else "기본 추천"
            recommendations.append(StyleRecommendation(
                style=data["style"],
                score=data["score"],
                reason=reason
            ))

        return recommendations
