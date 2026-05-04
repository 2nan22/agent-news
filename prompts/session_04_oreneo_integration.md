# Session 04: oreneo 프로젝트 뉴스 분석 통합 (FastAPI + Django + Celery)

> **Session Goal**: Session 03의 멀티-섹터 그래프를 `2026_oreneo` 프로젝트에 PoC 수준으로 통합.  
> FastAPI AI 서비스에 뉴스 분석 라우터 추가, Django 모델로 DB 영속화, Celery Beat 일일 자동 실행.
> **Branch**: `feat/news-analysis` (oreneo 프로젝트 `dev`에서 분기)
> **예상 소요**: 2 ~ 2.5시간
> **전제 조건**: Session 03 완료 (멀티-섹터 그래프, `migrations/001_initial_schema.sql` 작성 완료)
> **작업 디렉토리**: `/Users/2nan/Documents/Project/2026_oreneo`

---

## 세션 시작 전 주입

```
# oreneo 프로젝트
Read /Users/2nan/Documents/Project/2026_oreneo/docker-compose.yml
Read /Users/2nan/Documents/Project/2026_oreneo/backend/config/settings/base.py
Read /Users/2nan/Documents/Project/2026_oreneo/backend/config/celery.py
Read /Users/2nan/Documents/Project/2026_oreneo/ai_service/main.py
Read /Users/2nan/Documents/Project/2026_oreneo/ai_service/config.py
Read /Users/2nan/Documents/Project/2026_oreneo/backend/apps/public_data/tasks.py

# AI-Agent 프로젝트 참조 (이식할 코드)
Read /Users/2nan/Documents/Project/2026_AI-Agent/src/graph/keywords.py
Read /Users/2nan/Documents/Project/2026_AI-Agent/src/graph/nodes.py
Read /Users/2nan/Documents/Project/2026_AI-Agent/src/graph/builder.py
Read /Users/2nan/Documents/Project/2026_AI-Agent/migrations/001_initial_schema.sql
```

---

## 배경 및 목표

oreneo는 개인 재정·의사결정 관리 웹 앱이다.
기존 구조:
- **백엔드**: Django 5.2 + DRF, PostgreSQL 16, Redis
- **AI 서비스**: FastAPI 8001포트, Ollama(gemma4) + Tavily 기존 사용 중
- **Celery**: `django-celery-beat`, 현재 2개 스케줄 운영 중
- **AI 라우터 패턴**: `/ai_service/routers/{coach,decision,public_data}.py`

### 통합 아키텍처

```
Celery Beat (매일 08:00 KST)
  └─► Django Celery Task
        backend/apps/news/tasks.py::run_daily_news_analysis
          └─► HTTP POST http://ai_service:8001/news/analyze
                └─► FastAPI router (ai_service/routers/news.py)
                      └─► LangGraph 그래프 실행 (AI-Agent 로직 이식)
                            └─► Tavily 검색 + Ollama 분석
                      └─► JSON 응답 반환
          └─► TBL_NEWS_ANALYSIS, TBL_NEWS_SECTOR_ANALYSIS 저장
Django REST API (향후 프론트엔드 연동)
```

### 최종 파일 변경 목록

```
2026_oreneo/
├── backend/
│   ├── apps/
│   │   └── news/                     ← (신규 Django 앱)
│   │       ├── __init__.py
│   │       ├── apps.py
│   │       ├── models.py             ← TBL_NEWS_ANALYSIS, TBL_NEWS_SECTOR_ANALYSIS, ...
│   │       ├── tasks.py              ← run_daily_news_analysis Celery 태스크
│   │       ├── serializers.py
│   │       ├── views.py
│   │       └── urls.py
│   └── config/
│       └── settings/
│           └── base.py               ← INSTALLED_APPS 추가, CELERY_BEAT_SCHEDULE 추가
├── ai_service/
│   ├── routers/
│   │   └── news.py                   ← (신규) POST /news/analyze
│   ├── services/
│   │   └── news_graph.py             ← (신규) LangGraph 그래프 이식
│   ├── main.py                       ← 뉴스 라우터 등록
│   └── requirements.txt              ← langgraph, langchain 추가
```

---

## 꼭지 1: Django `news` 앱 생성 + 모델 정의

**작업 A:** `backend/apps/news/` 앱 스켈레톤 생성

```bash
cd /Users/2nan/Documents/Project/2026_oreneo
mkdir -p backend/apps/news
touch backend/apps/news/__init__.py
```

**작업 B:** `backend/apps/news/apps.py`

```python
# backend/apps/news/apps.py
from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    app_label = "news"
    name = "apps.news"
```

**작업 C:** `backend/apps/news/models.py` — TBL_ 스키마를 Django ORM으로 구현

```python
# backend/apps/news/models.py
from django.db import models


class MarketSector(models.Model):
    """TBL_MARKET_SECTOR — 섹터 마스터."""

    MARKET_CHOICES = [("KR", "한국"), ("US", "미국"), ("ALL", "공통")]

    sector_code = models.CharField(max_length=30, unique=True)
    sector_name_ko = models.CharField(max_length=50)
    sector_name_en = models.CharField(max_length=50)
    market = models.CharField(max_length=5, choices=MARKET_CHOICES)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TBL_MARKET_SECTOR"
        ordering = ["display_order"]

    def __str__(self) -> str:
        return f"{self.sector_name_ko} ({self.market})"


class MarketCompany(models.Model):
    """TBL_MARKET_COMPANY — 회사 마스터."""

    MARKET_CHOICES = [("KR", "한국"), ("US", "미국")]

    ticker = models.CharField(max_length=20, unique=True)
    company_name_ko = models.CharField(max_length=100, blank=True)
    company_name_en = models.CharField(max_length=100)
    market = models.CharField(max_length=5, choices=MARKET_CHOICES)
    exchange = models.CharField(max_length=20, blank=True)   # KOSPI, KOSDAQ, NYSE, NASDAQ
    sector = models.ForeignKey(
        MarketSector, null=True, blank=True, on_delete=models.SET_NULL
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TBL_MARKET_COMPANY"

    def __str__(self) -> str:
        return f"{self.ticker} — {self.company_name_en}"


class NewsArticle(models.Model):
    """TBL_NEWS_ARTICLE — Tavily 수집 원문 기사."""

    MARKET_CHOICES = [("KR", "한국"), ("US", "미국")]

    article_url = models.TextField(unique=True)
    title = models.TextField()
    content = models.TextField(blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    market = models.CharField(max_length=5, choices=MARKET_CHOICES, blank=True)
    language = models.CharField(max_length=5, default="ko")
    raw_data = models.JSONField(null=True, blank=True)       # Tavily 원본
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TBL_NEWS_ARTICLE"
        indexes = [
            models.Index(fields=["market"]),
            models.Index(fields=["-published_at"]),
        ]


class NewsAnalysis(models.Model):
    """TBL_NEWS_ANALYSIS — 분석 실행 헤더 (1 run = 1 row)."""

    STATUS_CHOICES = [
        ("PENDING",   "대기"),
        ("RUNNING",   "실행 중"),
        ("COMPLETED", "완료"),
        ("FAILED",    "실패"),
    ]
    ENGINE_CHOICES = [("langgraph", "LangGraph"), ("crewai", "CrewAI")]
    MARKET_CHOICES = [("KR", "한국"), ("US", "미국"), ("ALL", "전체")]

    analysis_date = models.DateField()
    market = models.CharField(max_length=5, choices=MARKET_CHOICES)
    engine_type = models.CharField(max_length=20, choices=ENGINE_CHOICES, default="langgraph")
    run_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    overall_analysis = models.TextField(blank=True)
    raw_result = models.JSONField(null=True, blank=True)     # sector_analyses 전체
    run_duration_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TBL_NEWS_ANALYSIS"
        unique_together = [("analysis_date", "market", "engine_type")]

    def __str__(self) -> str:
        return f"{self.analysis_date} [{self.market}] {self.engine_type} — {self.run_status}"


class NewsSectorAnalysis(models.Model):
    """TBL_NEWS_SECTOR_ANALYSIS — 섹터별 분석 결과."""

    analysis = models.ForeignKey(
        NewsAnalysis, on_delete=models.CASCADE, related_name="sector_analyses"
    )
    sector = models.ForeignKey(MarketSector, on_delete=models.PROTECT)
    analysis_text = models.TextField(blank=True)             # ## Summary / ## Key Signals / ## Risk Factors
    article_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TBL_NEWS_SECTOR_ANALYSIS"
        unique_together = [("analysis", "sector")]


class UserWatchlist(models.Model):
    """TBL_USER_WATCHLIST — 사용자 관심 섹터/종목."""

    TYPE_CHOICES = [("SECTOR", "섹터"), ("COMPANY", "종목")]

    user_id = models.BigIntegerField(null=True, blank=True)  # accounts.CustomUser FK (추후 연결)
    watchlist_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    sector = models.ForeignKey(
        MarketSector, null=True, blank=True, on_delete=models.CASCADE
    )
    company = models.ForeignKey(
        MarketCompany, null=True, blank=True, on_delete=models.CASCADE
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TBL_USER_WATCHLIST"
```

**작업 D:** `backend/config/settings/base.py` — INSTALLED_APPS 추가

```python
# INSTALLED_APPS에 추가
INSTALLED_APPS = [
    ...
    "apps.news",     # ← 추가
]
```

**완료 기준:**
- [ ] `docker compose exec backend python manage.py check` 오류 없음

**커밋:**
```
feat(news): add news Django app with TBL_ schema models
```

---

## 꼭지 2: Django 마이그레이션 생성 + 시드 데이터

**작업 A:** 마이그레이션 생성 및 적용

```bash
docker compose exec backend python manage.py makemigrations news
docker compose exec backend python manage.py migrate
```

**작업 B:** 섹터 시드 데이터 (`backend/apps/news/migrations/0002_seed_sectors.py`)

```python
# backend/apps/news/migrations/0002_seed_sectors.py
from django.db import migrations

SECTORS = [
    ("SEMICONDUCTOR", "반도체",  "Semiconductor",          "KR",  1),
    ("AI",            "AI",      "Artificial Intelligence", "ALL", 2),
    ("SHIPBUILDING",  "조선",    "Shipbuilding",            "KR",  3),
    ("RAW_MATERIALS", "원자재",  "Raw Materials",           "ALL", 4),
    ("ENERGY",        "에너지",  "Energy",                  "ALL", 5),
    ("FINANCE",       "금융",    "Finance",                 "ALL", 6),
]


def seed_sectors(apps, schema_editor):
    MarketSector = apps.get_model("news", "MarketSector")
    for code, ko, en, market, order in SECTORS:
        MarketSector.objects.get_or_create(
            sector_code=code,
            defaults={
                "sector_name_ko": ko,
                "sector_name_en": en,
                "market": market,
                "display_order": order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("news", "0001_initial")]

    operations = [migrations.RunPython(seed_sectors, migrations.RunPython.noop)]
```

**완료 기준:**
- [ ] `docker compose exec backend python manage.py migrate` 성공
- [ ] `docker compose exec db psql -U postgres -d oreneo -c "SELECT sector_code FROM \"TBL_MARKET_SECTOR\";"` → 6개 섹터 출력

**커밋:**
```
feat(news): add migrations and sector seed data
```

---

## 꼭지 3: FastAPI 뉴스 분석 라우터 + AI 서비스 이식

**작업 A:** AI 서비스 의존성 추가 (`ai_service/requirements.txt`)

```
# 기존 의존성 유지 + 추가
langgraph>=0.2.0,<1.0
langchain>=0.3.0,<1.0
langchain-openai>=0.2.0,<1.0
tavily-python>=0.5.0
```

**작업 B:** `ai_service/services/news_graph.py` — AI-Agent 그래프 로직 이식

```python
# ai_service/services/news_graph.py
"""AI-Agent 멀티-섹터 LangGraph 로직 (oreneo AI 서비스용)."""
import asyncio
import logging
import os
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from tavily import TavilyClient

logger = logging.getLogger(__name__)

# ─── 섹터 키워드 (AI-Agent keywords.py와 동기화) ───────────────────────────
KR_SECTOR_KEYWORDS: dict[str, str] = {
    "반도체": "반도체 DRAM 낸드 삼성전자 SK하이닉스",
    "AI":     "AI 인공지능 네이버 카카오 LG AI연구원",
    "조선":   "조선 해운 현대중공업 삼성중공업 한화오션",
    "원자재": "원자재 철강 포스코 구리 리튬",
    "에너지": "에너지 한국전력 SK에너지 발전 원전",
    "금융":   "금융 은행 KB 신한 하나 증시",
}
US_SECTOR_KEYWORDS: dict[str, str] = {
    "반도체": "semiconductor chip TSMC NVIDIA AMD",
    "AI":     "AI artificial intelligence OpenAI Google",
    "에너지": "energy oil gas Exxon Chevron",
    "금융":   "finance banking JPMorgan Goldman Fed",
}
DEFAULT_SECTORS = list(KR_SECTOR_KEYWORDS.keys())


# ─── AgentState ────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    target_date: str
    market: str
    sectors: list[str]
    watchlist_companies: list[str]
    sector_articles: dict[str, list[str]]
    sector_analyses: dict[str, str]
    overall_analysis: str
    error_count: int


# ─── LLM / Tavily 팩토리 ──────────────────────────────────────────────────
def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key="ollama",
        model=os.environ.get("OLLAMA_MODEL", "gemma4"),
        temperature=0.3,
    )


# ─── 노드 ─────────────────────────────────────────────────────────────────
async def multi_search_node(state: AgentState) -> dict:
    """섹터별 Tavily 검색."""
    market = state["market"]
    sector_articles: dict[str, list[str]] = {}

    for sector in state["sectors"]:
        kw = (US_SECTOR_KEYWORDS if market == "US" else KR_SECTOR_KEYWORDS).get(sector, sector)
        query = f"{kw} news {state['target_date']}" if market == "US" else f"{kw} 뉴스 {state['target_date']}"
        try:
            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            resp = await asyncio.to_thread(
                client.search, query=query, max_results=5, search_depth="basic"
            )
            sector_articles[sector] = [
                f"[{r.get('title','')}]\n{r.get('content','')[:400]}\n출처: {r.get('url','')}"
                for r in resp.get("results", [])
            ]
        except Exception as exc:
            logger.error("섹터 '%s' 검색 실패: %s", sector, exc)
            sector_articles[sector] = []

    total = sum(len(v) for v in sector_articles.values())
    return {
        "sector_articles": sector_articles,
        "error_count": state["error_count"] + (0 if total > 0 else 1),
    }


async def sector_analyze_node(state: AgentState) -> dict:
    """섹터별 분석 보고서 생성."""
    llm = _make_llm()
    sector_analyses: dict[str, str] = {}
    for sector, articles in state["sector_articles"].items():
        text = "\n\n---\n\n".join(articles) if articles else "검색 결과 없음."
        prompt = f"""[{sector}] 섹터 {state['target_date']} 금융 분석 보고서:
## Summary / ## Key Signals / ## Risk Factors 세 섹션을 포함하라.
[기사]\n{text}"""
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        sector_analyses[sector] = resp.content
    return {"sector_analyses": sector_analyses}


async def aggregate_node(state: AgentState) -> dict:
    """전체 요약 생성."""
    llm = _make_llm()
    summaries = "\n\n".join(f"### {s}\n{a[:500]}" for s, a in state["sector_analyses"].items())
    prompt = f"{state['target_date']} {state['market']} 멀티-섹터 종합 요약 (3-5문장):\n{summaries}"
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    return {"overall_analysis": resp.content}


def _route(state: AgentState) -> str:
    total = sum(len(v) for v in state["sector_articles"].values())
    if total > 0 or state["error_count"] >= 2:
        return "sector_analyze_node"
    return "multi_search_node"


# ─── 그래프 빌드 ───────────────────────────────────────────────────────────
def build_news_graph():
    """뉴스 분석 StateGraph 컴파일."""
    b = StateGraph(AgentState)
    b.add_node("multi_search_node", multi_search_node)
    b.add_node("sector_analyze_node", sector_analyze_node)
    b.add_node("aggregate_node", aggregate_node)
    b.set_entry_point("multi_search_node")
    b.add_conditional_edges(
        "multi_search_node", _route,
        {"multi_search_node": "multi_search_node", "sector_analyze_node": "sector_analyze_node"},
    )
    b.add_edge("sector_analyze_node", "aggregate_node")
    b.add_edge("aggregate_node", END)
    return b.compile()
```

**작업 C:** `ai_service/routers/news.py`

```python
# ai_service/routers/news.py
import time
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_service.services.news_graph import AgentState, DEFAULT_SECTORS, build_news_graph

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


class NewsAnalyzeRequest(BaseModel):
    target_date: str
    market: str = "KR"                      # KR / US / ALL
    sectors: list[str] = DEFAULT_SECTORS
    watchlist_companies: list[str] = []
    engine: str = "langgraph"               # 향후 crewai 전환용


class NewsAnalyzeResponse(BaseModel):
    overall_analysis: str
    sector_analyses: dict[str, str]
    run_duration_ms: int


@router.post("/analyze", response_model=NewsAnalyzeResponse)
async def analyze_news(req: NewsAnalyzeRequest) -> NewsAnalyzeResponse:
    """멀티-섹터 뉴스 분석 실행."""
    logger.info("뉴스 분석 시작: %s %s %s", req.target_date, req.market, req.sectors)
    t0 = time.monotonic()
    try:
        graph = build_news_graph()
        initial: AgentState = {
            "target_date": req.target_date,
            "market": req.market,
            "sectors": req.sectors,
            "watchlist_companies": req.watchlist_companies,
            "sector_articles": {},
            "sector_analyses": {},
            "overall_analysis": "",
            "error_count": 0,
        }
        result = await graph.ainvoke(initial)
    except Exception as exc:
        logger.error("뉴스 분석 실패: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return NewsAnalyzeResponse(
        overall_analysis=result["overall_analysis"],
        sector_analyses=result["sector_analyses"],
        run_duration_ms=elapsed_ms,
    )
```

**작업 D:** `ai_service/main.py` — 라우터 등록 (기존 router 등록 패턴 유지)

```python
# 기존 import 아래에 추가
from ai_service.routers.news import router as news_router

# 기존 app.include_router(...) 줄들 아래에 추가
app.include_router(news_router)
```

**완료 기준:**
- [ ] `docker compose build ai_service` 성공
- [ ] `docker compose up -d ai_service`
- [ ] `curl -X POST http://localhost:8001/news/analyze -H "Content-Type: application/json" -d '{"target_date":"2026-05-04","market":"KR","sectors":["반도체","AI"]}'` → JSON 응답

**커밋:**
```
feat(ai): add news analysis FastAPI router with LangGraph engine
```

---

## 꼭지 4: Celery 태스크 + Beat 스케줄 등록

**작업 A:** `backend/apps/news/tasks.py`

```python
# backend/apps/news/tasks.py
import logging
import time
from datetime import date

import httpx
from celery import shared_task
from django.conf import settings

from apps.news.models import MarketSector, NewsAnalysis, NewsSectorAnalysis

logger = logging.getLogger(__name__)

AI_SERVICE_URL = settings.AI_SERVICE_URL           # "http://ai_service:8001"
AI_SERVICE_SECRET = settings.AI_SERVICE_SECRET


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def run_daily_news_analysis(
    self,
    target_date: str | None = None,
    market: str = "KR",
    sectors: list[str] | None = None,
    engine: str = "langgraph",
) -> dict:
    """매일 08:00 KST 실행 — 멀티-섹터 뉴스 분석 후 DB 저장."""
    target_date = target_date or str(date.today())
    sectors = sectors or list(
        MarketSector.objects.filter(is_active=True, market__in=[market, "ALL"])
        .order_by("display_order")
        .values_list("sector_name_ko", flat=True)
    )

    # 분석 헤더 레코드 생성 (RUNNING)
    analysis_obj, _ = NewsAnalysis.objects.update_or_create(
        analysis_date=target_date,
        market=market,
        engine_type=engine,
        defaults={"run_status": "RUNNING", "error_message": ""},
    )

    t0 = time.monotonic()
    try:
        resp = httpx.post(
            f"{AI_SERVICE_URL}/news/analyze",
            json={
                "target_date": target_date,
                "market": market,
                "sectors": sectors,
                "engine": engine,
            },
            headers={"X-Service-Secret": AI_SERVICE_SECRET},
            timeout=300,                             # LLM 호출 시간 고려
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        analysis_obj.run_status = "FAILED"
        analysis_obj.error_message = str(exc)
        analysis_obj.run_duration_ms = elapsed_ms
        analysis_obj.save()
        logger.error("뉴스 분석 태스크 실패: %s", exc)
        raise self.retry(exc=exc)

    # DB 저장
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    analysis_obj.run_status = "COMPLETED"
    analysis_obj.overall_analysis = data["overall_analysis"]
    analysis_obj.raw_result = data["sector_analyses"]
    analysis_obj.run_duration_ms = elapsed_ms
    analysis_obj.save()

    # 섹터별 저장
    sector_map = {
        s.sector_name_ko: s
        for s in MarketSector.objects.filter(sector_name_ko__in=sectors)
    }
    for sector_name, analysis_text in data["sector_analyses"].items():
        sector_obj = sector_map.get(sector_name)
        if sector_obj:
            NewsSectorAnalysis.objects.update_or_create(
                analysis=analysis_obj,
                sector=sector_obj,
                defaults={"analysis_text": analysis_text},
            )

    logger.info("뉴스 분석 완료: %s %s (%d ms)", target_date, market, elapsed_ms)
    return {"analysis_id": analysis_obj.id, "run_duration_ms": elapsed_ms}
```

**작업 B:** `backend/config/settings/base.py` — Celery Beat 스케줄 추가

```python
# CELERY_BEAT_SCHEDULE 기존 항목 아래에 추가
CELERY_BEAT_SCHEDULE = {
    # 기존 스케줄 유지
    ...
    # 뉴스 분석 (매일 08:00 KST = 23:00 UTC 전일)
    "run-daily-news-analysis-8am-kst": {
        "task": "apps.news.tasks.run_daily_news_analysis",
        "schedule": crontab(hour=23, minute=0),     # UTC 23:00 = KST 08:00
        "kwargs": {"market": "KR", "engine": "langgraph"},
    },
}
```

**완료 기준:**
- [ ] `docker compose exec backend python manage.py shell -c "from apps.news.tasks import run_daily_news_analysis; result = run_daily_news_analysis('2026-05-04', 'KR', ['반도체', 'AI']); print(result)"` 성공
- [ ] DB 확인: `docker compose exec db psql -U postgres -d oreneo -c "SELECT run_status, overall_analysis FROM \"TBL_NEWS_ANALYSIS\";"` → COMPLETED

**커밋:**
```
feat(news): Celery task run_daily_news_analysis with DB persistence
chore(celery): register daily news analysis beat schedule at 08:00 KST
```

---

## 꼭지 5: E2E 검증

```bash
# 1. 전체 스택 재빌드 (ai_service langgraph 포함)
docker compose build

# 2. 스택 기동
docker compose up -d

# 3. Django 마이그레이션 확인
docker compose exec backend python manage.py showmigrations news

# 4. FastAPI 라우터 직접 테스트 (섹터 2개)
curl -s -X POST http://localhost:8001/news/analyze \
  -H "Content-Type: application/json" \
  -d '{"target_date":"2026-05-04","market":"KR","sectors":["반도체","AI"]}' \
  | python -m json.tool

# 5. Celery 태스크 수동 트리거 (Django shell)
docker compose exec backend python manage.py shell -c "
from apps.news.tasks import run_daily_news_analysis
result = run_daily_news_analysis('2026-05-04', 'KR', ['반도체', 'AI'])
print('결과:', result)
"

# 6. DB 저장 확인
docker compose exec db psql -U postgres -d oreneo -c "
SELECT id, analysis_date, market, run_status, run_duration_ms
FROM \"TBL_NEWS_ANALYSIS\";
"

docker compose exec db psql -U postgres -d oreneo -c "
SELECT s.sector_name_ko, n.article_count, LEFT(n.analysis_text, 100) as preview
FROM \"TBL_NEWS_SECTOR_ANALYSIS\" n
JOIN \"TBL_MARKET_SECTOR\" s ON n.sector_id = s.id;
"

# 7. 재시도 로직 검증 (TAVILY_API_KEY 없이)
docker compose exec -e TAVILY_API_KEY="" backend python manage.py shell -c "
from apps.news.tasks import run_daily_news_analysis
result = run_daily_news_analysis('2026-05-04', 'KR', ['반도체'])
print(result)
"
# → FAILED 상태로 저장되어야 함 (max_retries 초과 후)
```

**완료 기준:**
- [ ] FastAPI `/news/analyze` → JSON 응답 (overall_analysis, sector_analyses, run_duration_ms)
- [ ] `TBL_NEWS_ANALYSIS` 에 COMPLETED 레코드 생성
- [ ] `TBL_NEWS_SECTOR_ANALYSIS` 에 섹터별 레코드 생성
- [ ] Celery Beat 스케줄 등록 확인: `docker compose exec backend celery -A config inspect scheduled`

**커밋:**
```
chore(docker): verify oreneo news integration E2E with DB persistence
```

---

## 세션 종료

```bash
# PR 생성 (oreneo 프로젝트)
cd /Users/2nan/Documents/Project/2026_oreneo
git push origin feat/news-analysis
gh pr create \
  --base dev \
  --title "[feat] News analysis integration — FastAPI + Django + Celery" \
  --body "$(cat <<'EOF'
## Overview
2026_AI-Agent의 LangGraph 멀티-섹터 뉴스 분석을 oreneo에 통합 (PoC).

## Changes
- `backend/apps/news/`: Django 앱 (모델 6개, Celery 태스크)
- `ai_service/routers/news.py`: POST /news/analyze FastAPI 라우터
- `ai_service/services/news_graph.py`: LangGraph 그래프 이식
- `backend/config/settings/base.py`: INSTALLED_APPS + 08:00 KST 스케줄

## Data Flow
Celery Beat (08:00 KST) → Django Task → HTTP POST ai_service:8001/news/analyze
  → LangGraph (Tavily + Ollama) → JSON → TBL_NEWS_ANALYSIS + TBL_NEWS_SECTOR_ANALYSIS

## Test Plan
- [ ] docker compose build 성공 (langgraph 포함)
- [ ] curl /news/analyze → JSON 응답
- [ ] Celery 태스크 수동 실행 → DB COMPLETED 저장
- [ ] TBL_NEWS_SECTOR_ANALYSIS 섹터별 레코드 확인
EOF
)"

gh pr merge --merge --delete-branch

# AI-Agent 세션 파일 아카이브 (기준 프로젝트에서)
cd /Users/2nan/Documents/Project/2026_AI-Agent
mv prompts/session_04_oreneo_integration.md prompts/_complete/
```

> **다음 세션 후보**:
> - session_05: Django REST API 뷰 + Next.js 대시보드 연동
> - session_05: CrewAI vs LangGraph 성능 비교 리포트 자동화 (--engine 전환 후 결과 diff)
> - session_05: 워치리스트 관리 UI + user_id FK 연결 (accounts.CustomUser)

---

## 참고: oreneo 프로젝트 기존 패턴

| 위치 | 참고 목적 |
|------|---------|
| `backend/apps/public_data/tasks.py` | Celery 태스크 패턴 (paginated API polling + DB sync) |
| `backend/apps/reports/tasks.py` | 리포트 생성 태스크 패턴 |
| `ai_service/routers/public_data.py` | FastAPI 라우터 패턴 (X-Service-Secret 인증) |
| `ai_service/services/gemma_client.py` | LLM 클라이언트 패턴 |

## 참고: 트러블슈팅

| 문제 | 해결 |
|------|------|
| `ImportError: langgraph` (ai_service) | `ai_service/requirements.txt`에 langgraph 추가 후 `docker compose build` |
| Celery 태스크 timeout | `httpx.post(timeout=300)` 확인, Ollama 응답 지연 시 경량 모델로 교체 |
| `TBL_` 테이블 없음 | `python manage.py migrate` 재실행 |
| AI 서비스 연결 실패 | `AI_SERVICE_URL=http://ai_service:8001` (Docker 내부 서비스명) 확인 |
| 섹터 FK 없음 | `TBL_MARKET_SECTOR` seed 마이그레이션 적용 확인 (`0002_seed_sectors`) |
