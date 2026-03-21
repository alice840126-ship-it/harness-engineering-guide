#!/usr/bin/env python3
"""
PPTXStyleRecommender v2 단위 테스트
"""

import pytest
from pptx_style_recommender_v2 import PPTXStyleRecommender


class TestPPTXStyleRecommender:
    """PPTXStyleRecommender 테스트"""

    def test_init(self):
        """초기화 테스트"""
        recommender = PPTXStyleRecommender()
        assert recommender.name == "pptx_style_recommender"

    def test_validate_input(self):
        """입력 검증"""
        recommender = PPTXStyleRecommender()
        assert recommender.validate_input({
            "content": "AI 자동화 시스템"
        }) is True

    def test_process_recommend(self):
        """스타일 추천 처리"""
        recommender = PPTXStyleRecommender()
        result = recommender.run({
            "content": "AI 자동화 보고서",
            "top_n": 3
        })
        assert "recommendations" in result
        assert "top_pick" in result

    def test_recommend(self):
        """최고 스타일 추천"""
        recommender = PPTXStyleRecommender()
        style = recommender.recommend("인공지능 프로젝트")
        # 스타일이 반환되거나 None
        assert style is None or hasattr(style, 'name')

    def test_get_stats(self):
        """통계 확인"""
        recommender = PPTXStyleRecommender()
        stats = recommender.get_stats()
        assert "runs" in stats
