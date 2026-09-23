"""Application configuration.

All runtime settings come from environment variables (or a local .env file)
so the system can run anywhere without code changes. Defaults target a fully
local setup driven by Ollama.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # --- Local LLM provider (Ollama) ---
    # Any model you have pulled locally, e.g. "llama3.1", "qwen2.5",
    # "mistral", "deepseek-r1", "phi3".
    OLLAMA_MODEL: str = "llama3.1"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # Max output tokens per LLM call.
    OLLAMA_MAX_TOKENS: int = 2048
    OLLAMA_TEMPERATURE: float = 0.2
    # Optional per-agent-role model overrides (JSON object in .env).
    OLLAMA_ROLE_MODELS: dict[str, str] = {}

    # Optional remote provider (OpenAI-compatible chat). Kept for platforms
    # that don't fit the named presets below (e.g. Groq-compatible endpoints).
    FALLBACK_PROVIDER: str = "none"  # "none" | "groq" | "openrouter" | "cerebras" | "gemini" | "openai-compatible"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Provider API keys + endpoints (OpenAI-compatible chat interface).
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_BASE_URL: str = "https://api.cerebras.ai/v1"
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Embeddings provider ("gemini" | "openai-compatible" | "ollama") for the
    # pgvector semantic memory (Agent 6/7). Default free options below.
    EMBEDDING_PROVIDER: str = "gemini"
    EMBEDDING_MODEL: str = "gemini-embedding-2"   # Gemini free embedding model
    EMBEDDING_DIM: int = 768

    # --- Workflow tuning ---
    # How many businesses to scan per discovery run.
    DISCOVERY_TARGET: int = 10
    # Minimum confidence score (0-100) a business must reach to be kept.
    MIN_CONFIDENCE: int = 50
    # Number of parallel Analysis sub-agents.
    ANALYSIS_WORKERS: int = 3

    # --- Data storage ---
    DATA_DIR: str = "data"
    OUTPUT_DIR: str = "output"
    LOG_DIR: str = "logs"

    # --- Google Sheets knowledge base (optional) ---
    GOOGLE_SHEETS_CREDENTIALS: str = ""  # path to service-account.json
    GOOGLE_SHEETS_ID: str = ""           # spreadsheet id from the sheet URL

    # --- Scheduling (APScheduler) ---
    SCHEDULER_ENABLED: bool = False
    DAILY_HOUR: int = 6
    DAILY_MINUTE: int = 0
    WEEKLY_DAY: str = "mon"     # day of week for the weekly job
    WEEKLY_HOUR: int = 6
    MONTHLY_DAY: int = 1        # day of month for the monthly job
    QUARTERLY_MONTHS: str = "1,4,7,10"
    YEARLY_MONTH: int = 1

    # --- Anti-bot fetch layer ---
    # "http" (plain) or "playwright" (headless Chromium for JS-heavy sites).
    FETCH_MODE: str = "http"
    # Optional proxy URL, e.g. http://user:pass@host:port for a residential exit.
    PROXY_URL: str = ""
    # Seconds between fetch attempts, capped attempts per page.
    FETCH_RETRIES: int = 2
    FETCH_TIMEOUT: int = 30
    # Playwright options.
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_SLOWMO_MS: int = 0
    PLAYWRIGHT_STEALTH: bool = True  # mask headless fingerprints + real user-agent

    # --- Data-source API adapters (leave provider "none" for local/DuckDuckGo) ---
    # Lead discovery: "none" | "serper" | "value_serp" | "data_for_seo"
    SERP_PROVIDER: str = "none"
    SERPER_API_KEY: str = ""
    VALUE_SERP_API_KEY: str = ""
    DATA_FOR_SEO_USER: str = ""
    DATA_FOR_SEO_PASSWORD: str = ""
    PAGESPEED_API_KEY: str = ""          # free Google PageSpeed Insights key
    # SEO datasets: "none" | "ahrefs" | "semrush" | "moz"
    SEO_PROVIDER: str = "none"
    AHREFS_API_LINK: str = "https://apiv2.ahrefs.com"
    AHREFS_API_KEY: str = ""
    SEMRUSH_API_KEY: str = ""
    MOZ_ACCESS_ID: str = ""
    MOZ_SECRET_KEY: str = ""
    # Social listening: "none" | "apify" | "brandwatch"
    SOCIAL_PROVIDER: str = "none"
    APIFY_API_KEY: str = ""
    BRANDWATCH_API_TOKEN: str = ""

    # --- PostgreSQL + pgvector knowledge base (optional) ---
    DATABASE_URL: str = ""               # e.g. postgresql://user:pass@host:5432/ecom
    DB_POOL_SIZE: int = 5

    # --- Distributed tasks (Celery + Redis, optional) ---
    USE_CELERY: bool = False             # dispatch deepdive per-lead to Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # --- API + dashboard ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DASHBOARD_TITLE: str = "ecom-intel Dashboard"
    DASHBOARD_DATABASE_URL: str = ""     # overrides DATABASE_URL for dashboard reads

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# --- Derived paths ---
for _dir in (settings.DATA_DIR, settings.OUTPUT_DIR, settings.LOG_DIR):
    os.makedirs(_dir, exist_ok=True)