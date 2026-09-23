"""LLM factory with per-agent model routing.

Returns a chat model configured to talk to a local Ollama instance
(optionally falling back to an OpenAI-compatible endpoint). Different agents
can use different open-source models — see ``MODEL_ASSIGNMENTS`` — so you can
route each role to the model it's best at (e.g. DeepSeek for reasoning-heavy
synthesis, Qwen for flawless structured JSON, Llama for general tool-accuracy
work) without changing the agents' code.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Role -> Ollama model name. Pull these locally with:
#   ollama pull llama3.3:70b
#   ollama pull qwen2.5:72b
#   ollama pull deepseek-r1:70b   (or whatever deepseek variant you pulled)
#
# Model routing rationale (128K context on all three):
#   1. Tool calling & structured extraction (Discovery, Website, storage):
#      Llama 3.3 + Qwen 2.5 — native function calling, strict JSON schemas
#      that feed the database cleanly.
#   2. Mass content & context handling (Marketing, Social, Sentiment):
#      Qwen/Llama 128K windows digest whole digital footprints without
#      dropping earlier context.
#   3. Deep logical analysis & roadmap synthesis (Product Trend, Competitor,
#      Recommendation): DeepSeek-R1 chain-of-thought cross-references
#      competitors and derives prioritised, premium-tier roadmaps.
MODEL_ASSIGNMENTS: dict[str, str] = {
    "discovery": "llama3.3:70b",       # Llama 3.3 — structured extraction
    "website": "qwen2.5:72b",          # Qwen 2.5 — flawless strict JSON schemas
    "marketing": "llama3.3:70b",       # Llama 3.3 — 128K mass-content handling
    "social": "qwen2.5:72b",           # Qwen 2.5 — feed ingestion + struct JSON
    "product_trend": "deepseek-r1:70b",  # DeepSeek-R1 — logical market analysis
    "sentiment": "qwen2.5:72b",        # Qwen 2.5 — 128K review digestion + JSON
    "competitor": "deepseek-r1:70b",   # DeepSeek-R1 — chain-of-thought comparison
    "recommendation": "deepseek-r1:70b",  # DeepSeek-R1 — strategic roadmap synthesis
}

# Note: the "AI Scoring System" needs no LLM — it is deterministic arithmetic
# (see src/scoring.py), which keeps scores reproducible across runs. The
# evidence that feeds it comes from the Qwen-routed agents.


def _resolved_assignments() -> dict[str, str]:
    """Env-provided OLLAMA_ROLE_MODELS overrides win; else built-in routing."""
    return {**MODEL_ASSIGNMENTS, **settings.OLLAMA_ROLE_MODELS}

# Map convenience: roles not in the lookup fall back to the default model.
_ROLE_MODEL_FALLBACK = "OLLAMA_MODEL"

# ---------------------------------------------------------------------------
# Remote OpenAI-compatible providers (free tiers). Each maps agent roles to a
# provider-native model id; roles without an explicit entry use the provider's
# `default`. Set FALLBACK_PROVIDER + the matching *_API_KEY in .env to enable.
# ---------------------------------------------------------------------------
# Provider name -> {"base_url", "api_key", "default", "roles": {role: model}}
REMOTE_PROVIDERS: dict[str, dict[str, str | dict[str, str]]] = {
    # openai/gpt-oss is the model family available on this account's free tier.
    # 20B = fast structured extraction; 120B = deeper reasoning/synthesis.
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "GROQ_API_KEY",
        "default": "openai/gpt-oss-20b",
        "roles": {
            "discovery": "openai/gpt-oss-20b",
            "website": "openai/gpt-oss-20b",
            "marketing": "openai/gpt-oss-120b",
            "social": "openai/gpt-oss-20b",
            "sentiment": "openai/gpt-oss-120b",
            "product_trend": "openai/gpt-oss-120b",
            "competitor": "openai/gpt-oss-120b",
            "recommendation": "openai/gpt-oss-120b",
        },
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "OPENROUTER_API_KEY",
        # Free-tier slugs verified against the live catalog (2026-09): the old
        # llama-3.3-70b-instruct:free / deepseek-r1:free slugs now return 404.
        "default": "nvidia/nemotron-3-super-120b-a12b:free",
        "roles": {
            "discovery": "nvidia/nemotron-3-super-120b-a12b:free",
            "website": "nvidia/nemotron-3-super-120b-a12b:free",
            "marketing": "nvidia/nemotron-3-super-120b-a12b:free",
            "social": "openrouter/free",
            "sentiment": "openrouter/free",
            "product_trend": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "competitor": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "recommendation": "nvidia/nemotron-3-ultra-550b-a55b:free",
        },
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": "CEREBRAS_API_KEY",
        "default": "gpt-oss-120b",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": "GEMINI_API_KEY",
        "default": "gemini-3.6-flash",
    },
}


# Failover order: the FALLBACK_PROVIDER always runs first; the remaining
# providers (in this order) kick in automatically when it hits a rate limit,
# times out, or returns a model/API error. Providers without a configured key
# are skipped.
_PROVIDER_PRIORITY = ["openrouter", "cerebras", "gemini"]


def _provider_model(provider: str, role: str) -> str:
    cfg = REMOTE_PROVIDERS[provider]
    roles = cfg.get("roles") or {}
    return roles.get(role, cfg["default"]) if role != "default" else cfg["default"]


def _chat_for(provider: str, role: str, temperature: float):
    from langchain_openai import ChatOpenAI

    cfg = REMOTE_PROVIDERS[provider]
    api_key = getattr(settings, str(cfg["api_key"])) or settings.OPENAI_API_KEY
    return ChatOpenAI(
        model=_provider_model(provider, role),
        api_key=api_key,
        base_url=settings.GEMINI_BASE_URL if provider == "gemini" else cfg["base_url"],
        temperature=temperature,
        timeout=120,
        max_retries=1,
    )


def _remote_chain(role: str, temperature: float):
    """Ordered list of configured remote clients for ``role`` (primary first)."""
    from langchain_core.exceptions import (
        ModelConnectionError,
        ModelError,
        ModelRateLimitError,
        ModelTimeoutError,
    )

    primary = settings.FALLBACK_PROVIDER
    providers = [primary, *[p for p in _PROVIDER_PRIORITY if p != primary]]
    chain = []
    for provider in providers:
        cfg = REMOTE_PROVIDERS.get(provider)
        if not cfg:
            continue
        api_key = getattr(settings, str(cfg["api_key"]))
        if not api_key and not settings.OPENAI_API_KEY:
            continue
        chain.append(_chat_for(provider, role, temperature))

    if len(chain) <= 1:
        return chain, ()

    exceptions = (ModelRateLimitError, ModelTimeoutError, ModelConnectionError, ModelError)
    return chain, exceptions


def get_llm_rotation(
    role: str = "default",
    temperature: Optional[float] = None,
) -> list[BaseChatModel]:
    """Return one configured remote client per provider, primary first.

    Unlike ``get_llm`` (which hides providers behind ``with_fallbacks``),
    this returns the raw list so callers can actively rotate providers when
    one returns syntactically invalid output (which fallbacks never see,
    since they only fire on model/API exceptions).
    """
    temp = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
    chain, _exceptions = _remote_chain(role, temp)
    return chain


def get_llm(
    role: str = "default",
    temperature: Optional[float] = None,
) -> BaseChatModel:
    """Return a chat model for the given agent role.

    ``role`` selects the model from ``MODEL_ASSIGNMENTS``; unknown roles and
    the OpenAI-compatible fallback use the default settings.

    When a remote provider is configured, the call is wrapped with
    ``with_fallbacks`` so every other provider that has an API key in .env
    takes over automatically if the primary one rate-limits, times out, or
    returns a model/API error (e.g. hitting a daily cap) — no code changes
    needed in the agents.
    """
    provider = settings.FALLBACK_PROVIDER
    if provider and provider != "none":
        cfg = REMOTE_PROVIDERS.get(provider)
        if cfg:
            api_key = getattr(settings, str(cfg["api_key"])) or settings.OPENAI_API_KEY
            if api_key:
                temp = temperature if temperature is not None else settings.OLLAMA_TEMPERATURE
                chain, exceptions = _remote_chain(role, temp)
                if not chain:
                    logger.warning("Provider '%s' configured but missing its API key.", provider)
                else:
                    primary, *fallbacks = chain
                    if fallbacks and exceptions:
                        wrapped = primary.with_fallbacks(
                            fallbacks,
                            exceptions_to_handle=exceptions,
                        )
                        logger.debug(
                            "Routing role %r with %d fallback providers (first: %s/%s)",
                            role, len(fallbacks), provider, primary.model,
                        )
                        return wrapped
                    return primary
            logger.warning("Provider '%s' configured but missing its API key.", provider)

    if settings.FALLBACK_PROVIDER == "openai-compatible" and settings.OPENAI_API_KEY:
        # Local Ollama not available: delegate to an OpenAI-compatible endpoint.
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            temperature=temperature if temperature is not None else settings.OLLAMA_TEMPERATURE,
        )

    # Local Ollama path (requires ollama serve; empty models on failure).
    model = _resolved_assignments().get(role, settings.OLLAMA_MODEL)
    try:
        llm = ChatOllama(
            model=model,
            base_url=settings.OLLAMA_BASE_URL,
            num_predict=settings.OLLAMA_MAX_TOKENS,
            temperature=temperature if temperature is not None else settings.OLLAMA_TEMPERATURE,
        )
    except Exception as exc:  # noqa: BLE001 - fall back to a bare client
        logger.warning("Ollama unavailable (%s); roles without a free provider key will fail at call time.", exc)
        llm = ChatOllama(
            model=model,
            base_url=settings.OLLAMA_BASE_URL,
            num_predict=settings.OLLAMA_MAX_TOKENS,
        )
    logger.debug("Routing role '%s' -> %s model '%s'", role, provider or "ollama", model)
    return llm


def get_llm_for(agent_role: str) -> BaseChatModel:
    """Shorthand used by the pipeline to build each agent's dedicated model."""
    return get_llm(role=agent_role)