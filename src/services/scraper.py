"""Website scraper & fingerprinting.

Fetches a business site and extracts the signals the agents need:
readable text, HTML fingerprints (platform detection), contact info,
SSL, rough load time, broken links (sampled), and product/shop signals.

Fetching goes through the anti-bot layer (``fetcher.build_fetcher``): plain
HTTP by default, Playwright headless Chromium for JS-heavy / challenge-gated
stores when ``FETCH_MODE=playwright``. Optional proxy (residential exit) via
``PROXY_URL``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import trafilatura

from src.schemas import Platform
from src.services.fetcher import get_fetcher, readable_text

logger = logging.getLogger(__name__)

# (platform, regex) fingerprints checked against the raw HTML.
PLATFORM_FINGERPRINTS: list[tuple[Platform, str]] = [
    (Platform.SHOPIFY, r"shopify"),
    (Platform.WOOCOMMERCE, r"woocommerce"),
    (Platform.MAGENTO, r"magento"),
    (Platform.BIGCOMMERCE, r"bigcommerce"),
    (Platform.ETSY, r"etsy\.com/"),
    (Platform.AMAZON, r"amazon\.(com|eg|ae|sa|de|co\.uk)/"),
    (Platform.WIX, r"wix\.com|static\.wixstatic\.com"),
    (Platform.SQUARESPACE, r"squarespace"),
    (Platform.FACEBOOK_SHOP, r"facebook\.com/.{2,}/shop"),
    (Platform.INSTAGRAM_SHOP, r"instagram\.com"),
]

TRUST_WORDS = ("ssl", "secure checkout", "guarantee", "returns", "refund", "privacy policy", "terms")
CHECKOUT_WORDS = ("add to cart", "checkout", "buy now", "shop now")
CONTACT_WORDS = ("contact us", "about us", "shipping", "faq", "live chat")


@dataclass
class ScrapedPage:
    url: str
    title: str
    text: str
    word_count: int
    has_shop: bool
    has_checkout: bool
    has_trust_signals: int = 0
    has_contact_pages: int = 0
    broken_links: int = 0
    checked_links: int = 0
    has_ssl: bool = False
    load_time_ms: int = 0
    platform: Platform = Platform.UNKNOWN
    html_hits: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


def scrape_website(url: str, check_links_limit: int = 6) -> ScrapedPage | None:
    """Fetch ``url``, fingerprint the platform, and extract signals.

    Returns None when the site can't be fetched (offline / blocked).
    """
    if not url:
        return None
    try:
        fetcher = get_fetcher()
        result = fetcher.fetch(url)
        if result is None:
            return None
        raw_html = result.html
        final_url = result.final_url or url

        text = (
            trafilatura.extract(raw_html, include_comments=False)
            or readable_text(raw_html)
            or ""
        )
        low_html = raw_html.lower()
        text_low = text.lower()

        platform, hits = _detect_platform(final_url, low_html)

        emails = list(dict.fromkeys(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw_html)))[:5]
        phones = list(dict.fromkeys(re.findall(r"\+?[\d\s().-]{9,17}", text)))[:5]

        links = _extract_links(raw_html, final_url)
        broken, checked = _probe_links(links, check_links_limit)

        return ScrapedPage(
            url=final_url,
            title=_extract_title(text),
            text=text,
            word_count=len(text.split()),
            has_shop=_mentions(text_low, ("shop", "products", "collection", "catalog")),
            has_checkout=_mentions(text_low, CHECKOUT_WORDS),
            has_trust_signals=sum(_mentions(text_low, w) for w in TRUST_WORDS),
            has_contact_pages=sum(_mentions(text_low, w) for w in CONTACT_WORDS),
            broken_links=broken,
            checked_links=checked,
            has_ssl=result.effective_strategy == "playwright" or final_url.startswith("https://"),
            load_time_ms=result.took_ms,
            platform=platform,
            html_hits=hits,
            emails=emails,
            phones=phones,
            links=links,
        )
    except Exception:  # pragma: no cover - network dependent
        logger.warning("Scrape failed for %s", url)
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_platform(final_url: str, low_html: str) -> tuple[Platform, list[str]]:
    """Return (platform, matched fingerprints) from URL + HTML."""
    hits: list[str] = []
    for platform, pattern in PLATFORM_FINGERPRINTS:
        if re.search(pattern, low_html) or re.search(pattern, final_url.lower()):
            hits.append(platform.value)
    if hits:
        return Platform(hits[0]), hits
    return Platform.CUSTOM, hits


def _extract_links(html: str, base: str) -> list[str]:
    """Pull hrefs from anchor and similar tags (bs4 optional)."""
    import httpx

    links: list[str] = []
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True)[:40]:
            href = a["href"]
            if href.startswith("http"):
                links.append(href)
            elif href.startswith("/"):
                parsed = httpx.URL(base)
                links.append(f"{parsed.scheme}://{parsed.host}{href}")
    except Exception:  # bs4 missing or parse error
        links = re.findall(r'href="(https?://[^"]+)"', html)[:40]
    return list(dict.fromkeys(links))


def _probe_links(links: list[str], limit: int) -> tuple[int, int]:
    """Sample links and count non-200 responses."""
    import httpx

    broken = 0
    checked = 0
    with httpx.Client(
        timeout=httpx.Timeout(6.0),
        headers={"User-Agent": "ecom-intel/0.1 (research bot)"},
        follow_redirects=True,
        verify=False,
    ) as client:
        for href in links[:limit]:
            try:
                checked += 1
                if client.head(href).status_code >= 400:
                    broken += 1
            except Exception:
                broken += 1
                checked += 1
    return broken, checked


def _mentions(text: str, words: tuple[str, ...] | list[str]) -> bool:
    return any(w in text for w in words)


def _extract_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0][:120] if lines else ""