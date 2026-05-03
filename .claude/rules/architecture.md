# Rule: Project Architecture

## 모듈 책임 분리

| 파일 | 책임 | 금지 사항 |
|------|------|---------|
| `crew_agent.py` | CLI 진입점. `src/`에서 임포트해 Crew 조립 후 `kickoff()` 호출. **80줄 이내 유지** | Task 로직, Agent 정의 직접 포함 금지 |
| `src/agents.py` | Agent 팩토리 함수. 각 함수는 `crewai.Agent` 하나 반환 | Task 정의 금지 |
| `src/tasks.py` | Task 팩토리 함수. `target_date: str`을 받아 `crewai.Task` 반환 | Agent 인스턴스 생성 금지 |
| `src/tools.py` | `BaseTool` 서브클래스. 외부 서비스(Tavily 등) 1개당 1 클래스 | API 키 하드코딩 금지 |

---

## 환경 변수 규칙

- 모든 환경 값은 `.env` (로컬) 또는 `env_file: .env` (Docker)에서 주입
- 소스 파일에 API 키, 모델명, base URL **절대 하드코딩 금지**
- 필수 변수:

```bash
OLLAMA_BASE_URL   # http://host.docker.internal:11434/v1 (Docker)
                  # http://localhost:11434/v1 (로컬 직접 실행)
OLLAMA_MODEL      # gemma4 (또는 ollama list에서 확인한 모델명)
TAVILY_API_KEY    # tvly-... (https://app.tavily.com)
```

---

## LLM 설정

```python
from langchain_openai import ChatOpenAI

ChatOpenAI(
    base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    api_key="ollama",      # Ollama는 키 검증 안 함, 빈 문자열이면 LangChain 에러
    model=os.environ.get("OLLAMA_MODEL", "gemma4"),
    temperature=0.3,
)
```

> 상용 API 전환 시: `OLLAMA_BASE_URL`을 OpenAI/Anthropic endpoint로 교체하고 `api_key`를 실제 키로 변경

---

## Docker 규칙

- Compose 파일: `version:` 필드 없음 (Docker Compose Specification v2)
- Mac Docker Desktop에서 호스트 Ollama 접근: `http://host.docker.internal:11434`
- Linux Docker Engine 호환: `extra_hosts: ["host.docker.internal:host-gateway"]`
- 출력 디렉토리 볼륨 마운트: `./output:/app/output` (컨테이너 종료 후에도 파일 보존)

---

## 코드 스타일 규칙

- **타입 힌트**: 모든 함수 시그니처에 필수
- **Docstring**: 공개 함수/클래스에 한 줄 설명 (Google 스타일)
- **주석**: WHY가 명확하지 않은 경우에만 작성 (WHAT 설명 금지)
- **로깅**: `logging` 모듈 사용. `print()` 는 `crew_agent.py`의 최종 결과 출력에만 허용
- **예외 처리**: 시스템 경계(외부 API, 사용자 입력)에서만 처리. 내부 코드는 예외를 그대로 전파

---

## 에이전트 추가 절차

1. `src/agents.py`에 팩토리 함수 추가
2. `src/tasks.py`에 대응하는 태스크 팩토리 추가
3. `crew_agent.py`의 `Crew(agents=[...], tasks=[...])` 리스트에 추가
4. 세션 파일(`prompts/session_XX.md`)에 꼭지로 문서화

---

## 출력 구조

분석 결과는 `output/analysis_{YYYY-MM-DD}.md`에 저장됨:

```markdown
## Summary
(3-5문장 요약)

## Key Signals
- 중요도 순 핵심 시그널

## Risk Factors
- 모니터링 필요 리스크 목록
```

`output/` 디렉토리는 `.gitignore`에 포함 — 버전 관리 대상 아님
