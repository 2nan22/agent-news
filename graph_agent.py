import argparse
import asyncio
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.graph.builder import build_graph
from src.graph.keywords import DEFAULT_SECTORS
from src.graph.report import build_report
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

    if args.engine == "langgraph":
        result = await _run_langgraph(args)
    else:
        result = await asyncio.to_thread(_run_crewai, args)

    output_path = Path(f"output/analysis_{args.engine}_{args.market}_{args.date}.md")
    content = build_report(args, result)
    output_path.write_text(content, encoding="utf-8")
    logger.info("분석 완료 [%s] — 결과: %s", args.engine, output_path)
    print("\n" + "=" * 60)
    print(content)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
