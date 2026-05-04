import logging

from src.graph.state import AgentState

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


def route_after_multi_search(state: AgentState) -> str:
    """multi_search_node 후 라우팅.

    Returns:
        "multi_search_node": 재시도 (전체 빈 결과 + 재시도 한도 미초과)
        "sector_analyze_node": 분석 진행
    """
    total = sum(len(v) for v in state["sector_articles"].values())
    if total > 0:
        return "sector_analyze_node"
    if state["error_count"] < MAX_RETRIES:
        logger.warning("전체 검색 결과 없음 — 재시도 %d/%d", state["error_count"], MAX_RETRIES)
        return "multi_search_node"
    logger.error("최대 재시도 도달 — 빈 결과로 분석 진행")
    return "sector_analyze_node"
