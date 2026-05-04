"""CrewAI 엔진으로 섹터별 순차 분석 실행."""
import logging
import os

from crewai import Agent, Crew, Process, Task
from crewai import LLM

from src.graph.keywords import build_query

logger = logging.getLogger(__name__)


def _make_llm() -> LLM:
    return LLM(
        model=f"openai/{os.environ.get('OLLAMA_MODEL', 'gemma4')}",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
        temperature=0.3,
    )


def run_crewai(
    target_date: str,
    market: str,
    sectors: list[str],
    watchlist_companies: list[str],
) -> dict:
    """섹터별 CrewAI 실행 후 결과 집계."""
    from crewai_tools import TavilySearchTool

    llm = _make_llm()
    tavily_tool = TavilySearchTool()
    sector_analyses: dict[str, str] = {}

    researcher = Agent(
        role="News_Researcher",
        goal="지정 섹터의 금융 뉴스를 수집한다",
        backstory="10년 경력 금융 저널리스트",
        tools=[tavily_tool],
        llm=llm,
        max_iter=3,
    )
    analyst = Agent(
        role="Financial_Analyst",
        goal="수집 뉴스를 분석하여 투자 보고서를 작성한다",
        backstory="선임 퀀트 애널리스트",
        llm=llm,
        max_iter=2,
    )

    all_sectors = sectors + [f"WATCHLIST:{t}" for t in watchlist_companies]
    for sector in all_sectors:
        query = build_query(sector, market, target_date)
        research_task = Task(
            description=f"Tavily로 다음 쿼리를 검색하라: '{query}'. 결과 5건을 정리하라.",
            expected_output="제목·요약·출처 URL 포함 5건의 뉴스 항목",
            agent=researcher,
        )
        analysis_task = Task(
            description=f"{target_date} 기준 {sector} 분석 보고서를 ## Summary / ## Key Signals / ## Risk Factors 세 섹션으로 작성하라.",
            expected_output="세 섹션이 포함된 마크다운 보고서",
            agent=analyst,
            context=[research_task],
        )
        crew = Crew(
            agents=[researcher, analyst],
            tasks=[research_task, analysis_task],
            process=Process.sequential,
            verbose=False,
        )
        result = crew.kickoff()
        sector_analyses[sector] = str(result)
        logger.info("CrewAI 섹터 '%s' 완료", sector)

    overall = f"{target_date} {market} 멀티-섹터 분석 완료 ({len(sector_analyses)}개 섹터)"
    return {"sector_analyses": sector_analyses, "overall_analysis": overall}
