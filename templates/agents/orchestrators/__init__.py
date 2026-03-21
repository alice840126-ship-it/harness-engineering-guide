"""
오케스트레이터 - 실전 파이프라인 예시

여러 에이전트를 조립하여 실제 작업을 수행하는 파이프라인들입니다.
"""

from .daily_news_pipeline import (
    DailyNewsPipeline,
    ScraperAgent,
    AnalyzerAgent,
    SummarizerAgent,
    TelegramSenderAgent
)

from .market_analysis_pipeline import (
    MarketAnalysisPipeline,
    MultiCategoryScraper,
    CategoryFocusAnalyzer
)

__all__ = [
    # Daily News Pipeline
    "DailyNewsPipeline",
    "ScraperAgent",
    "AnalyzerAgent",
    "SummarizerAgent",
    "TelegramSenderAgent",

    # Market Analysis Pipeline
    "MarketAnalysisPipeline",
    "MultiCategoryScraper",
    "CategoryFocusAnalyzer",
]
