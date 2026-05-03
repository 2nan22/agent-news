# Session 01: CrewAI 멀티 에이전트 뉴스 분석 시스템 구축

> **Session Goal**: Docker 환경에서 동작하는 두 에이전트(News_Researcher + Financial_Analyst) 크루를 구현하고 E2E 검증
> **Branch**: `feat/crew-agents` (from dev)
> **예상 소요**: 1.5 ~ 2시간

---

## 세션 시작 전 주입

```
Read .claude/rules/git_workflow.md
Read .claude/rules/architecture.md
```

---

## 배경 및 목표

로컬 Mac 환경의 Ollama(gemma4)와 Tavily 검색 API를 활용해 매일 주요 부동산/금융 뉴스를 자동 수집·분석하는 멀티 에이전트 시스템을 구축한다.

**기술 스택:**
- LLM: `langchain_openai.ChatOpenAI` → Ollama 로컬 연결 (`base_url=http://host.docker.internal:11434/v1`)
- 검색: `tavily-python` (TavilySearchTool)
- 오케스트레이션: `crewai` (Process.sequential)
- 실행 환경: Docker Compose v2 (단일 서비스)

---

## 꼭지 1: Docker 인프라

**작업:**
- `Dockerfile` 생성 (python:3.12-slim, 2-stage: deps → production)
- `docker-compose.yml` 생성 (v2 spec, `version:` 필드 없음)
  - `extra_hosts: ["host.docker.internal:host-gateway"]` 포함
  - `env_file: .env`, `volumes: ./output:/app/output`

**완료 기준:**
- [ ] `docker compose build` 종료 코드 0
- [ ] `docker compose run --rm crew_agent python -c "import crewai; print(crewai.__version__)"` 버전 출력

**커밋:**
```
chore(docker): Dockerfile and docker-compose.yml for crew_agent service
```

---

## 꼭지 2: src/ 패키지 — tools, agents, tasks

**작업:**
- `src/__init__.py` (빈 파일, 패키지 마킹)
- `src/tools.py`: `TavilySearchTool(BaseTool)` 구현
  - `api_key: str = ""` Pydantic 필드, `__init__`에서 env 주입
  - `_run(query: str) -> str` — Tavily 호출, 결과 포맷팅
- `src/agents.py`: `_make_llm()`, `make_researcher_agent()`, `make_analyst_agent()`
  - LLM: `ChatOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", model=OLLAMA_MODEL)`
  - News_Researcher: `tools=[TavilySearchTool()]`, `max_iter=3`
  - Financial_Analyst: `tools=[]`, `max_iter=2`
- `src/tasks.py`: `make_research_task(target_date, topic)`, `make_analysis_task(target_date)`
  - 분석 태스크: `output_file="output/analysis_{target_date}.md"`

**완료 기준:**
- [ ] `python -c "from src.tools import TavilySearchTool; print(TavilySearchTool().name)"` → `tavily_search`
- [ ] `python -c "from src.agents import make_researcher_agent; print(make_researcher_agent().role)"` → `News_Researcher`
- [ ] 임포트 에러 없음

**커밋:**
```
feat(src): TavilySearchTool, agent factories, task factories
```

---

## 꼭지 3: crew_agent.py 진입점

**작업:**
- `argparse` CLI: `--date` (기본: 오늘 ISO), `--topic` (기본: "global financial markets")
- 최상단에 `load_dotenv()` 호출
- `Path("output").mkdir(exist_ok=True)` 로 출력 디렉토리 보장
- `Crew(agents=[...], tasks=[...], process=Process.sequential)` 조립 후 `kickoff()`
- 80줄 이내 유지

**완료 기준:**
- [ ] `python crew_agent.py --date 2026-05-04 --topic "부동산 시장"` 오류 없이 실행
- [ ] `output/analysis_2026-05-04.md` 생성됨
- [ ] 파일 내 `## Summary`, `## Key Signals`, `## Risk Factors` 섹션 존재

**커밋:**
```
feat(crew): crew_agent.py CLI entry point with sequential crew
```

---

## 꼭지 4: Docker E2E 검증

**작업:**
- Docker 컨테이너 내에서 전체 실행 검증
- host.docker.internal → Mac 호스트 Ollama 연결 확인

**검증 명령어:**

```bash
# Ollama 연결 확인
docker compose run --rm crew_agent \
  python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags').read()[:100])"

# 전체 실행
docker compose run --rm crew_agent python crew_agent.py --date 2026-05-04

# 출력 검증 (3개 섹션 확인)
grep -E "^## (Summary|Key Signals|Risk Factors)" output/analysis_2026-05-04.md | wc -l
# → 3
```

**완료 기준:**
- [ ] Docker 컨테이너에서 Ollama 응답 JSON 수신
- [ ] 컨테이너 종료 후 호스트 `./output/analysis_2026-05-04.md` 존재
- [ ] 출력 파일에 3개 섹션 헤더 존재

**커밋:**
```
chore(docker): verify end-to-end Docker run with volume output
```

---

## 세션 종료

```bash
# PR 생성
git push origin feat/crew-agents
gh pr create \
  --base dev \
  --title "[feat] CrewAI two-agent news analysis crew" \
  --body "$(cat <<'EOF'
## Overview
CrewAI 멀티 에이전트 뉴스 분석 시스템 구현 (News_Researcher + Financial_Analyst)

## Changes
- src/tools.py: TavilySearchTool (BaseTool 서브클래스)
- src/agents.py: make_researcher_agent(), make_analyst_agent()
- src/tasks.py: make_research_task(), make_analysis_task()
- crew_agent.py: argparse CLI 진입점
- Dockerfile + docker-compose.yml: 단일 서비스 컨테이너

## Test Plan
- [ ] docker compose build 성공
- [ ] docker compose run 후 output/analysis_*.md 생성
- [ ] 출력 파일에 Summary / Key Signals / Risk Factors 섹션 존재
- [ ] host.docker.internal → Mac 호스트 Ollama 연결 확인
EOF
)"

# PR 병합 후 세션 파일 이동
gh pr merge --merge --delete-branch
mv prompts/session_01_crew_setup.md prompts/_complete/
```

> **다음 세션**: session_02 — 에러 처리 강화, 재시도 로직, 출력 포맷 개선

---

## 참고: 트러블슈팅

| 문제 | 해결 |
|------|------|
| `host.docker.internal` 미해석 (Linux) | `extra_hosts: ["host.docker.internal:host-gateway"]` 확인 |
| `TAVILY_API_KEY not set` 경고 | `.env` 파일 생성 후 키 입력 |
| Pydantic `ValidationError` in TavilySearchTool | `super().__init__(api_key=os.environ.get("TAVILY_API_KEY", ""))` 패턴으로 변경 |
| Ollama 모델명 오류 | `ollama list` 로 정확한 태그 확인 후 `.env`의 `OLLAMA_MODEL` 수정 |
