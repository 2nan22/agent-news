from typing import TypedDict


class AgentState(TypedDict):
    query: str
    target_date: str
    topic: str
    articles: list[str]
    analysis: str
    error_count: int
