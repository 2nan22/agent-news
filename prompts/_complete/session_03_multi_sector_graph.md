# Session 03: 멀티-섹터 한/미 뉴스 분석 그래프 확장 + DB 스키마 설계

> **Session Goal**: LangGraph 그래프를 한국/미국 시장·섹터별·워치리스트 기업 분석으로 확장.  
> CrewAI도 동일한 CLI로 전환 가능한 `--engine` 공통 인터페이스 구성.  
> PostgreSQL 스키마 DDL 파일 작성 (Session 04 oreneo 통합 전 설계 완료).
> **Branch**: `feat/multi-sector-graph` (from dev)
> **예상 소요**: 2 ~ 2.5시간
> **전제 조건**: Session 02 완료 (LangGraph 단일 주제 분석, `src/graph/` 패키지 존재)

---

## 세션 시작 전 주입

```
Read .claude/rules/git_workflow.md
Read .claude/rules/architecture.md
Read src/graph/state.py
Read src/graph/nodes.py
Read src/graph/edges.py
Read src/graph/builder.py
Read graph_agent.py
```

---

## 배경 및 목표

Session 02의 그래프는 `topic` 하나를 단일 Tavily 검색에 넣고 전체 분석을 한 번에 수행한다.
이번 세션에서는:

1. **시장 구분**: `--market KR | US | ALL` 으로 한국/미국 뉴스를 분리 수집
2. **섹터별 분석**: 반도체·AI·조선·원자재·에너지·금융 각각에 맞는 키워드로 Tavily 검색 → 섹터별 분석 보고서 생성
3. **워치리스트**: `--watchlist 005930 NVDA` 지정 시 해당 종목 추가 검색
4. **엔진 전환**: `--engine langgraph | crewai` 파라미터로 동일한 입력에 대해 두 엔진 결과 비교 가능

### 최종 파일 구조

```
2026_AI-Agent/
├── src/
│   ├── graph/
│   │   ├── keywords.py   ← (신규) KR/US 섹터 키워드 상수
│   │   ├── state.py      ← AgentState v2 (market, sectors, watchlist, sector_articles, sector_analyses, overall_analysis)
│   │   ├── nodes.py      ← multi_search_node, sector_analyze_node, aggregate_node
│   │   ├── edges.py      ← route_after_multi_search
│   │   └── builder.py    ← 새 토폴로지 (search → analyze → aggregate)
│   └── crew/
│       ├── __init__.py   ← (신규)
│       ├── agents.py     ← (신규) researcher, analyst 팩토리
│       └── runner.py     ← (신규) run_crewai(config) — 섹터별 crew 루프
├── graph_agent.py        ← v2: --engine / --market / --sectors / --watchlist
└── migrations/
    └── 001_initial_schema.sql  ← (신규) PostgreSQL 전체 DDL
```

### 그래프 토폴로지 변경

```
v1 (Session 02)
START → search_node → analyze_node → END

v2 (Session 03)
START
  │
  ▼
multi_search_node ─── (results) ──► sector_analyze_node ──► aggregate_node ──► END
      ▲
      └── (empty + retry < 2)
```

---

## 꼭지 1: 섹터 키워드 상수 파일

**작업:** `src/graph/keywords.py` 신규 생성

```python
# src/graph/keywords.py
"""섹터별 Tavily 검색 키워드 상수.

향후 TBL_MARKET_SECTOR.search_keywords_ko / _en 컬럼으로 DB 이전 가능.
"""

KR_SECTOR_KEYWORDS: dict[str, str] = {
    "반도체": "반도체 DRAM 낸드 삼성전자 SK하이닉스 코스피",
    "AI":     "AI 인공지능 네이버 카카오 LG AI연구원",
    "조선":   "조선 해운 현대중공업 삼성중공업 한화오션",
    "원자재": "원자재 철강 포스코 구리 리튬 배터리소재",
    "에너지": "에너지 한국전력 SK에너지 발전 원전",
    "금융":   "금융 은행 KB 신한 하나 증시",
}

US_SECTOR_KEYWORDS: dict[str, str] = {
    "반도체": "semiconductor chip TSMC NVIDIA AMD Intel",
    "AI":     "AI artificial intelligence OpenAI Google Microsoft",
    "조선":   "shipbuilding maritime shipping",
    "원자재": "raw materials steel copper lithium commodities",
    "에너지": "energy oil gas Exxon Chevron renewables",
    "금융":   "finance banking JPMorgan Goldman Fed interest rate",
}

DEFAULT_SECTORS: list[str] = list(KR_SECTOR_KEYWORDS.keys())


def get_keyword(sector: str, market: str) -> str:
    """시장별 섹터 키워드 반환. 등록되지 않은 섹터는 이름 그대로 사용."""
    if market == "US":
        return US_SECTOR_KEYWORDS.get(sector, sector)
    return KR_SECTOR_KEYWORDS.get(sector, sector)


def build_query(sector: str, market: str, target_date: str) -> str:
    """Tavily 검색 쿼리 조립."""
    keyword = get_keyword(sector, market)
    if market == "US":
        return f"{keyword} news {target_date}"
    return f"{keyword} 뉴스 {target_date}"
```

**완료 기준:**
- [ ] `python -c "from src.graph.keywords import DEFAULT_SECTORS, build_query; print(build_query('반도체','KR','2026-05-04'))"` 출력

**커밋:**
```
feat(graph): add sector keyword constants for KR/US markets
```

---

## 꼭지 2: AgentState v2

**작업:** `src/graph/state.py` 수정

```python
# src/graph/state.py
from typing import TypedDict


class AgentState(TypedDict):
    target_date: str
    market: str                        # "KR" | "US" | "ALL"
    sectors: list[str]                 # 분석할 섹터 목록
    watchlist_companies: list[str]     # 옵셔널 티커 목록 (["005930", "NVDA"])
    sector_articles: dict[str, list[str]]  # sector → articles (WATCHLIST:TICKER도 포함)
    sector_analyses: dict[str, str]        # sector → analysis markdown
    overall_analysis: str              # aggregate_node 최종 요약
    error_count: int
```

**완료 기준:**
- [ ] `python -c "from src.graph.state import AgentState; print('ok')"` 통과

**커밋:**
```
feat(graph): AgentState v2 with market, sectors, watchlist, sector_analyses fields
```

---

## 꼭지 3: 노드 구현 (multi_search / sector_analyze / aggregate)

**작업:** `src/graph/nodes.py` 전면 교체

```python
# src/graph/nodes.py
import asyncio
import logging
import os

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tavily import TavilyClient

from src.graph.keywords import build_query
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


def _make_client() -> TavilyClient:
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def _format_articles(results: list[dict]) -> list[str]:
    return [
        f"[{r.get('title', '')}]\n{r.get('content', '')[:400]}\n출처: {r.get('url', '')}"
        for r in results
    ]


async def _search_sector(sector: str, market: str, target_date: str) -> list[str]:
    """단일 섹터 Tavily 검색. 실패 시 빈 리스트 반환."""
    query = build_query(sector, market, target_date)
    try:
        client = _make_client()
        resp = await asyncio.to_thread(
            client.search, query=query, max_results=5, search_depth="basic"
        )
        return _format_articles(resp.get("results", []))
    except Exception as exc:
        logger.error("섹터 '%s' 검색 실패: %s", sector, exc)
        return []


async def multi_search_node(state: AgentState) -> dict:
    """섹터별 + 워치리스트 Tavily 검색. 전체 빈 결과 시 error_count 증가."""
    market = state["market"]
    sector_articles: dict[str, list[str]] = {}

    # 섹터 검색 (KR이면 KR 키워드, US면 US, ALL이면 두 번 합산)
    search_markets = ["KR", "US"] if market == "ALL" else [market]
    for sector in state["sectors"]:
        merged: list[str] = []
        for m in search_markets:
            merged.extend(await _search_sector(sector, m, state["target_date"]))
        sector_articles[sector] = merged

    # 워치리스트 검색
    for ticker in state.get("watchlist_companies", []):
        query = (
            f"{ticker} 주가 뉴스 {state['target_date']}"
            if market != "US"
            else f"{ticker} stock news {state['target_date']}"
        )
        try:
            client = _make_client()
            resp = await asyncio.to_thread(
                client.search, query=query, max_results=3, search_depth="basic"
            )
            sector_articles[f"WATCHLIST:{ticker}"] = _format_articles(resp.get("results", []))
        except Exception as exc:
            logger.error("워치리스트 '%s' 검색 실패: %s", ticker, exc)
            sector_articles[f"WATCHLIST:{ticker}"] = []

    total = sum(len(v) for v in sector_articles.values())
    if total == 0:
        return {"sector_articles": sector_articles, "error_count": state["error_count"] + 1}
    return {"sector_articles": sector_articles, "error_count": 0}


async def sector_analyze_node(state: AgentState) -> dict:
    """섹터별 ChatOpenAI 분석 보고서 생성."""
    llm = _make_llm()
    sector_analyses: dict[str, str] = {}

    for sector, articles in state["sector_articles"].items():
        articles_text = (
            "\n\n---\n\n".join(articles) if articles else "검색 결과를 가져오지 못했습니다."
        )
        prompt = f"""다음은 {state['target_date']} 기준 [{sector}] 섹터의 뉴스 기사다.
금융 분석 보고서를 정확히 세 섹션으로 작성하라: ## Summary / ## Key Signals / ## Risk Factors

[뉴스 기사]
{articles_text}
"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        sector_analyses[sector] = response.content

    return {"sector_analyses": sector_analyses}


async def aggregate_node(state: AgentState) -> dict:
    """섹터별 분석을 종합하여 전체 시장 요약 생성."""
    llm = _make_llm()
    sector_summaries = "\n\n".join(
        f"### {sector}\n{analysis[:600]}"
        for sector, analysis in state["sector_analyses"].items()
    )
    prompt = f"""{state['target_date']} 기준 {state['market']} 시장 멀티-섹터 종합 요약을 3-5문장으로 작성하라.
아래 섹터별 분석을 바탕으로 전체 시장의 핵심 흐름과 주요 리스크를 제시하라.

{sector_summaries}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"overall_analysis": response.content}
```

**완료 기준:**
- [ ] `python -c "from src.graph.nodes import multi_search_node, sector_analyze_node, aggregate_node; print('ok')"` 통과

**커밋:**
```
feat(graph): multi_search_node, sector_analyze_node, aggregate_node
```

---

## 꼭지 4: 조건부 엣지 + 그래프 빌더 v2

**작업:** `src/graph/edges.py` 수정

```python
# src/graph/edges.py
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
```

**작업:** `src/graph/builder.py` 수정

```python
# src/graph/builder.py
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
```

**완료 기준:**
- [ ] `python -c "from src.graph.builder import build_graph; g = build_graph(); print(type(g))"` → `CompiledStateGraph`
- [ ] `route_after_multi_search` 단위 테스트:
  ```python
  python -c "
  from src.graph.edges import route_after_multi_search
  print(route_after_multi_search({'sector_articles': {}, 'error_count': 0}))         # multi_search_node
  print(route_after_multi_search({'sector_articles': {}, 'error_count': 2}))         # sector_analyze_node
  print(route_after_multi_search({'sector_articles': {'반도체': ['a']}, 'error_count': 0}))  # sector_analyze_node
  "
  ```

**커밋:**
```
feat(graph): multi-sector edges and builder v2
```

---

## 꼭지 5: graph_agent.py v2 + CrewAI 멀티섹터

**작업 A:** `graph_agent.py` v2 — `--engine / --market / --sectors / --watchlist`

```python
# graph_agent.py (80줄 이내)
import argparse
import asyncio
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.graph.builder import build_graph
from src.graph.keywords import DEFAULT_SECTORS
from src.graph.state import AgentState

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="뉴스 분석 CLI")
    parser.add_argument("--engine", choices=["langgraph", "crewai"], default="langgraph")
    parser.add_argument("--market", choices=["KR", "US", "ALL"], default="KR")
    parser.add_argument("--sectors", nargs="+", default=None, help="분석 섹터 (기본: 전체)")
    parser.add_argument("--watchlist", nargs="*", default=[], help="종목 티커 (예: 005930 NVDA)")
    parser.add_argument("--date", default=str(date.today()), help="분석 기준 날짜 (YYYY-MM-DD)")
    return parser.parse_args()


async def _run_langgraph(args: argparse.Namespace) -> dict:
    """LangGraph 엔진 실행."""
    graph = build_graph()
    initial_state: AgentState = {
        "target_date": args.date,
        "market": args.market,
        "sectors": args.sectors or DEFAULT_SECTORS,
        "watchlist_companies": args.watchlist,
        "sector_articles": {},
        "sector_analyses": {},
        "overall_analysis": "",
        "error_count": 0,
    }
    return await graph.ainvoke(initial_state)


def _run_crewai(args: argparse.Namespace) -> dict:
    """CrewAI 엔진 실행."""
    from src.crew.runner import run_crewai
    return run_crewai(
        target_date=args.date,
        market=args.market,
        sectors=args.sectors or DEFAULT_SECTORS,
        watchlist_companies=args.watchlist,
    )


async def main() -> None:
    args = _parse_args()
    Path("output").mkdir(exist_ok=True)
    sectors = args.sectors or DEFAULT_SECTORS

    if args.engine == "langgraph":
        result = await _run_langgraph(args)
    else:
        result = await asyncio.to_thread(_run_crewai, args)

    # 출력 파일 구성
    sector_tag = "-".join(sectors[:3]) + ("..." if len(sectors) > 3 else "")
    output_path = Path(f"output/analysis_{args.engine}_{args.market}_{args.date}.md")
    content = _build_report(args, result)
    output_path.write_text(content, encoding="utf-8")
    logger.info("분석 완료 [%s] — 결과: %s", args.engine, output_path)
    print("\n" + "=" * 60)
    print(content)
    print("=" * 60 + "\n")


def _build_report(args: argparse.Namespace, result: dict) -> str:
    """결과 dict → 마크다운 보고서 문자열."""
    header = f"# 뉴스 분석 보고서 [{args.market}] — {args.date} ({args.engine})\n\n"
    overall = f"## 전체 시장 요약\n\n{result.get('overall_analysis', '')}\n\n---\n\n"
    sectors_md = ""
    for sector, analysis in result.get("sector_analyses", {}).items():
        sectors_md += f"## {sector}\n\n{analysis}\n\n---\n\n"
    return header + overall + sectors_md


if __name__ == "__main__":
    asyncio.run(main())
```

**작업 B:** `src/crew/` CrewAI 멀티섹터 구현

```python
# src/crew/__init__.py  (빈 파일)

# src/crew/runner.py
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

    # 섹터별 독립 Crew 실행
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
```

**완료 기준:**
- [ ] LangGraph: `python graph_agent.py --engine langgraph --market KR --sectors 반도체 AI --date 2026-05-04` 정상 실행, `output/analysis_langgraph_KR_2026-05-04.md` 생성
- [ ] CrewAI: `python graph_agent.py --engine crewai --market KR --sectors 반도체 --date 2026-05-04` 정상 실행
- [ ] 출력 파일에 섹터별 분석 섹션 포함

**커밋:**
```
feat(agent): graph_agent.py v2 with --engine --market --sectors --watchlist
feat(crew): multi-sector CrewAI runner in src/crew/
```

---

## 꼭지 6: PostgreSQL DDL 파일 작성

**작업:** `migrations/001_initial_schema.sql` 신규 생성

```sql
-- migrations/001_initial_schema.sql
-- PostgreSQL 16+ 기준
-- 명명 규칙: TBL_{도메인}_{엔티티}, snake_case 컬럼, id BIGSERIAL PK

BEGIN;

-- ───────────────────────────────────────────
-- 섹터 마스터
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_MARKET_SECTOR" (
    id              BIGSERIAL       PRIMARY KEY,
    sector_code     VARCHAR(30)     UNIQUE NOT NULL,  -- SEMICONDUCTOR, AI, SHIPBUILDING, ...
    sector_name_ko  VARCHAR(50)     NOT NULL,
    sector_name_en  VARCHAR(50)     NOT NULL,
    market          VARCHAR(5)      NOT NULL,          -- KR / US / ALL
    display_order   INT             DEFAULT 0,
    is_active       BOOLEAN         DEFAULT TRUE,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- ───────────────────────────────────────────
-- 회사 마스터
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_MARKET_COMPANY" (
    id               BIGSERIAL       PRIMARY KEY,
    ticker           VARCHAR(20)     UNIQUE NOT NULL,   -- 005930, NVDA
    company_name_ko  VARCHAR(100),
    company_name_en  VARCHAR(100)    NOT NULL,
    market           VARCHAR(5)      NOT NULL,          -- KR / US
    exchange         VARCHAR(20),                       -- KOSPI, KOSDAQ, NYSE, NASDAQ
    sector_id        BIGINT          REFERENCES "TBL_MARKET_SECTOR"(id),
    is_active        BOOLEAN         DEFAULT TRUE,
    created_at       TIMESTAMPTZ     DEFAULT NOW(),
    updated_at       TIMESTAMPTZ     DEFAULT NOW()
);

-- ───────────────────────────────────────────
-- 뉴스 원문
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_NEWS_ARTICLE" (
    id           BIGSERIAL       PRIMARY KEY,
    article_url  TEXT            UNIQUE NOT NULL,
    title        TEXT            NOT NULL,
    content      TEXT,
    source_name  VARCHAR(100),
    published_at TIMESTAMPTZ,
    market       VARCHAR(5),                            -- KR / US
    language     VARCHAR(5)      DEFAULT 'ko',          -- ko / en
    raw_data     JSONB,                                 -- Tavily 원본 응답
    created_at   TIMESTAMPTZ     DEFAULT NOW(),
    updated_at   TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_article_market ON "TBL_NEWS_ARTICLE" (market);
CREATE INDEX IF NOT EXISTS idx_news_article_published_at ON "TBL_NEWS_ARTICLE" (published_at DESC);

-- ───────────────────────────────────────────
-- 기사-섹터 매핑 (M:N)
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_NEWS_ARTICLE_SECTOR" (
    id               BIGSERIAL   PRIMARY KEY,
    article_id       BIGINT      NOT NULL REFERENCES "TBL_NEWS_ARTICLE"(id) ON DELETE CASCADE,
    sector_id        BIGINT      NOT NULL REFERENCES "TBL_MARKET_SECTOR"(id),
    relevance_score  FLOAT,                             -- 0.0 ~ 1.0
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (article_id, sector_id)
);

-- ───────────────────────────────────────────
-- 분석 헤더 (1회 실행 = 1 row)
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_NEWS_ANALYSIS" (
    id               BIGSERIAL   PRIMARY KEY,
    analysis_date    DATE        NOT NULL,
    market           VARCHAR(5)  NOT NULL,              -- KR / US / ALL
    engine_type      VARCHAR(20) DEFAULT 'langgraph',   -- langgraph / crewai
    run_status       VARCHAR(20) DEFAULT 'PENDING',     -- PENDING / RUNNING / COMPLETED / FAILED
    overall_analysis TEXT,
    raw_result       JSONB,                             -- sector_analyses 전체
    run_duration_ms  INT,
    error_message    TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (analysis_date, market, engine_type)
);

-- ───────────────────────────────────────────
-- 섹터별 분석 결과 (1:N from TBL_NEWS_ANALYSIS)
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_NEWS_SECTOR_ANALYSIS" (
    id              BIGSERIAL   PRIMARY KEY,
    analysis_id     BIGINT      NOT NULL REFERENCES "TBL_NEWS_ANALYSIS"(id) ON DELETE CASCADE,
    sector_id       BIGINT      NOT NULL REFERENCES "TBL_MARKET_SECTOR"(id),
    analysis_text   TEXT,                              -- ## Summary / ## Key Signals / ## Risk Factors
    article_count   INT         DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (analysis_id, sector_id)
);

-- ───────────────────────────────────────────
-- 사용자 워치리스트 (Session 04에서 user_id FK 연결)
-- ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "TBL_USER_WATCHLIST" (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         BIGINT,                            -- nullable: oreneo 연동 시 FK 추가
    watchlist_type  VARCHAR(20) NOT NULL,              -- SECTOR / COMPANY
    sector_id       BIGINT      REFERENCES "TBL_MARKET_SECTOR"(id),
    company_id      BIGINT      REFERENCES "TBL_MARKET_COMPANY"(id),
    is_active       BOOLEAN     DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_watchlist_target CHECK (
        (watchlist_type = 'SECTOR' AND sector_id IS NOT NULL AND company_id IS NULL)
        OR
        (watchlist_type = 'COMPANY' AND company_id IS NOT NULL AND sector_id IS NULL)
    )
);

-- ───────────────────────────────────────────
-- 기본 섹터 데이터 seed
-- ───────────────────────────────────────────
INSERT INTO "TBL_MARKET_SECTOR" (sector_code, sector_name_ko, sector_name_en, market, display_order)
VALUES
    ('SEMICONDUCTOR', '반도체',  'Semiconductor', 'KR', 1),
    ('AI',            'AI',      'Artificial Intelligence', 'ALL', 2),
    ('SHIPBUILDING',  '조선',    'Shipbuilding', 'KR', 3),
    ('RAW_MATERIALS', '원자재',  'Raw Materials', 'ALL', 4),
    ('ENERGY',        '에너지',  'Energy', 'ALL', 5),
    ('FINANCE',       '금융',    'Finance', 'ALL', 6)
ON CONFLICT (sector_code) DO NOTHING;

COMMIT;
```

**완료 기준:**
- [ ] `docker run --rm -e POSTGRES_PASSWORD=test postgres:16 psql -U postgres -c "CREATE DATABASE test_schema;"` (postgres 컨테이너 기동 확인)
- [ ] DDL 구문 오류 없음 (실제 적용은 Session 04에서 oreneo DB에 수행)

**커밋:**
```
feat(db): add PostgreSQL DDL migrations/001_initial_schema.sql
```

---

## 세션 종료

```bash
# PR 생성
git push origin feat/multi-sector-graph
gh pr create \
  --base dev \
  --title "[feat] Multi-sector KR/US news analysis with --engine switch" \
  --body "$(cat <<'EOF'
## Overview
LangGraph 그래프를 멀티-섹터·한/미 시장·워치리스트 분석으로 확장.
CrewAI와 공통 CLI 인터페이스(--engine) 구성.

## Changes
- `src/graph/keywords.py`: KR/US 섹터 키워드 상수
- `src/graph/state.py`: AgentState v2
- `src/graph/nodes.py`: multi_search_node, sector_analyze_node, aggregate_node
- `src/graph/edges.py`: route_after_multi_search
- `src/graph/builder.py`: 새 그래프 토폴로지
- `src/crew/runner.py`: CrewAI 멀티섹터 러너
- `graph_agent.py`: --engine / --market / --sectors / --watchlist CLI
- `migrations/001_initial_schema.sql`: PostgreSQL 7개 테이블 DDL

## Test Plan
- [ ] `--engine langgraph --market KR --sectors 반도체 AI` 실행 후 파일 생성
- [ ] `--engine crewai --market KR --sectors 반도체` 실행
- [ ] `--market ALL` 시 KR+US 키워드 혼합 검색
- [ ] `TAVILY_API_KEY=""` 시 재시도 2회 후 빈 결과로 완료
EOF
)"

gh pr merge --merge --delete-branch

# 세션 파일 아카이브
mv prompts/session_03_multi_sector_graph.md prompts/_complete/
```

> **다음 세션**: session_04 — `2026_oreneo` 프로젝트 FastAPI 라우터 + Django 모델 + Celery 통합

---

## 참고: 엔진 비교

| 관점 | LangGraph (기본) | CrewAI |
|------|-----------------|--------|
| 검색 제어 | 코드가 직접 Tavily 호출 | 에이전트가 툴 선택 (환각 위험) |
| 섹터 순회 | for-loop (예측 가능) | 에이전트 판단 (비결정적) |
| 재시도 | 조건부 엣지로 정밀 제어 | max_iter 한도만 |
| async | ainvoke 지원 | 미지원 |
| 출력 보장 | 노드 코드로 강제 가능 | 프롬프트 유도만 |
| 추천 용도 | 프로덕션 예약 분석 | 탐색적/비교 실험 |

## 참고: 트러블슈팅

| 문제 | 해결 |
|------|------|
| ALL 시장에서 결과 누락 | `search_markets = ["KR", "US"]` 루프 확인 |
| CrewAI 섹터 환각 | `verbose=True`로 툴 호출 추적, `max_iter` 줄이기 |
| 섹터별 LLM 호출 타임아웃 | OLLAMA_MODEL을 경량 모델(qwen2.5:7b)로 교체 |
| `graph_agent.py` 80줄 초과 | `_build_report` 를 `src/graph/report.py`로 분리 |
