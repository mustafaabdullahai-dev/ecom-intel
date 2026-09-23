"""Deterministic scoring engine.

Maps the seven intelligence agents' outputs onto the standardized 14-score
model and computes the lead-qualification tier. Everything here is pure
arithmetic (no LLM) so scores and priorities stay consistent across runs —
only agent *evidence* drives the numbers.

Score definitions:
  website              capability of the online store itself
  seo                  organic-search readiness
  marketing            marketing maturity
  brand                brand consistency & positioning strength
  social               social presence strength
  content              content quality & blog/creative strength
  customer_experience  usability + checkout + support experience
  trust                trust signals, policies, security, reputation
  technical            performance, CWV, indexability, security
  product_trend        product-line market opportunity
  growth_potential     headroom: how much upside the business has
  lead_qualification   how good a sales prospect this is (weakness + potential)
  business_health      average of capability scores (higher = healthier)
  ai_opportunity       overall AI-driven service opportunity for us
"""

from __future__ import annotations

from statistics import mean

from src.schemas import (
    BusinessIntelligence,
    LeadPriority,
    LeadQualification,
    Scores,
)


def _avg(values: list[int]) -> int:
    return int(round(mean(values))) if values else 0


def _cat(analysis, key: str) -> int:
    """Read one 0-100 category score off a WebsiteAnalysis (0 when absent)."""
    if analysis is None or analysis.categories is None:
        return 0
    return int(getattr(analysis.categories, key, 0) or 0)


def score_business(intel: BusinessIntelligence) -> Scores:
    """Compute the 14 scores for one business from its agent outputs."""
    w = intel.website
    m = intel.marketing
    s = intel.social
    p = intel.product_trend
    se = intel.sentiment
    c = intel.competitor

    # --- website + seo (from Agent 2 category scores) ----------------------
    website = _avg([
        _cat(w, "homepage_quality"), _cat(w, "navigation"), _cat(w, "user_experience"),
        _cat(w, "mobile_responsiveness"), _cat(w, "website_speed"), _cat(w, "performance"),
        _cat(w, "product_pages"), _cat(w, "image_quality"), _cat(w, "content_quality"),
        _cat(w, "conversion_optimization"), _cat(w, "call_to_actions"), _cat(w, "landing_pages"),
    ]) if w else 0

    seo = _avg([
        _cat(w, "seo"), _cat(w, "technical_seo"), _cat(w, "schema_markup"),
        _cat(w, "metadata"), _cat(w, "internal_linking"), _cat(w, "page_structure"),
        _cat(w, "indexability"), _cat(w, "core_web_vitals"), _cat(w, "broken_links"),
    ]) if w else 0

    # --- marketing / brand / social / content ------------------------------
    marketing = m.maturity_score if m else 0

    brand_positioning = ((m.channel_scores if m else None) or {}).get("brand_positioning", marketing)
    brand = _avg([brand_positioning, s.brand_consistency if s else 0,
                  _cat(w, "trust_signals")]) if (m or s or w) else 0

    social = s.overall_score if s else 0

    content_scores = [_cat(w, "content_quality"), _cat(w, "blog_activity")]
    if m and "content_marketing" in (m.channel_scores or {}):
        content_scores.append(m.channel_scores["content_marketing"])
    content = _avg(content_scores) if w else 0

    # --- customer experience / trust / technical ---------------------------
    customer_experience = _avg([
        _cat(w, "user_experience"), _cat(w, "checkout_experience"),
        _cat(w, "payment_options"), _cat(w, "search_functionality"),
        _cat(w, "filtering"), _cat(w, "faq"), _cat(w, "live_chat"),
        _cat(w, "contact_information"), _cat(w, "reviews"),
        _cat(w, "mobile_responsiveness"),
    ]) if w else 0

    trust = _avg([
        _cat(w, "trust_signals"), _cat(w, "return_policy"), _cat(w, "privacy_policy"),
        _cat(w, "security"), _cat(w, "ssl"), _cat(w, "reviews"),
        se.reputation_score if se else 0,
    ]) if (w or se) else 0

    technical = _avg([
        _cat(w, "performance"), _cat(w, "website_speed"), _cat(w, "core_web_vitals"),
        _cat(w, "technical_seo"), _cat(w, "indexability"), _cat(w, "security"),
        _cat(w, "ssl"),
    ]) if w else 0

    # --- product trend / growth / qualification ----------------------------
    product_trend = p.overall_score if p else 0

    growth_potential = _avg([
        product_trend,
        100 - website if w else 100,
        100 - marketing if m else 100,
        social,
        (100 - c.overall_score) if c else 50,
    ])

    # High-priority prospect: active business with weak website/SEO/marketing
    # but demonstrated demand and a social following.
    active = 100 if (w or s or se) else 40
    lead_qualification = _avg([
        (100 - website) if w else 90,
        (100 - seo) if w else 90,
        (100 - marketing) if m else 80,
        p.demand if p else 40,
        social,
        active,
    ])

    # --- health + opportunity ----------------------------------------------
    business_health = _avg([website, seo, marketing, brand, social, content,
                            customer_experience, trust, technical])
    ai_opportunity = _avg([lead_qualification, 100 - business_health,
                           (100 - c.overall_score) if c else 50, product_trend])

    return Scores(
        website=website, seo=seo, marketing=marketing, brand=brand, social=social,
        content=content, customer_experience=customer_experience, trust=trust,
        technical=technical, product_trend=product_trend,
        growth_potential=growth_potential, lead_qualification=lead_qualification,
        business_health=business_health, ai_opportunity=ai_opportunity,
    )


def qualify(intel: BusinessIntelligence, scores: Scores) -> LeadQualification:
    """Tier the lead deterministically from its scores."""
    q = scores.lead_qualification
    if q >= 72:
        priority = LeadPriority.HIGH
    elif q >= 45:
        priority = LeadPriority.MEDIUM
    else:
        priority = LeadPriority.LOW

    trigger = _tier_reason(intel, scores, priority)
    return LeadQualification(
        business_id=intel.lead.id,
        lead_qualification_score=q,
        priority=priority,
        reason=trigger,
    )


def _tier_reason(intel: BusinessIntelligence, scores: Scores, priority: LeadPriority) -> str:
    parts = []
    if scores.website < 40:
        parts.append("weak website")
    if scores.seo < 40:
        parts.append("poor SEO")
    if scores.marketing < 40:
        parts.append("low marketing maturity")
    if intel.product_trend and intel.product_trend.demand > 55:
        parts.append("healthy product demand")
    if intel.social and intel.social.overall_score > 40:
        parts.append("existing audience")
    base = ", ".join(parts) or "moderate profile"
    return f"{priority.value}-priority because of {base}."