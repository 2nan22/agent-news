from langgraph.graph import END, StateGraph

from src.graph.edges import route_after_search
from src.graph.nodes import analyze_node, search_node
from src.graph.state import AgentState


def build_graph():
    """StateGraph 조립 및 컴파일.

    Returns:
        컴파일된 LangGraph (ainvoke 가능).
    """
    builder = StateGraph(AgentState)
    builder.add_node("search_node", search_node)
    builder.add_node("analyze_node", analyze_node)
    builder.set_entry_point("search_node")
    builder.add_conditional_edges(
        "search_node",
        route_after_search,
        {"search_node": "search_node", "analyze_node": "analyze_node"},
    )
    builder.add_edge("analyze_node", END)
    return builder.compile()
