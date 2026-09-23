"""Agent 9 — Website Security & Gap Auditor.

Combines a deterministic live scan (src.services.security) with an LLM pass:
the LLM turns the raw facts into per-category scores, a risk level, concrete
findings with remediation steps, a "what the website lacks" gap list, and a
friendly outreach message addressed to the website owner.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.services.security import SecurityScan, run_security_scan
from src.schemas import SecurityAnalysis, SecurityFinding, SecurityGap
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)


def _scan_block(scan: SecurityScan) -> str:
    """Render the raw scan facts into a compact prompt block."""
    lines = [
        f"URL: {scan.url}",
        f"Reachable: {scan.reachable}",
        f"HTTPS enforcement: {scan.https_enforced}",
        *[f"  - {o}" for o in scan.https_observations],
        f"TLS protocol: {scan.protocol or 'unknown'}",
        f"Cipher: {scan.cipher or 'unknown'}",
        f"Cert issuer: {scan.cert_issuer or 'unknown'}",
        f"Cert expires in (days): {scan.cert_expires_days if scan.cert_expires_days >= 0 else 'unknown'}",
        f"Legacy TLS allowed: {', '.join(scan.legacy_protocols) or 'none detected'}",
        "Security headers found:",
    ]
    for name, present in scan.security_headers.items():
        lines.append(f"  - {name}: {'present' if present else 'MISSING'}")
    lines.append(f"Cookies Secure flag: {scan.cookies_secure}")
    lines.append(f"Cookies HttpOnly flag: {scan.cookies_httponly}")
    lines.append(f"Login forms found: {scan.login_forms}")
    for form in scan.forms[:6]:
        lines.append(
            f"  - form method={form.get('method','?')} action={form.get('action','')} "
            f"inputs={form.get('inputs', {})}"
        )
    lines.append("Exposed/sensitive paths:")
    lines.append(f"  - {', '.join(scan.exposed_paths) or 'none found'}")
    lines.append("Auth endpoint enumeration:")
    lines.append(f"  - {', '.join(scan.auth_findings) or 'none checked'}")
    return "\n".join(lines)


PROMPT = """You are a website security & digital-presence auditor.
Analyze the REAL live scan facts of a website. Be honest: if the evidence is
missing or a check could not run, score conservatively and say so.

Return a SINGLE JSON object with this exact shape:
{
  "overall_score": 0,
  "risk_level": "low|medium|high|critical",
  "https": 0,
  "ssl_tls": 0,
  "authentication": 0,
  "input_validation": 0,
  "file_permissions": 0,
  "security_headers": 0,
  "findings": [
    {"severity":"low|medium|high|critical|info","category":"https|ssl_tls|authentication|input_validation|file_permissions|headers|cookies|general","title":"...","detail":"...","remediation":"..."}
  ],
  "gaps": [
    {"topic":"an area that is missing or weak","status":"present|weak|lacking","reason":"why it is lacking and why it matters","recommendation":"concrete AI recommendation to improve it"}
  ],
  "summary": "two sentence overall verdict",
  "outreach_message": "A professional, friendly, 4-6 sentence message addressed to the website owner, mentioning the top issues found, why fixing them matters, and a gentle call to action."
}
Rules:
- Each score 0-100 where 100 is the most secure / best state.
- https: HTTPS enforced? score high only when plain HTTP redirects or is refused.
- ssl_tls: modern TLS (1.2/1.3), valid non-expiring cert, no legacy versions.
- authentication: login/access control is enforced on admin surfaces (401/403 are good).
- input_validation: forms exist and use typed inputs; missing forms/password fields are a gap.
- file_permissions: no sensitive files (.env, .git, backups, configs) exposed.
- security_headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options etc.
- List at least 3 "gaps" covering security AND general website items that are lacking
  (e.g. no HTTPS, missing privacy policy, weak SSL config, exposed config files,
  no contact page, missing mobile optimization, slow loading) with reasons.
- JSON only, no markdown.
"""


class SecurityAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, url: str, business_id: str = "") -> SecurityAnalysis:
        scan = run_security_scan(url)
        user = _scan_block(scan)
        parsed = ask(self.llm, PROMPT, user)

        analysis = SecurityAnalysis(
            business_id=business_id or url,
            url=url,
            overall_score=int((parsed or {}).get("overall_score") or 0),
            risk_level=(parsed or {}).get("risk_level", "unknown"),
            https=int((parsed or {}).get("https") or 0),
            ssl_tls=int((parsed or {}).get("ssl_tls") or 0),
            authentication=int((parsed or {}).get("authentication") or 0),
            input_validation=int((parsed or {}).get("input_validation") or 0),
            file_permissions=int((parsed or {}).get("file_permissions") or 0),
            security_headers=int((parsed or {}).get("security_headers") or 0),
            protocol=scan.protocol,
            cipher=scan.cipher,
            cert_issuer=scan.cert_issuer,
            cert_expires_days=scan.cert_expires_days,
            https_enforced=scan.https_enforced,
            security_headers_found=dict(scan.security_headers),
            cookies_secure=scan.cookies_secure,
            cookies_httponly=scan.cookies_httponly,
            exposed_paths=as_str_list(scan.exposed_paths),
            checks_performed=list(scan.checks),
            findings=_build_findings(scan, parsed),
            gaps=_build_gaps(parsed),
            summary=(parsed or {}).get("summary", ""),
            outreach_message=(parsed or {}).get("outreach_message", ""),
        )
        return analysis


def _build_findings(scan: SecurityScan, parsed) -> list[SecurityFinding]:
    """Merge LLM findings with deterministic facts we can always state."""
    findings: list[SecurityFinding] = []

    raw = (parsed or {}).get("findings")
    if isinstance(raw, list):
        for f in raw:
            if not isinstance(f, dict):
                continue
            findings.append(SecurityFinding(
                severity=str(f.get("severity") or "info"),
                category=str(f.get("category") or "general"),
                title=str(f.get("title") or ""),
                detail=str(f.get("detail") or ""),
                remediation=str(f.get("remediation") or ""),
            ))

    if not scan.https_enforced:
        findings.append(SecurityFinding(
            severity="high", category="https",
            title="HTTPS is not enforced",
            detail="The site does not force HTTPS; visitors can reach it over plain HTTP.",
            remediation="Redirect all HTTP traffic to HTTPS with a 301 and enable HSTS.",
        ))
    if scan.legacy_protocols:
        findings.append(SecurityFinding(
            severity="medium", category="ssl_tls",
            title="Legacy TLS versions accepted",
            detail=f"Server negotiates {', '.join(scan.legacy_protocols)}.",
            remediation="Disable TLS 1.0/1.1 and require TLS 1.2+ (IDEALLY TLS 1.3).",
        ))
    if 0 <= scan.cert_expires_days <= 30:
        findings.append(SecurityFinding(
            severity="high", category="ssl_tls",
            title="SSL certificate is about to expire",
            detail=f"Certificate expires in {scan.cert_expires_days} days.",
            remediation="Renew the certificate now and set up auto-renewal.",
        ))
    if scan.cert_expires_days == -1:
        findings.append(SecurityFinding(
            severity="medium", category="ssl_tls",
            title="Certificate expiry could not be verified",
            detail="The TLS handshake did not expose certificate dates.",
            remediation="Verify the certificate is valid and auto-renewing.",
        ))
    missing = [n for n, present in scan.security_headers.items() if not present]
    if missing:
        findings.append(SecurityFinding(
            severity="medium", category="headers",
            title="Missing security headers",
            detail=f"Missing: {', '.join(missing)}.",
            remediation="Set HSTS, Content-Security-Policy, X-Frame-Options, "
                       "X-Content-Type-Options and Referrer-Policy.",
        ))
    if not scan.cookies_secure or not scan.cookies_httponly:
        flags = []
        if not scan.cookies_secure:
            flags.append("Secure")
        if not scan.cookies_httponly:
            flags.append("HttpOnly")
        findings.append(SecurityFinding(
            severity="medium", category="cookies",
            title="Cookies miss security flags",
            detail=f"Missing flags: {', '.join(flags) or 'cookie flags unknown'}.",
            remediation="Set Secure + HttpOnly on every cookie, and SameSite accordingly.",
        ))
    if scan.exposed_paths:
        findings.append(SecurityFinding(
            severity="high", category="file_permissions",
            title="Sensitive path exposed",
            detail="Accessible: " + ", ".join(scan.exposed_paths[:8]) + ".",
            remediation="Block these paths at the web server, restrict file permissions "
                       "and remove backups/configs from the web root.",
        ))
    return findings


def _build_gaps(parsed) -> list[SecurityGap]:
    gaps: list[SecurityGap] = []
    raw = (parsed or {}).get("gaps")
    if not isinstance(raw, list):
        return gaps
    for g in raw:
        if not isinstance(g, dict):
            continue
        gaps.append(SecurityGap(
            topic=str(g.get("topic") or ""),
            status=str(g.get("status") or "lacking"),
            reason=str(g.get("reason") or ""),
            recommendation=str(g.get("recommendation") or ""),
        ))
    return [g for g in gaps if g.topic]