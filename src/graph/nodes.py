import asyncio
import logging
import os

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tavily import TavilyClient

from src.graph.keywords import build_query
from src.graph.state import AgentState

logger = logging.getLogger(__name__)


def _make_llm() -> ChatOpenAI:
    """ChatOpenAI 인스턴스 생성 (환경변수에서 설정 로드)."""
    return ChatOpenAI(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
        model=os.environ.get("OLLAMA_MODEL", "gemma4"),
        temperature=0.3,
    )


def _make_client() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def _format_articles(results: list[dict]) -> list[str]:
    return [
        f"[{r.get('title', '')}]\n{r.get('content', '')[:400]}\n출처: {r.get('url', '')}"
        for r in results
    ]


async def _search_sector(sector: str, market: str, target_date: str) -> list[str]:
    """단일 섹터 Tavily 검색. 실패 시 빈 리스트 반환."""
    query = build_query(sector, market, target_date)
    try:
        client = _make_client()
        resp = await asyncio.to_thread(
            client.search, query=query, max_results=5, search_depth="basic"
        )
        return _format_articles(resp.get("results", []))
    except Exception as exc:
        logger.error("섹터 '%s' 검색 실패: %s", sector, exc)
        return []


async def multi_search_node(state: AgentState) -> dict:
    """섹터별 + 워치리스트 Tavily 검색. 전체 빈 결과 시 error_count 증가."""
    market = state["market"]
    sector_articles: dict[str, list[str]] = {}

    search_markets = ["KR", "US"] if market == "ALL" else [market]
    for sector in state["sectors"]:
        merged: list[str] = []
        for m in search_markets:
            merged.extend(await _search_sector(sector, m, state["target_date"]))
        sector_articles[sector] = merged

    for ticker in state.get("watchlist_companies", []):
        query = (
            f"{ticker} 주가 뉴스 {state['target_date']}"
            if market != "US"
            else f"{ticker} stock news {state['target_date']}"
        )
        try:
            client = _make_client()
            resp = await asyncio.to_thread(
                client.search, query=query, max_results=3, search_depth="basic"
            )
            sector_articles[f"WATCHLIST:{ticker}"] = _format_articles(resp.get("results", []))
        except Exception as exc:
            logger.error("워치리스트 '%s' 검색 실패: %s", ticker, exc)
            sector_articles[f"WATCHLIST:{ticker}"] = []

    total = sum(len(v) for v in sector_articles.values())
    if total == 0:
        return {"sector_articles": sector_articles, "error_count": state["error_count"] + 1}
    return {"sector_articles": sector_articles, "error_count": 0}


async def sector_analyze_node(state: AgentState) -> dict:
    """섹터별 ChatOpenAI 분석 보고서 생성."""
    llm = _make_llm()
    sector_analyses: dict[str, str] = {}

    for sector, articles in state["sector_articles"].items():
        articles_text = (
            "\n\n---\n\n".join(articles) if articles else "검색 결과를 가져오지 못했습니다."
        )
        prompt = f"""다음은 {state['target_date']} 기준 [{sector}] 섹터의 뉴스 기사다.
금융 분석 보고서를 정확히 세 섹션으로 작성하라: ## Summary / ## Key Signals / ## Risk Factors

[뉴스 기사]
{articles_text}
"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        sector_analyses[sector] = response.content

    return {"sector_analyses": sector_analyses}


async def aggregate_node(state: AgentState) -> dict:
    """섹터별 분석을 종합하여 전체 시장 요약 생성."""
    llm = _make_llm()
    sector_summaries = "\n\n".join(
        f"### {sector}\n{analysis[:600]}"
        for sector, analysis in state["sector_analyses"].items()
    )
    prompt = f"""{state['target_date']} 기준 {state['market']} 시장 멀티-섹터 종합 요약을 3-5문장으로 작성하라.
아래 섹터별 분석을 바탕으로 전체 시장의 핵심 흐름과 주요 리스크를 제시하라.

{sector_summaries}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"overall_analysis": response.content}
