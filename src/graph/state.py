from typing import TypedDict


class AgentState(TypedDict):
    target_date: str
    market: str                          # "KR" | "US" | "ALL"
    sectors: list[str]                   # 분석할 섹터 목록
    watchlist_companies: list[str]       # 옵셔널 티커 목록 (["005930", "NVDA"])
    sector_articles: dict[str, list[str]]    # sector → articles (WATCHLIST:TICKER도 포함)
    sector_analyses: dict[str, str]          # sector → analysis markdown
    overall_analysis: str                # aggregate_node 최종 요약
    error_count: int
