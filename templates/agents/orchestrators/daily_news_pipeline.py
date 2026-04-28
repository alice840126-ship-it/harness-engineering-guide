#!/usr/bin/env python3
"""
아침 뉴스 파이프라인

실제 작동하는 데일리 뉴스 파이프라인 예시
- 뉴스 수집 → 분석 → 요약 → 텔레그램 발송
"""

from typing import Dict, Any, List
from base_agent import BaseAgent
from pipeline_agent import PipelineAgent

# 기존 에이전트 import (경로에 따라 조정 필요)
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from news_scraper import NewsScraper
from news_analyzer import NewsAnalyzer
from summarizer import Summarizer
from telegram_sender import TelegramSender


class ScraperAgent(BaseAgent):
    """뉴스 스크래핑 에이전트 (BaseAgent 래퍼)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("news_scraper", config)
        self.scraper = NewsScraper()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        뉴스 스크래핑

        Args:
            data: {"query": str, "display": int}

        Returns:
            {"articles": List[Dict], "query": str}
        """
        query = data.get("query", "경제")
        display = data.get("display", 10)

        # 스크래핑
        news = self.scraper.scrape_naver_news(query, display=display)

        return {
            "articles": news,
            "query": query,
            "count": len(news)
        }


class AnalyzerAgent(BaseAgent):
    """뉴스 분석 에이전트 (BaseAgent 래퍼)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("news_analyzer", config)
        self.analyzer = NewsAnalyzer(config)

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """입력 검증"""
        return "articles" in data

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        뉴스 분석

        Args:
            data: {"articles": List[Dict], "operation": str, "date_range": str}

        Returns:
            {"analysis": Dict, "articles": List[Dict]}
        """
        articles = data.get("articles", [])
        operation = data.get("operation", "insights")
        date_range = data.get("date_range", "오늘")

        # 분석
        result = self.analyzer.run({
            "articles": articles,
            "operation": operation,
            "date_range": date_range
        })

        # 원본 기사도 함께 반환
        result["articles"] = articles

        return result


class SummarizerAgent(BaseAgent):
    """요약 에이전트 (BaseAgent 래퍼)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("summarizer", config)
        self.summarizer = Summarizer()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        뉴스 요약

        Args:
            data: {"articles": List[Dict], "max_count": int}

        Returns:
            {"summary": str, "article_count": int}
        """
        articles = data.get("articles", [])
        max_count = data.get("max_count", 5)

        # 요약
        summary = self.summarizer.summarize_news(articles, max_count=max_count)

        return {
            "summary": summary,
            "article_count": len(articles)
        }


class TelegramSenderAgent(BaseAgent):
    """텔레그램 발송 에이전트 (BaseAgent 래퍼)"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("telegram_sender", config)
        self.sender = TelegramSender()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        텔레그램 발송

        Args:
            data: {"title": str, "content": str, "metadata": Dict}

        Returns:
            {"sent": bool, "message_id": str}
        """
        title = data.get("title", "뉴스")
        content = data.get("content", "")
        metadata = data.get("metadata", {})

        # 데일리 리포트 형식으로 발송
        success = self.sender.send_daily_report(title, content, metadata)

        return {
            "sent": success,
            "title": title,
            "content_length": len(content)
        }


class DailyNewsPipeline:
    """
    아침 뉴스 파이프라인

    사용 예시:
        pipeline = DailyNewsPipeline()
        result = pipeline.run("부동산", display=10)
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        초기화

        Args:
            config: 파이프라인 설정
        """
        self.config = config or {}

        # 에이전트 조립 (observe=True → pipeline_observer JSONL 자동 기록)
        self.pipeline = PipelineAgent(
            name="daily_news_pipeline",
            agents=[
                ScraperAgent(),           # 1. 뉴스 수집
                AnalyzerAgent(config),    # 2. 뉴스 분석
                SummarizerAgent(),        # 3. 요약
            ],
            stop_on_error=False,
            observe=True,
            observe_keyword_key="query",
        )

        # 텔레그램 발송 에이전트 (별도)
        self.sender = TelegramSenderAgent(config)

    def run(
        self,
        query: str,
        display: int = 10,
        send_telegram: bool = False
    ) -> Dict[str, Any]:
        """
        파이프라인 실행

        Args:
            query: 검색어
            display: 수집할 뉴스 개수
            send_telegram: 텔레그램 발송 여부

        Returns:
            실행 결과
        """
        # 1-3단계: 파이프라인 실행
        result = self.pipeline.run({
            "query": query,
            "display": display,
            "operation": "insights",
            "date_range": "오늘"
        })

        # 4단계: 텔레그램 발송 (선택)
        if send_telegram:
            # 메시지 포맷팅
            title = f"📰 {query} 뉴스"
            content = result.get("summary", "")
            metadata = {
                "분석": result.get("analysis", {}),
                "기사 수": result.get("article_count", 0)
            }

            send_result = self.sender.run({
                "title": title,
                "content": content,
                "metadata": metadata
            })

            result["telegram_sent"] = send_result["sent"]

        return result


# 메인 실행 예시
if __name__ == "__main__":
    # 파이프라인 실행
    pipeline = DailyNewsPipeline()

    print("🚀 아침 뉴스 파이프라인 실행 중...")
    result = pipeline.run("부동산", display=5)

    print(f"\n✅ 완료!")
    print(f"수집된 기사: {result.get('count', 0)}건")
    print(f"요약: {result.get('summary', '')[:100]}...")

    if "analysis" in result and "insights" in result["analysis"]:
        print(f"\n📊 인사이트:")
        for insight in result["analysis"]["insights"][:3]:
            print(f"  - {insight.get('insight', '')}")
