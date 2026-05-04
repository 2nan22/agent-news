import asyncio
import logging
import os

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tavily import TavilyClient

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


async def search_node(state: AgentState) -> dict:
    """Tavily 뉴스 검색. 실패·빈 결과 시 error_count 증가."""
    query = f"{state['topic']} {state['target_date']} financial news"
    try:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        resp = await asyncio.to_thread(
            client.search, query=query, max_results=5, search_depth="basic"
        )
        articles = [
            f"[{r.get('title', '')}]\n{r.get('content', '')[:400]}\n출처: {r.get('url', '')}"
            for r in resp.get("results", [])
        ]
        if not articles:
            return {"articles": [], "error_count": state["error_count"] + 1}
        return {"articles": articles, "error_count": 0}
    except Exception as exc:
        logger.error("search_node 실패: %s", exc)
        return {"articles": [], "error_count": state["error_count"] + 1}


async def analyze_node(state: AgentState) -> dict:
    """ChatOpenAI로 수집 기사 분석 보고서 생성."""
    llm = _make_llm()
    articles_text = (
        "\n\n---\n\n".join(state["articles"])
        if state["articles"]
        else "검색 결과를 가져오지 못했습니다."
    )
    prompt = f"""다음 뉴스 기사를 바탕으로 {state['target_date']} 기준 금융 분석 보고서를 작성하라.
정확히 세 섹션을 포함할 것: ## Summary / ## Key Signals / ## Risk Factors

[뉴스 기사]
{articles_text}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"analysis": response.content}
