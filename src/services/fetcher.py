"""Anti-bot fetch layer.

Provides a pluggable ``Fetcher`` so ecommerce crawling survives Cloudflare /
CAPTCHA walls and renders JavaScript-heavy stores (Shopify/WooCommerce flows).

Two implementations:

* ``HttpFetcher`` — plain HTTP (trafilatura + requests), cheap and fast, best
  for static pages and search snippets. No browser overhead.
* ``PlaywrightFetcher`` — headless Chromium that executes JS, waits through
  challenges, and routes traffic through an optional (residential) proxy.

Selection is driven by ``settings.FETCH_MODE``. Everything stays optional:
if Playwright/Chromium isn't installed, the pipeline degrades to HTTP.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import requests
from bs4 import BeautifulSoup

from src.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Normalized fetch output shared by every fetcher implementation."""

    url: str
    html: str
    final_url: str
    status_code: int
    effective_strategy: str  # "http" | "playwright"
    via_proxy: bool
    took_ms: int


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchResult | None:
        """Return rendered/extracted HTML for ``url`` or ``None`` on hard failure."""
        ...


def build_fetcher(mode: str | None = None, proxy: str | None = None) -> Fetcher:
    """Build the configured fetcher. Defaults to HTTP; Playwright when asked."""
    mode = (mode or settings.FETCH_MODE).lower()
    proxy = proxy if proxy is not None else settings.PROXY_URL
    if mode == "playwright":
        try:
            return PlaywrightFetcher(proxy=proxy)
        except Exception as exc:  # playwright or chromium missing
            logger.warning("Playwright unavailable (%s); falling back to HTTP.", exc)
    return HttpFetcher(proxy=proxy)


# ---------------------------------------------------------------------------
# HTTP fetcher (lightweight)
# ---------------------------------------------------------------------------


class HttpFetcher:
    """Plain HTTP fetch with retries, desktop browser headers, optional proxy."""

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy or None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def fetch(self, url: str) -> FetchResult | None:
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        last_exc: Exception | None = None
        for attempt in range(1, settings.FETCH_RETRIES + 2):
            start = time.monotonic()
            try:
                resp = self.session.get(
                    url, timeout=settings.FETCH_TIMEOUT, proxies=proxies,
                    headers={"User-Agent": self.session.headers["User-Agent"]},
                )
                if resp.status_code >= 400:
                    last_exc = RuntimeError(f"HTTP {resp.status_code}")
                    time.sleep(attempt)
                    continue
                return FetchResult(
                    url=url, html=resp.text, final_url=str(resp.url),
                    status_code=resp.status_code,
                    effective_strategy="http",
                    via_proxy=bool(self.proxy),
                    took_ms=int((time.monotonic() - start) * 1000),
                )
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(attempt)
        logger.debug("HTTP fetch failed for %s: %s", url, last_exc)
        return None


# ---------------------------------------------------------------------------
# Playwright fetcher (headless browser / JS rendering / challenges)
# ---------------------------------------------------------------------------


class PlaywrightFetcher:
    """Headless Chromium fetch with stealth headers, challenge wait, proxy."""

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy or None
        # Playwright is imported lazily so the rest of the stack works without it.
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright

    def _proxy_kwargs(self) -> dict:
        """Translate a proxy URL into Playwright launch/context kwargs."""
        if not self.proxy:
            return {}
        from urllib.parse import urlparse

        parsed = urlparse(self.proxy)
        spec = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 80}"
        return {"proxy": {"server": spec, "username": parsed.username, "password": parsed.password}}

    def fetch(self, url: str) -> FetchResult | None:
        from playwright.sync_api import TimeoutError as PWTimeout

        start = time.monotonic()
        for attempt in range(1, settings.FETCH_RETRIES + 2):
            try:
                return self._fetch_once(url)
            except PWTimeout:
                logger.debug("Playwright timeout on %s (attempt %d).", url, attempt)
                time.sleep(attempt)
        elapsed = int((time.monotonic() - start) * 1000)
        logger.warning("Playwright failed for %s after %dms.", url, elapsed)
        return None

    def _fetch_once(self, url: str) -> FetchResult:
        start = time.monotonic()
        with self._pw() as pw:
            browser = pw.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                slow_mo=settings.PLAYWRIGHT_SLOWMO_MS,
                **self._proxy_kwargs(),
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                locale="en-US",
                viewport={"width": 1366, "height": 768},
                **self._proxy_kwargs(),
            )
            page = context.new_page()
            page.set_default_timeout(settings.FETCH_TIMEOUT * 1000)
            resp = page.goto(url, wait_until="domcontentloaded")
            # Give JS-rendered content time to paint.
            page.wait_for_timeout(1200)
            html = page.content()
            status = resp.status if resp else 0
            final_url = page.url
            browser.close()
            return FetchResult(
                url=url, html=html, final_url=final_url, status_code=status,
                effective_strategy="playwright",
                via_proxy=bool(self.proxy),
                took_ms=int((time.monotonic() - start) * 1000),
            )


# ---------------------------------------------------------------------------
# Convenience: extract readable text (kept here so agents stay source-agnostic)
# ---------------------------------------------------------------------------


def readable_text(html: str) -> str:
    """Cheap DOM text extraction without trafilatura's meta HTTP calls."""
    try:
        from trafilatura import extract
        text = extract(html, include_comments=False, include_tables=True)
        if text:
            return text
    except Exception:
        pass
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return " ".join(soup.get_text(" ").split())[:20000]


def get_fetcher() -> Fetcher:
    """Module-level singleton fetcher so browsers aren't spawned per request here."""
    global _FETCHER
    if _FETCHER is None:
        _FETCHER = build_fetcher()
    return _FETCHER


_FETCHER: Fetcher | None = None