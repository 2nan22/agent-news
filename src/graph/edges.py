import logging

from src.graph.state import AgentState

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def route_after_search(state: AgentState) -> str:
    """search_node 후 라우팅 결정.

    Returns:
        "search_node": 재시도 (빈 결과 + 재시도 한도 미초과)
        "analyze_node": 분석 진행 (정상 결과 or 재시도 한도 초과)
    """
    if state["articles"]:
        return "analyze_node"
    if state["error_count"] < MAX_RETRIES:
        logger.warning("검색 결과 없음 — 재시도 %d/%d", state["error_count"], MAX_RETRIES)
        return "search_node"
    logger.error("최대 재시도 도달 — 빈 결과로 분석 진행")
    return "analyze_node"
