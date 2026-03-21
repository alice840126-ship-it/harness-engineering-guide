#!/usr/bin/env python3
"""
하네스 엔지니어링 v2 사용 예시

BaseAgent, PipelineAgent를 활용한 에이전트 조립 방법을 보여줍니다.
"""

# ===== 1단계: 기본 에이전트 사용 =====

from news_analyzer_v2 import NewsAnalyzer

# 기본 사용
analyzer = NewsAnalyzer()

# 키워드 추출
result = analyzer.run({
    "articles": [
        {"title": "삼성전자 HBM 생산", "content": "AI 반도체 호재"},
        {"title": "SK하이닉스 칩", "content": "HBM 투자 확대"}
    ],
    "operation": "keywords"
})
print(result)
# {"keywords": [('AI', 'HBM'), ('AI', '반도체'), ...]}

# ===== 2단계: 파이프라인 사용 =====

from pipeline_agent import PipelineAgent
from news_scraper import NewsScraper
from summarizer import Summarizer

# 개별 에이전트 생성 (BaseAgent 래퍼 필요한 경우 래퍼 클래스 작성)
class ScraperAgent(BaseAgent):
    def __init__(self):
        super().__init__("news_scraper")
        self.scraper = NewsScraper()

    def process(self, data):
        query = data["query"]
        news = self.scraper.scrape_naver_news(query, display=10)
        return {"articles": news}

class SummarizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("summarizer")
        self.summarizer = Summarizer()

    def process(self, data):
        articles = data["articles"]
        summary = self.summarizer.summarize_news(articles, max_count=5)
        return {"summary": summary}

# 파이프라인 조립
pipeline = PipelineAgent(
    name="daily_news_pipeline",
    agents=[
        ScraperAgent(),      # 뉴스 수집
        NewsAnalyzer(),      # 뉴스 분석
        SummarizerAgent()    # 요약
    ]
)

# 파이프라인 실행
result = pipeline.run({
    "query": "부동산 정책",
    "operation": "insights",
    "date_range": "2026-03-21"
})
print(result)

# ===== 3단계: 조건부 파이프라인 =====

from pipeline_agent import ConditionalPipelineAgent

# 카테고리별 분기
def category_condition(data):
    """뉴스 카테고리에 따라 분기"""
    query = data.get("query", "")
    if "부동산" in query:
        return "real_estate"
    elif "주식" in query or "코스피" in query:
        return "stock"
    else:
        return "general"

# 분기별 에이전트 구성
branches = {
    "real_estate": [NewsAnalyzer({"focus": "부동산"})],
    "stock": [NewsAnalyzer({"focus": "금융"})],
    "general": [NewsAnalyzer()]
}

conditional_pipeline = ConditionalPipelineAgent(
    name="smart_news_pipeline",
    branches=branches,
    condition=category_condition
)

# ===== 4단계: 병렬 파이프라인 =====

from pipeline_agent import ParallelPipelineAgent

# 여러 분석을 병렬로 실행
parallel_pipeline = ParallelPipelineAgent(
    name="multi_analysis_pipeline",
    agents=[
        NewsAnalyzer({"name": "keyword_analyzer"}),
        NewsAnalyzer({"name": "sentiment_analyzer"})
    ],
    merge_strategy="combine"
)

result = parallel_pipeline.run({
    "articles": [...],
    "operation": "keywords"
})

# ===== 5단계: 에러 핸들링 =====

# 에러가 발생해도 계속 실행
pipeline = PipelineAgent(
    name="robust_pipeline",
    agents=[...],
    stop_on_error=False  # 에러가 발생해도 계속
)

try:
    result = pipeline.run(data)
except Exception as e:
    # 에러가 발생하면 여기서 처리
    print(f"파이프라인 실패: {e}")

# ===== 6단계: 통계 확인 =====

print(pipeline.get_stats())
# {"runs": 10, "errors": 1, "last_run": "2026-03-21T10:00:00"}

for agent in pipeline.agents:
    print(f"{agent.name}: {agent.get_stats()}")
