#!/usr/bin/env python3
"""
통합 테스트 - 데일리 뉴스 파이프라인

실제 사용 시나리오를 기반으로 한 통합 테스트 예시
"""

import pytest
from base_agent import BaseAgent


class MockNewsScraper(BaseAgent):
    """뉴스 스크래핑 모의 에이전트"""

    def __init__(self):
        super().__init__("news_scraper")
        self.mock_news = [
            {
                "title": "삼성전자 HBM 투자 확대",
                "description": "AI 반도체 수요 증가로 투자 확대",
                "link": "https://news.naver.com/1"
            },
            {
                "title": "SK하이닉스 HBM3e 개발 성공",
                "description": "차세대 HBM 기술 개발",
                "link": "https://news.naver.com/2"
            },
            {
                "title": "부동산 시장 회복세",
                "description": "서울 아파트 prices 상승",
                "link": "https://news.naver.com/3"
            }
        ]

    def process(self, data):
        query = data.get("query", "")
        return {"articles": self.mock_news, "query": query}


class MockNewsAnalyzer(BaseAgent):
    """뉴스 분석 모의 에이전트"""

    def process(self, data):
        articles = data.get("articles", [])

        # 간단한 키워드 분석
        keywords = []
        for article in articles:
            title = article.get("title", "")
            if "HBM" in title or "반도체" in title:
                keywords.append(("AI", "반도체"))
            if "부동산" in title or "아파트" in title:
                keywords.append(("부동산", "시장"))

        return {
            "articles": articles,
            "keywords": keywords,
            "analysis": "총 {}개 기사 분석 완료".format(len(articles))
        }


class MockSummarizer(BaseAgent):
    """요약 모의 에이전트"""

    def process(self, data):
        articles = data.get("articles", [])
        keywords = data.get("keywords", [])

        summary_lines = []
        for i, article in enumerate(articles[:3], 1):
            summary_lines.append(
                "{}. {}".format(i, article.get("title", ""))
            )

        return {
            "summary": "\n".join(summary_lines),
            "keywords": keywords,
            "article_count": len(articles)
        }


class MockTelegramSender(BaseAgent):
    """텔레그램 발송 모의 에이전트"""

    def __init__(self):
        super().__init__("telegram_sender")
        self.sent_messages = []

    def process(self, data):
        message = data.get("message", "")
        self.sent_messages.append(message)
        return {"sent": True, "message_count": len(self.sent_messages)}


class TestDailyNewsPipeline:
    """데일리 뉴스 파이프라인 통합 테스트"""

    def test_full_pipeline(self):
        """전체 파이프라인 실행 테스트"""
        # 파이프라인 구성
        scraper = MockNewsScraper()
        analyzer = MockNewsAnalyzer()
        summarizer = MockSummarizer()
        sender = MockTelegramSender()

        # 1단계: 뉴스 수집
        scrape_result = scraper.run({"query": "반도체"})
        assert "articles" in scrape_result
        assert len(scrape_result["articles"]) > 0

        # 2단계: 뉴스 분석
        analyze_result = analyzer.run(scrape_result)
        assert "keywords" in analyze_result
        assert len(analyze_result["keywords"]) > 0

        # 3단계: 요약
        summary_result = summarizer.run(analyze_result)
        assert "summary" in summary_result
        assert summary_result["article_count"] > 0

        # 4단계: 발송
        message = "📰 오늘의 뉴스\n\n{}".format(summary_result["summary"])
        send_result = sender.run({"message": message})
        assert send_result["sent"] is True
        assert len(sender.sent_messages) == 1

    def test_pipeline_with_empty_news(self):
        """빈 뉴스 처리 테스트"""
        scraper = MockNewsScraper()
        scraper.mock_news = []  # 빈 뉴스

        result = scraper.run({"query": "test"})
        assert result["articles"] == []

    def test_pipeline_integration_with_data_flow(self):
        """데이터 흐름 확인 테스트"""
        # 파이프라인 실행
        scraper = MockNewsScraper()
        analyzer = MockNewsAnalyzer()
        summarizer = MockSummarizer()

        # 데이터 흐름 추적
        data = {"query": "HBM"}

        # 각 단계에서 데이터가 올바르게 전달되는지 확인
        data = scraper.run(data)
        assert "articles" in data

        data = analyzer.run(data)
        assert "keywords" in data
        assert data["article_count"] == len(scraper.mock_news)

        data = summarizer.run(data)
        assert "summary" in data


class TestErrorHandling:
    """에러 처리 통합 테스트"""

    class FailingScraper(BaseAgent):
        """실패하는 스크래퍼"""

        def process(self, data):
            raise ConnectionError("네트워크 오류")

    def test_scraper_failure(self):
        """스크래퍼 실패 시 처리"""
        scraper = self.FailingScraper()
        analyzer = MockNewsAnalyzer()

        # 스크래퍼 실패
        with pytest.raises(ConnectionError):
            scraper.run({"query": "test"})

        # 에러 후 통계 확인
        stats = scraper.get_stats()
        assert stats["errors"] == 1
