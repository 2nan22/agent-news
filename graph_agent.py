import argparse
import asyncio
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.graph.builder import build_graph
from src.graph.state import AgentState

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangGraph 뉴스 분석 CLI")
    parser.add_argument("--date", default=str(date.today()), help="분석 기준 날짜 (YYYY-MM-DD)")
    parser.add_argument("--topic", default="global financial markets", help="검색 주제")
    return parser.parse_args()


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
