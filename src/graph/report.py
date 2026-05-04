"""분석 결과 dict → 마크다운 보고서 변환."""
import argparse


def build_report(args: argparse.Namespace, result: dict) -> str:
    """결과 dict → 마크다운 보고서 문자열."""
    header = f"# 뉴스 분석 보고서 [{args.market}] — {args.date} ({args.engine})\n\n"
    overall = f"## 전체 시장 요약\n\n{result.get('overall_analysis', '')}\n\n---\n\n"
    sectors_md = ""
    for sector, analysis in result.get("sector_analyses", {}).items():
        sectors_md += f"## {sector}\n\n{analysis}\n\n---\n\n"
    return header + overall + sectors_md
