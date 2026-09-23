"""Live website security scanner.

Probes the actual target over the network and returns deterministic facts
about HTTPS enforcement, SSL/TLS configuration, security headers, cookie
flags, form/input handling, and exposure of sensitive files & endpoints.

All network work is bounded (short timeouts, concurrent probes) so the
scanner adds only a few seconds to a pipeline run. Results are consumed by
``src.agents.security.SecurityAgent`` which turns the facts into the typed
``SecurityAnalysis`` verdict.
"""

from __future__ import annotations

import logging
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Security-relevant response headers worth checking.
HARDENING_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "x-xss-protection",
    "permissions-policy",
]

# Paths probed for hidden config/exposure (GET). Responses that are NOT
# 404/403/401 count as a potential exposure.
SENSITIVE_PATHS = [
    "/.env",
    "/.git/HEAD",
    "/.git/config",
    "/config.php",
    "/configuration.yml",
    "/db.sql",
    "/database.sql",
    "/backup.zip",
    "/wp-config.php.bak",
    "/appsettings.json",
    "/.htaccess",
]

# Paths probed to evaluate authentication & access control. 401/403 = good
# (auth enforced). 200 with content = weak access control.
AUTH_PATHS = [
    "/admin",
    "/dashboard",
    "/wp-admin",
    "/wp-login.php",
    "/login",
    "/user",
    "/account",
    "/api/",
]

# "Good" responses we accept when enumerating exposed paths.
GOOD_STATUS = {200, 202, 204, 206, 301, 302, 303, 307, 308}
NEUTRAL_STATUS = {403, 404, 405, 406, 429, 400, 410, 501}


@dataclass
class SecurityScan:
    """Raw deterministic facts collected from the live site."""

    url: str
    final_url: str = ""
    reachable: bool = False
    https_enforced: bool = False
    https_observations: list[str] = field(default_factory=list)
    protocol: str = ""            # negotiated TLS protocol e.g. TLSv1.3
    cipher: str = ""              # negotiated TLS cipher
    cert_issuer: str = ""
    cert_expires_days: int = 0
    legacy_protocols: list[str] = field(default_factory=list)  # e.g. ["tls1.0"]
    security_headers: dict[str, bool] = field(default_factory=dict)
    cookies_secure: bool = False
    cookies_httponly: bool = False
    forms: list[dict] = field(default_factory=list)  # method, action, input types
    login_forms: int = 0
    exposed_paths: list[str] = field(default_factory=list)
    auth_findings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Low-level probes
# ---------------------------------------------------------------------------


def _tls_probe(host: str, port: int = 443, min_version: ssl._SSLMethod | None = None) -> dict | None:
    """Connect + handshake, return TLS protocol/cipher/cert facts."""
    try:
        ctx = ssl.create_default_context()
        if min_version is not None:
            ctx.minimum_version = min_version
        with socket.create_connection((host, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                return {
                    "protocol": tls.version(),
                    "cipher": tls.cipher()[0] if tls.cipher() else "",
                    "cert_der": tls.getpeercert(binary_form=True),
                }
    except Exception as exc:
        logger.debug("TLS probe %s:%s (min=%s) failed: %s", host, port, min_version, exc)
        return None


def _cert_info(cert_der: bytes | None) -> tuple[str, int]:
    """Return (issuer rfc4514, days-until-expiry) from DER cert bytes."""
    if not cert_der:
        return "", -1
    try:
        from cryptography import x509

        cert = x509.load_der_x509_certificate(cert_der)
        issuer = cert.issuer.rfc4514_string()[:160]
        not_after = cert.not_valid_after_utc
        days = (not_after - datetime.now(timezone.utc)).days
        return issuer, days
    except Exception as exc:
        logger.debug("Cert parse failed: %s", exc)
        return "", -1


def _https_enforcement(url: str) -> tuple[bool, list[str]]:
    """Check whether plain http redirects to https (or is refused)."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False, ["Target was not served over HTTPS."]
    http_url = f"http://{parsed.netloc}/"
    observations: list[str] = []
    try:
        with httpx.Client(
            timeout=httpx.Timeout(8.0), follow_redirects=False,
            headers={"User-Agent": "ecom-intel-security-scan"},
            verify=False,
        ) as client:
            resp = client.get(http_url)
            location = resp.headers.get("location", "")
            status = resp.status_code
            if status in (301, 302, 303, 307, 308) and location.startswith("https"):
                observations.append(f"HTTP → HTTPS redirect enforced ({status}).")
                return True, observations
            if status >= 400:
                observations.append(f"Plain HTTP returned {status}; not serving the site over HTTP.")
                return True, observations
            observations.append(f"Plain HTTP served content with status {status} — no HTTPS enforcement.")
            return False, observations
    except httpx.HTTPError as exc:
        # Connection failed/refused → the site does not answer over plain HTTP.
        observations.append("Plain HTTP connection refused/dropped — HTTPS-only is implied.")
        return True, observations


def _probe(path: str, base_url: str, client: httpx.Client) -> tuple[str, int, bool]:
    """GET one path; return (path, status_code, exposed_flag)."""
    url = f"{base_url.rstrip('/')}{path}"
    try:
        resp = client.get(url)
        status = resp.status_code
        content = resp.headers.get("content-type", "") or ""
        exposed = status in GOOD_STATUS and "text/html" not in content
        # Treat a real page at a sensitive path as exposure too.
        if status in GOOD_STATUS:
            exposed = True
        return path, status, exposed
    except httpx.HTTPError:
        return path, 0, False


def run_security_scan(url: str) -> SecurityScan:
    """Scan a live url and return the raw facts (no LLM involved)."""
    scan = SecurityScan(url=url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        scan.checks.append("Invalid URL scheme.")
        return scan

    host = parsed.hostname or ""
    https_url = f"https://{parsed.netloc}/"
    try:
        resp = httpx.get(
            https_url,
            timeout=httpx.Timeout(8.0),
            follow_redirects=False,
            headers={"User-Agent": "ecom-intel-security-scan"},
            verify=False,
        )
        scan.reachable = True
        scan.final_url = str(resp.url)
        scan.checks.append("Homepage fetched over HTTPS.")
    except httpx.HTTPError as exc:
        logger.warning("Security scan could not reach %s: %s", url, exc)
        scan.checks.append(f"Homepage unreachable over HTTPS ({exc.__class__.__name__}).")
        return scan

    # -- HTTPS enforcement ------------------------------------------------
    scan.https_enforced, obs = _https_enforcement(url)
    scan.https_observations = obs
    scan.checks.append("HTTP→HTTPS redirect check.")

    # -- TLS + certificate ------------------------------------------------
    probe = _tls_probe(host, 443)
    if probe:
        scan.protocol = probe.get("protocol", "")
        scan.cipher = probe.get("cipher", "")
        scan.cert_issuer, scan.cert_expires_days = _cert_info(probe.get("cert_der"))
        # Negotiated protocol is the baseline; check whether legacy is allowed.
        for label, ver in (("TLSv1", ssl.TLSVersion.TLSv1), ("TLSv1.1", ssl.TLSVersion.TLSv1_1)):
            legacy = _tls_probe(host, 443, min_version=ver)
            if legacy:
                scan.legacy_protocols.append(label.lower())
            break  # first legacy handshake answer decides
        scan.checks.append("TLS handshake + certificate inspection.")

    # Split out headers from the homepage response.
    headers = {k.lower(): v for k, v in resp.headers.items()}
    for name in HARDENING_HEADERS:
        scan.security_headers[name] = bool(headers.get(name))

    # -- Cookie flags ------------------------------------------------------
    set_cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [resp.headers.get("set-cookie", "")]
    scan.cookies_secure = all("secure" in (c or "").lower() for c in set_cookies if c)
    scan.cookies_httponly = all("httponly" in (c or "").lower() for c in set_cookies if c)

    # -- Forms & input validation -----------------------------------------
    html = resp.text
    try:
        from bs4 import BeautifulSoup
    except Exception:
        BeautifulSoup = None
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for form in soup.find_all("form"):
            method = (form.get("method") or "get").lower()
            action = form.get("action") or ""
            inputs = {"password": False, "email": False, "file": False, "hidden": False, "text": 0, "number": 0}
            for inp in form.find_all("input"):
                it = (inp.get("type") or "text").lower()
                if it == "password":
                    inputs["password"] = True
                elif it == "email":
                    inputs["email"] = True
                elif it == "file":
                    inputs["file"] = True
                elif it == "hidden":
                    inputs["hidden"] = True
                elif it == "text":
                    inputs["text"] += 1
                elif it == "number":
                    inputs["number"] += 1
            scan.forms.append({"method": method, "action": action, "inputs": inputs})
            if inputs["password"]:
                scan.login_forms += 1
    scan.checks.append("Form/input parsing for validation signals.")

    # -- Sensitive path + auth enumeration (concurrent) --------------------
    with httpx.Client(
        timeout=httpx.Timeout(6.0), follow_redirects=False,
        headers={"User-Agent": "ecom-intel-security-scan"},
        verify=False,
    ) as client:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(_probe, p, https_url, client) for p in SENSITIVE_PATHS + AUTH_PATHS]
            for fut in as_completed(futs):
                try:
                    path, status, exposed = fut.result()
                except Exception:
                    continue
                if path in SENSITIVE_PATHS:
                    if status in GOOD_STATUS and exposed:
                        scan.exposed_paths.append(f"{path} (HTTP {status})")
                else:
                    # auth path
                    if status in NEUTRAL_STATUS:
                        scan.auth_findings.append(f"{path} → {status} (access denied/not present).")
                    elif status in GOOD_STATUS:
                        scan.auth_findings.append(f"{path} → {status} (reachable without auth).")

    scan.checks.append("Sensitive path & auth surface enumeration.")
    return scan