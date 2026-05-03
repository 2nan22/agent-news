# ─── Stage 1: 의존성 설치 ─────────────────────────────────────────────
FROM python:3.12-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ─── Stage 2: 프로덕션 이미지 ─────────────────────────────────────────
FROM deps AS production

# 소스 복사 (의존성 레이어는 캐시 유지)
COPY . .

# 컨테이너 시작 시 output/ 없으면 생성
RUN mkdir -p output

CMD ["python", "crew_agent.py"]
