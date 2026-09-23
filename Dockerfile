# ---- Frontend build ----------------------------------------------------------
FROM node:20-alpine AS ui
ENV NPM_CONFIG_FETCH_RETRIES=30 \
    NPM_CONFIG_FETCH_TIMEOUT=120000 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=2000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_MAXSOCKETS=6
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY ui/ ./
RUN --mount=type=cache,target=/root/.npm npm run build

# ---- Backend runtime -----------------------------------------------------------
FROM python:3.12-slim AS api
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 30 -r requirements.txt

COPY main.py ./
COPY src/ ./src/
COPY deploy/schema.sql ./deploy/schema.sql
COPY --from=ui /app/ui/dist ./ui/dist

RUN mkdir -p data output logs config

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]