# Session 02: LangGraph 하네스 엔지니어링 — 상태 기반 뉴스 분석 그래프

> **Session Goal**: CrewAI 방식의 에이전트 자율성 대신, LangGraph로 흐름을 명확히 통제하는 하네스(Harness) 엔지니어링 패턴으로 동일한 뉴스 분석 시스템을 재구현
> **Branch**: `feat/langgraph-agent` (from dev)
> **예상 소요**: 2 ~ 2.5시간
> **전제 조건**: Session 01 완료 (M1 병합, Docker E2E 검증 완료)

---

## 세션 시작 전 주입

```
Read .claude/rules/git_workflow.md
Read .claude/rules/architecture.md
Read crew_agent.py
Read src/agents.py
```

---

## 배경 및 목표

Session 01에서 CrewAI로 만든 뉴스 분석 시스템은 에이전트가 알아서 흐름을 결정한다.
이번에는 **LangGraph의 StateGraph**를 사용해, 개발자가 노드(Node)와 엣지(Edge)를 명시적으로 정의하고 조건부 라우팅(Conditional Edge)으로 재시도 로직까지 통제하는 방식으로 재구현한다.

### CrewAI vs LangGraph 비교

| 관점 | Session 01 (CrewAI) | Session 02 (LangGraph) |
|------|---------------------|------------------------|
| 흐름 제어 | 에이전트가 자율 결정 | 개발자가 Graph로 명시 |
| 상태 관리 | 암묵적 (CrewAI 내부) | 명시적 (`TypedDict`) |
| 재시도 | 에이전트 max_iter | 조건부 엣지 라우팅 |
| LLM 연결 | `crewai.LLM(model="openai/...")` | `ChatOpenAI(base_url=...)` 직접 |
| 비동기 | 불가 | `ainvoke` + `asyncio` |

> **주의**: LangGraph는 LangChain 네이티브라 `ChatOpenAI`를 그대로 사용할 수 있다.
> CrewAI에서 litellm 프리픽스(`openai/`) 문제는 여기서 발생하지 않는다.

### 최종 그래프 구조

```
START
  │
  ▼
search_node ──── (articles 있음) ────► analyze_node ──► END
     ▲                                       
     │ (articles 없음 AND error_count < 2)  
     └────────────────────────────────────── (retry)
     
     (articles 없음 AND error_count >= 2) → analyze_node (빈 결과로 진행)
```

### 최종 파일 구조

```
2026_AI-Agent/
├── src/
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py      ← AgentState TypedDict
│   │   ├── nodes.py      ← search_node, analyze_node (async)
│   │   ├── edges.py      ← route_after_search() 조건부 라우터
│   │   └── builder.py    ← build_graph() → CompiledStateGraph
│   └── (기존 src/ 파일 유지)
├── graph_agent.py         ← asyncio CLI 진입점 (신규)
└── requirements.txt       ← langgraph, langchain-community 추가
```

---

## 꼭지 1: 의존성 추가 + src/graph/ 패키지 스켈레톤

**작업:**
- `requirements.txt`에 패키지 추가:
  ```
  langgraph>=0.2.0,<1.0
  langchain>=0.3.0,<1.0
  langchain-community>=0.3.0,<1.0
  ```
  (langchain-openai, tavily-python은 기존 유지)
- `src/graph/__init__.py` 빈 파일 생성
- `src/graph/state.py`, `nodes.py`, `edges.py`, `builder.py` 빈 파일 생성 (껍데기)
- `docker compose build` 로 신규 패키지 설치 확인

**완료 기준:**
- [ ] `docker compose build` 종료 코드 0
- [ ] `docker compose run --rm crew_agent python -c "import langgraph; print(langgraph.__version__)"` 버전 출력

**커밋:**
```
chore(deps): add langgraph, langchain-community to requirements
```

---

## 꼭지 2: AgentState + search_node 구현

**작업:**

`src/graph/state.py`:
```python
from typing import TypedDict

class AgentState(TypedDict):
    query: str           # 최종 검색 쿼리 문자열
    target_date: str     # 분석 기준 날짜 (ISO)
    topic: str           # 검색 주제
    articles: list[str]  # Tavily 검색 결과 본문 목록
    analysis: str        # Financial_Analyst 분석 결과
    error_count: int     # 검색 실패 누적 횟수 (재시도 제어)
```

`src/graph/nodes.py` — `search_node`:
- `asyncio.to_thread(client.search, ...)` 로 Tavily 동기 API를 비동기로 래핑
- 결과가 비어있거나 예외 발생 시 `error_count += 1`로 상태 업데이트
- 성공 시 `error_count = 0` 리셋 (재시도 카운터 초기화)

```python
async def search_node(state: AgentState) -> dict:
    """Tavily 뉴스 검색. 실패·빈 결과 시 error_count 증가."""
    query = f"{state['topic']} {state['target_date']} financial news"
    try:
        client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
        resp = await asyncio.to_thread(
            client.search, query=query, max_results=5, search_depth="basic"
        )
        articles = [
            f"[{r.get('title','')}]\n{r.get('content','')[:400]}\n출처: {r.get('url','')}"
            for r in resp.get("results", [])
        ]
        if not articles:
            return {"articles": [], "error_count": state["error_count"] + 1}
        return {"articles": articles, "error_count": 0}
    except Exception as exc:
        logger.error("search_node 실패: %s", exc)
        return {"articles": [], "error_count": state["error_count"] + 1}
```

**완료 기준:**
- [ ] `python -c "from src.graph.state import AgentState; print('ok')"` 출력
- [ ] `python -c "from src.graph.nodes import search_node; print('ok')"` 출력
- [ ] 임포트 에러 없음

**커밋:**
```
feat(graph): AgentState TypedDict and async search_node
```

---

## 꼭지 3: analyze_node + 조건부 엣지 라우터

**작업:**

`src/graph/nodes.py` — `analyze_node`:
- `ChatOpenAI.ainvoke()` 를 직접 호출 (LangGraph는 LangChain 네이티브)
- `state["articles"]` 가 비어있으면 "검색 결과 없음" 경고 메시지를 분석에 포함
- 출력 형식: `## Summary\n## Key Signals\n## Risk Factors` 준수 요청

```python
async def analyze_node(state: AgentState) -> dict:
    """ChatOpenAI로 수집 기사 분석 보고서 생성."""
    llm = _make_llm()
    articles_text = (
        "\n\n---\n\n".join(state["articles"])
        if state["articles"]
        else "검색 결과를 가져오지 못했습니다."
    )
    prompt = f"""다음 뉴스 기사를 바탕으로 {state['target_date']} 기준 금융 분석 보고서를 작성하라.
정확히 세 섹션을 포함할 것: ## Summary / ## Key Signals / ## Risk Factors

[뉴스 기사]
{articles_text}
"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"analysis": response.content}
```

`src/graph/edges.py` — `route_after_search()`:

```python
MAX_RETRIES = 2  # 최대 재시도 횟수

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
```

**완료 기준:**
- [ ] `route_after_search` 단위 테스트 (직접 dict 주입):
  ```python
  python -c "
  from src.graph.edges import route_after_search
  print(route_after_search({'articles': [], 'error_count': 0}))  # search_node
  print(route_after_search({'articles': [], 'error_count': 2}))  # analyze_node
  print(route_after_search({'articles': ['a'], 'error_count': 0}))  # analyze_node
  "
  ```
- [ ] 세 케이스 모두 예상 결과 출력

**커밋:**
```
feat(graph): async analyze_node and route_after_search conditional edge
```

---

## 꼭지 4: 그래프 빌더 + graph_agent.py 진입점

**작업:**

`src/graph/builder.py`:
```python
from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.graph.nodes import search_node, analyze_node
from src.graph.edges import route_after_search

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
```

`graph_agent.py`:
- `argparse`: `--date` (기본: 오늘), `--topic` (기본: "global financial markets")
- `load_dotenv()` 최상단 호출
- `asyncio.run(main())` 패턴
- 결과를 `output/analysis_graph_{target_date}.md` 에 저장
  (crew_agent 출력과 구별하기 위해 `_graph_` 접두사 사용)
- 80줄 이내 유지

```python
async def main() -> None:
    args = _parse_args()
    Path("output").mkdir(exist_ok=True)

    graph = build_graph()
    initial_state: AgentState = {
        "query": f"{args.topic} {args.date}",
        "target_date": args.date,
        "topic": args.topic,
        "articles": [],
        "analysis": "",
        "error_count": 0,
    }
    result = await graph.ainvoke(initial_state)

    output_path = Path(f"output/analysis_graph_{args.date}.md")
    output_path.write_text(result["analysis"], encoding="utf-8")
    logger.info("그래프 실행 완료 — 결과: %s", output_path)
    print("\n" + "=" * 60)
    print(result["analysis"])
    print("=" * 60 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
```

**완료 기준:**
- [ ] `python graph_agent.py --date 2026-05-04` 오류 없이 실행
- [ ] `output/analysis_graph_2026-05-04.md` 생성됨
- [ ] 출력에 `## Summary`, `## Key Signals`, `## Risk Factors` 포함

**커밋:**
```
feat(graph): build_graph builder and graph_agent.py asyncio entry point
```

---

## 꼭지 5: Docker E2E 검증 + 재시도 로직 확인

**작업:**
- Docker 컨테이너에서 전체 그래프 실행
- 재시도 로직을 의도적으로 트리거해서 확인 (TAVILY_API_KEY를 일시 제거 후 실행)

**검증 명령어:**

```bash
# 1. Docker 빌드 (langgraph 포함)
docker compose build

# 2. 정상 실행
docker compose run --rm crew_agent python graph_agent.py --date 2026-05-04

# 3. 출력 파일 검증
grep -E "^## (Summary|Key Signals|Risk Factors)" output/analysis_graph_2026-05-04.md | wc -l
# → 3

# 4. 재시도 로직 검증 (TAVILY_API_KEY 없이 실행)
docker compose run --rm -e TAVILY_API_KEY="" crew_agent python graph_agent.py --date 2026-05-04
# → 로그에 "재시도 1/2", "재시도 2/2", "최대 재시도 도달" 출력 확인
# → 빈 결과로 분석 보고서 생성 (시스템이 중단되지 않고 완료되어야 함)

# 5. 두 방식 출력 비교
ls -la output/
# analysis_2026-05-04.md (CrewAI)
# analysis_graph_2026-05-04.md (LangGraph)
```

**완료 기준:**
- [ ] Docker 컨테이너에서 정상 실행 후 `analysis_graph_*.md` 생성
- [ ] TAVILY_API_KEY 없이 실행 시 재시도 로그가 최소 2회 출력되고 프로세스가 종료 코드 0으로 완료
- [ ] 두 출력 파일(`analysis_*.md`, `analysis_graph_*.md`)이 `output/`에 공존

**커밋:**
```
chore(docker): verify graph_agent Docker E2E with retry logic
```

---

## 세션 종료

```bash
# PR 생성
git push origin feat/langgraph-agent
gh pr create \
  --base dev \
  --title "[feat] LangGraph harness-engineering news analysis graph" \
  --body "$(cat <<'EOF'
## Overview
LangGraph StateGraph 기반 뉴스 분석 시스템 구현 (하네스 엔지니어링 패턴)

## Changes
- `src/graph/state.py`: AgentState TypedDict
- `src/graph/nodes.py`: async search_node, analyze_node
- `src/graph/edges.py`: route_after_search() 조건부 라우터 (MAX_RETRIES=2)
- `src/graph/builder.py`: build_graph() StateGraph 컴파일
- `graph_agent.py`: asyncio.run CLI 진입점
- `requirements.txt`: langgraph, langchain-community 추가

## Harness Points
- 재시도 로직: 빈 검색 결과 → search_node 재호출 (최대 2회)
- 최대 재시도 초과 시 빈 결과로 analyze_node 진행 (시스템 중단 없음)
- 상태 가시성: AgentState.error_count로 재시도 횟수 추적 가능

## Test Plan
- [ ] docker compose build 성공 (langgraph 포함)
- [ ] python graph_agent.py 실행 후 output/analysis_graph_*.md 생성
- [ ] TAVILY_API_KEY="" 환경에서 재시도 로그 2회 출력 확인
- [ ] 재시도 후에도 종료 코드 0 (시스템 중단 없음)
EOF
)"

gh pr merge --merge --delete-branch

# 세션 파일 아카이브
mv prompts/session_02_langgraph_agent.md prompts/_complete/
```

> **다음 세션**: session_03 — CrewAI vs LangGraph 성능 비교 리포트 생성, 또는 스케줄링(cron/celery) 추가

---

## 참고: LangGraph 핵심 개념

| 개념 | 설명 | 코드 위치 |
|------|------|---------|
| `StateGraph` | 상태 기반 그래프 컨테이너 | `src/graph/builder.py` |
| `TypedDict` | 그래프 상태 스키마 | `src/graph/state.py` |
| `add_node` | 노드 등록 (async 함수) | `builder.py` |
| `add_conditional_edges` | 조건부 라우팅 엣지 | `builder.py` |
| `ainvoke` | 비동기 그래프 실행 | `graph_agent.py` |
| `asyncio.to_thread` | 동기 Tavily API → 비동기 래핑 | `nodes.py` |

## 참고: 트러블슈팅

| 문제 | 해결 |
|------|------|
| `ImportError: langgraph` | `docker compose build` 재실행 |
| `ChatOpenAI` 연결 실패 | `.env`의 `OLLAMA_BASE_URL` 확인 (이번엔 `openai/` 프리픽스 불필요) |
| 재시도 루프가 끝나지 않음 | `MAX_RETRIES` 상수와 `error_count` 증가 로직 확인 |
| `ainvoke` AttributeError | `langgraph>=0.2.0` 버전 확인 (`requirements.txt`) |
| `asyncio.run()` 중첩 에러 (Jupyter) | `await main()` 직접 호출로 대체 |
