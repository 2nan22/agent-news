"""CrewAI tools — Tavily 웹 검색 래퍼."""

from __future__ import annotations

import logging
import os
from typing import Any

from crewai.tools import BaseTool
from tavily import TavilyClient

logger = logging.getLogger(__name__)

_MAX_RESULTS = 5
_MAX_SNIPPET_LEN = 400  # 결과 당 본문 최대 글자 수


class TavilySearchTool(BaseTool):
    """Tavily 웹 검색 도구.

    TAVILY_API_KEY를 인스턴스 생성 시점에 환경 변수에서 읽어
    agent/task 정의에 키가 노출되지 않도록 한다.
    """

    name: str = "tavily_search"
    description: str = (
        "최신 뉴스 및 금융 정보를 웹에서 검색한다. "
        "입력: 검색 쿼리 문자열. "
        "출력: 제목·본문 요약·출처 URL을 포함한 검색 결과 목록."
    )
    # Pydantic v2 모델 필드로 선언해야 __init__ 이후 할당이 가능하다.
    api_key: str = ""

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # super().__init__() 이후 Pydantic 필드 값을 주입하는 안전한 방법
        object.__setattr__(self, "api_key", os.environ.get("TAVILY_API_KEY", ""))
        if not self.api_key:
            logger.warning("TAVILY_API_KEY 미설정 — 검색 결과가 반환되지 않습니다")

    def _run(self, query: str) -> str:
        """Tavily 검색 실행 후 포맷팅된 스니펫 반환.

        Args:
            query: 자연어 검색 쿼리.

        Returns:
            포맷팅된 검색 결과 문자열. 실패 시 에러 메시지 반환.
        """
        if not self.api_key:
            return "검색 불가: TAVILY_API_KEY가 설정되지 않았습니다."

        try:
            client = TavilyClient(api_key=self.api_key)
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=_MAX_RESULTS,
                include_answer=False,
            )

            snippets: list[str] = []
            for result in response.get("results", []):
                title = result.get("title", "")
                content = result.get("content", "")[:_MAX_SNIPPET_LEN]
                url = result.get("url", "")
                snippets.append(f"[{title}]\n{content}\n출처: {url}")

            logger.info("Tavily 검색 완료 — query=%s results=%d", query, len(snippets))
            return "\n\n---\n\n".join(snippets) if snippets else "검색 결과 없음."

        except Exception as exc:
            logger.error("Tavily 검색 실패: %s", exc)
            return f"검색 오류: {exc}"
