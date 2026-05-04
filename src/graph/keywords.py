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
