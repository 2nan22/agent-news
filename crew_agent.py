"""
CrewAI 뉴스 분석 크루 — CLI 진입점.

Usage:
    python crew_agent.py [--date YYYY-MM-DD] [--topic "검색 주제"]

Example:
    python crew_agent.py --date 2026-05-04 --topic "한국 부동산 시장"
    docker compose run --rm crew_agent python crew_agent.py --date 2026-05-04
"""

from __future__ import annotations

import argparse
import datetime
import logging
from pathlib import Path

from dotenv import load_dotenv

# src/ 모듈이 os.environ을 사용하므로 임포트 전에 .env 로드
load_dotenv()

from crewai import Crew, Process  # noqa: E402

from src.tasks import make_analysis_task, make_research_task  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CrewAI 뉴스 분석 크루 실행")
    parser.add_argument(
        "--date",
        default=datetime.date.today().isoformat(),
        help="뉴스 검색 기준 날짜 (YYYY-MM-DD). 기본값: 오늘",
    )
    parser.add_argument(
        "--topic",
        default="global financial markets",
        help="검색 주제. 기본값: 'global financial markets'",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    target_date: str = args.date
    topic: str = args.topic

    # 크루가 output_file을 쓸 디렉토리 보장
    Path("output").mkdir(exist_ok=True)

    logger.info("크루 실행 시작 — date=%s topic=%s", target_date, topic)

    research_task = make_research_task(target_date=target_date, topic=topic)
    analysis_task = make_analysis_task(target_date=target_date)

    crew = Crew(
        agents=[research_task.agent, analysis_task.agent],
        tasks=[research_task, analysis_task],
        process=Process.sequential,  # 리서처 → 애널리스트 순서로 실행
        verbose=True,
    )

    result = crew.kickoff()

    output_path = f"output/analysis_{target_date}.md"
    logger.info("크루 실행 완료 — 결과: %s", output_path)

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
