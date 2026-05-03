"""Agent 팩토리 함수 — 뉴스 분석 크루의 에이전트 정의."""

from __future__ import annotations

import logging
import os

from crewai import Agent
from langchain_openai import ChatOpenAI

from src.tools import TavilySearchTool

logger = logging.getLogger(__name__)


def _make_llm() -> ChatOpenAI:
    """로컬 Ollama를 가리키는 ChatOpenAI 인스턴스 생성.

    Docker 환경: OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
    로컬 직접 실행: OLLAMA_BASE_URL=http://localhost:11434/v1

    Returns:
        Ollama 연결용 ChatOpenAI 클라이언트.
    """
    return ChatOpenAI(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",  # Ollama는 키 검증 안 함, 비어있으면 LangChain이 에러를 냄
        model=os.environ.get("OLLAMA_MODEL", "gemma4"),
        temperature=0.3,
    )


def make_researcher_agent() -> Agent:
    """News_Researcher 에이전트 생성.

    Tavily 검색 도구를 통해 지정 날짜의 금융/부동산 뉴스를 수집한다.

    Returns:
        검색 도구가 장착된 CrewAI Agent.
    """
    return Agent(
        role="News_Researcher",
        goal=(
            "지정된 날짜와 주제에 관련된 최신 금융·부동산 뉴스를 수집하고 "
            "출처와 함께 구조화된 목록으로 정리한다."
        ),
        backstory=(
            "10년 경력의 금융 전문 저널리스트. "
            "시장에 영향을 주는 뉴스를 빠르게 파악하고 항상 출처를 명시한다."
        ),
        tools=[TavilySearchTool()],
        llm=_make_llm(),
        verbose=True,
        max_iter=3,  # 무한 도구 호출 루프 방지
    )


def make_analyst_agent() -> Agent:
    """Financial_Analyst 에이전트 생성.

    수집된 뉴스를 바탕으로 투자자 관점의 구조화된 분석 보고서를 작성한다.

    Returns:
        분석 전용 CrewAI Agent (검색 도구 없음).
    """
    return Agent(
        role="Financial_Analyst",
        goal=(
            "뉴스 리서처가 수집한 정보를 바탕으로 "
            "핵심 시그널과 리스크 요인을 포함한 투자 분석 보고서를 작성한다."
        ),
        backstory=(
            "퀀트 헤지펀드의 시니어 애널리스트. "
            "노이즈를 제거하고 실행 가능한 인사이트만 추출하는 것이 강점이다."
        ),
        tools=[],  # 리서처 출력을 컨텍스트로 받아 분석만 수행
        llm=_make_llm(),
        verbose=True,
        max_iter=2,
    )
