"""Data-source adapters.

Every optional third-party API is wrapped behind a tiny adapter so the agents
stay source-agnostic. Providers are selected by env vars and disabled by
default ("none") — the local pipeline keeps working with zero keys.

Layers delivered here:
  - SERP / Google Maps  (Value Serp or DataForSEO)   -> lead discovery
  - PageSpeed           (Google PSI, free key)        -> Agent 2 website scores
  - SEO data            (Ahrefs / SEMrush / Moz)      -> Agent 2/3 signals
  - Social listening    (Apify / Brandwatch)          -> Agent 4 metrics
"""

from __future__ import annotations

import logging

from src.config.settings import settings

logger = logging.getLogger(__name__)

# Avoid import cost + hard failures when libraries are missing by importing
# adapters lazily inside the factory functions.


def serp_adapter():
    """Structured SERP / Maps adapter or None when not configured."""
    if settings.SERP_PROVIDER == "serper":
        from src.services.sources.serper import SerperAdapter

        if not settings.SERPER_API_KEY:
            logger.warning("SERP provider 'serper' configured but no SERPER_API_KEY set.")
            return None
        return SerperAdapter()

    from src.services.sources.serp import SerpAdapter

    if settings.SERP_PROVIDER not in ("value_serp", "data_for_seo"):
        return None
    adapter = SerpAdapter(provider=settings.SERP_PROVIDER)
    if not adapter.available:
        logger.warning("SERP provider '%s' configured but no credentials set.", settings.SERP_PROVIDER)
        return None
    return adapter


def pagespeed_adapter():
    """Google PageSpeed Insights adapter or None when no key."""
    from src.services.sources.pagespeed import PageSpeedAdapter

    if not settings.PAGESPEED_API_KEY:
        return None
    return PageSpeedAdapter(settings.PAGESPEED_API_KEY)


def seo_adapter():
    """SEO dataset adapter or None when not configured."""
    from src.services.sources.seo import SeoAdapter

    if settings.SEO_PROVIDER not in ("ahrefs", "semrush", "moz"):
        return None
    adapter = SeoAdapter(provider=settings.SEO_PROVIDER)
    if not adapter.available:
        logger.warning("SEO provider '%s' configured but missing credentials.", settings.SEO_PROVIDER)
        return None
    return adapter


def social_adapter():
    """Social listening adapter or None when not configured."""
    from src.services.sources.social import SocialAdapter

    if settings.SOCIAL_PROVIDER not in ("apify", "brandwatch"):
        return None
    adapter = SocialAdapter(provider=settings.SOCIAL_PROVIDER)
    if not adapter.available:
        logger.warning("Social provider '%s' configured but missing credentials.", settings.SOCIAL_PROVIDER)
        return None
    return adapter