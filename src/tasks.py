"""Task 팩토리 함수 — 뉴스 수집·분석 태스크 정의."""

from __future__ import annotations

from crewai import Task

from src.agents import make_analyst_agent, make_researcher_agent


def make_research_task(target_date: str, topic: str = "global financial markets") -> Task:
    """News_Researcher를 위한 뉴스 수집 태스크 생성.

    Args:
        target_date: 검색 기준 날짜 (ISO 형식, 예: '2026-05-04').
        topic: 검색 주제. 기본값은 'global financial markets'.

    Returns:
        설정된 CrewAI Task.
    """
    return Task(
        description=(
            f"{target_date} 기준으로 '{topic}'에 관한 주요 금융·부동산 뉴스를 검색하라. "
            "tavily_search 도구를 최소 3회 호출해 다음 영역을 커버할 것:\n"
            "1) 주식·채권 시장 동향\n"
            "2) 부동산 가격 및 거래량 지표\n"
            "3) 주요 기업 이벤트 또는 거시경제 발표\n"
            "모든 결과에 출처 URL을 포함할 것."
        ),
        expected_output=(
            "5~10개 뉴스 항목의 구조화된 목록. "
            "각 항목: 제목 / 한 문단 요약 / 발행일(가능하면) / 출처 URL."
        ),
        agent=make_researcher_agent(),
    )


def make_analysis_task(target_date: str) -> Task:
    """Financial_Analyst를 위한 분석 보고서 태스크 생성.

    Process.sequential 사용 시 앞 태스크 출력이 자동으로 컨텍스트로 전달된다.

    Args:
        target_date: 리서치 태스크와 동일한 날짜 (출력 파일명에 사용).

    Returns:
        Markdown 파일로 결과를 저장하는 CrewAI Task.
    """
    return Task(
        description=(
            f"{target_date} 뉴스 리서치 결과를 바탕으로 금융 분석 보고서를 작성하라. "
            "보고서는 정확히 다음 세 섹션을 포함해야 한다:\n"
            "1. 시장 전반 요약 (3~5문장)\n"
            "2. 핵심 시그널 (중요도 내림차순 불릿 목록)\n"
            "3. 모니터링 필요 리스크 (불릿 목록)\n"
            "리서치 입력에 없는 데이터는 절대 추가하지 말 것."
        ),
        expected_output=(
            "아래 세 헤더를 정확히 포함한 Markdown 문서:\n"
            "## Summary\n## Key Signals\n## Risk Factors"
        ),
        agent=make_analyst_agent(),
        output_file=f"output/analysis_{target_date}.md",
        # Process.sequential이므로 context 파라미터 불필요 — 앞 태스크 출력이 자동 전달됨
    )
