from langgraph.graph import END, StateGraph

from src.graph.edges import route_after_multi_search
from src.graph.nodes import aggregate_node, multi_search_node, sector_analyze_node
from src.graph.state import AgentState


def build_graph():
    """멀티-섹터 StateGraph 조립 및 컴파일."""
    builder = StateGraph(AgentState)
    builder.add_node("multi_search_node", multi_search_node)
    builder.add_node("sector_analyze_node", sector_analyze_node)
    builder.add_node("aggregate_node", aggregate_node)
    builder.set_entry_point("multi_search_node")
    builder.add_conditional_edges(
        "multi_search_node",
        route_after_multi_search,
        {
            "multi_search_node": "multi_search_node",
            "sector_analyze_node": "sector_analyze_node",
        },
    )
    builder.add_edge("sector_analyze_node", "aggregate_node")
    builder.add_edge("aggregate_node", END)
    return builder.compile()
