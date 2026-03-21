#!/usr/bin/env python3
"""
시장 분석 파이프라인

여러 카테고리의 뉴스를 수집하고 병렬로 분석하는 파이프라인 예시
"""

from typing import Dict, Any, List
from base_agent import BaseAgent
from pipeline_agent import ParallelPipelineAgent, ConditionalPipelineAgent

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from news_scraper import NewsScraper
from news_analyzer_v2 import NewsAnalyzer
from summarizer import Summarizer


class MultiCategoryScraper(BaseAgent):
    """다중 카테고리 스크래핑 에이전트"""

    def __init__(self, category: str, config: Dict[str, Any] = None):
        super().__init__(f"scraper_{category}", config)
        self.category = category
        self.scraper = NewsScraper()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """카테고리별 뉴스 수집"""
        display = data.get("display", 5)

        news = self.scraper.scrape_naver_news(self.category, display=display)

        return {
            f"{self.category}_news": news,
            "category": self.category,
            "count": len(news)
        }


class CategoryFocusAnalyzer(BaseAgent):
    """카테고리별 분석 에이전트"""

    def __init__(self, focus_area: str, config: Dict[str, Any] = None):
        super().__init__(f"analyzer_{focus_area}", config)
        self.focus_area = focus_area
        self.analyzer = NewsAnalyzer({
            **(config or {}),
            "focus": focus_area
        })

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """특정 분야에 집중한 분석"""
        # 모든 뉴스 카테고리에서 관련 기사 찾기
        all_articles = []

        for key, value in data.items():
            if key.endswith("_news") and isinstance(value, list):
                all_articles.extend(value)

        # 분석
        result = self.analyzer.run({
            "articles": all_articles,
            "operation": "insights",
            "date_range": "오늘"
        })

        result["focus_area"] = self.focus_area

        return result


class MarketAnalysisPipeline:
    """
    시장 분석 파이프라인

    여러 카테고리의 뉴스를 동시에 수집하고 분석합니다.
    """

    def __init__(self, categories: List[str] = None):
        """
        초기화

        Args:
            categories: 분석할 카테고리 리스트
        """
        self.categories = categories or ["부동산", "주식", "금리"]

        # 병렬 스크래핑 파이프라인
        self.scrapers = ParallelPipelineAgent(
            name="multi_scraper",
            agents=[
                MultiCategoryScraper(cat) for cat in self.categories
            ],
            merge_strategy="combine"
        )

        # 분석 파이프라인
        self.analyzers = ParallelPipelineAgent(
            name="multi_analyzer",
            agents=[
                CategoryFocusAnalyzer("부동산"),
                CategoryFocusAnalyzer("금융"),
                CategoryFocusAnalyzer(" macro")
            ],
            merge_strategy="all"
        )

    def run(self, display: int = 5) -> Dict[str, Any]:
        """
        파이프라인 실행

        Args:
            display: 카테고리별 수집할 뉴스 개수

        Returns:
            분석 결과
        """
        # 1단계: 병렬 스크래핑
        scrape_result = self.scrapers.run({"display": display})

        print(f"📰 뉴스 수집 완료")
        for key, value in scrape_result.items():
            if isinstance(value, dict) and "count" in value:
                print(f"  - {value.get('category', '')}: {value['count']}건")

        # 2단계: 병렬 분석
        analysis_result = self.analyzers.run(scrape_result)

        # 결과 정리
        summary = {
            "categories_analyzed": len(self.categories),
            "total_insights": 0,
            "focus_results": {}
        }

        if "_parallel_results" in analysis_result:
            for agent_name, result in analysis_result["_parallel_results"].items():
                focus_area = result.get("focus_area", agent_name)
                summary["focus_results"][focus_area] = result

                if "analysis" in result and "insights" in result["analysis"]:
                    summary["total_insights"] += len(result["analysis"]["insights"])

        return summary


# 메인 실행 예시
if __name__ == "__main__":
    # 파이프라인 실행
    pipeline = MarketAnalysisPipeline(["부동산", "주식", "금리"])

    print("🚀 시장 분석 파이프라인 실행 중...")
    result = pipeline.run(display=5)

    print(f"\n✅ 분석 완료!")
    print(f"분석된 카테고리: {result['categories_analyzed']}개")
    print(f"발견된 인사이트: {result['total_insights']}개")

    print(f"\n📊 분야별 인사이트:")
    for focus_area, data in result["focus_results"].items():
        print(f"\n【{focus_area}】")
        if "analysis" in data and "insights" in data["analysis"]:
            for insight in data["analysis"]["insights"][:2]:
                print(f"  - {insight.get('insight', '')}")
