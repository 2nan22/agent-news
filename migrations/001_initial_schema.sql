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
    ('SEMICONDUCTOR', '반도체',  'Semiconductor',          'KR',  1),
    ('AI',            'AI',      'Artificial Intelligence', 'ALL', 2),
    ('SHIPBUILDING',  '조선',    'Shipbuilding',            'KR',  3),
    ('RAW_MATERIALS', '원자재',  'Raw Materials',           'ALL', 4),
    ('ENERGY',        '에너지',  'Energy',                  'ALL', 5),
    ('FINANCE',       '금융',    'Finance',                 'ALL', 6)
ON CONFLICT (sector_code) DO NOTHING;

COMMIT;
