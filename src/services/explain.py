"""Deterministic score explanations for the 14-dimension scoring model.

Every explanation mirrors the exact inputs the deterministic scoring engine
(src.scoring) uses. Pure arithmetic + wording — no LLM — so explanations
stay 1:1 with the numbers they describe.

Each dimension explanation is a *structured* record, not a prose blob:

    {
      "label": "SEO readiness",
      "what": "Organic search readiness.",
      "basis": "Average of 9 SEO categories: ...",
      "score": 42,
      "band": "ok",                    # weak | ok | strong
      "band_label": "Developing (40-69)",
      "method": "average",             # average | single | composed | derived
      "formula": "average of 9 SEO categories",
      "input_count": 9,
      "inputs": [ {key,label,value,band,role,delta,note}, ... ],
      "contributors": [...],           # alias of inputs (back-compat)
      "reasons": [ {kind,text}, ... ], # kind: method | drag | support | context
      "summary": "42/100 — ok band. Equal-weight average of 9 inputs. ..."
    }

Provides:
  - explain_scores(intel, scores)  — live, rich explanations from agent outputs
  - explain_from_record(record)    — lightweight fallback from persisted row data
  - DIMENSION_META                 — static definition / basis for each dimension
"""
from __future__ import annotations

from statistics import mean
from typing import Any

from src.schemas import BusinessIntelligence, Scores

# --------------------------------------------------------------------------- #
# Thresholds + bands
# --------------------------------------------------------------------------- #

STRONG = 70
OK = 40

BAND_LABELS: dict[str, str] = {
    "strong": "Strong (70-100)",
    "ok": "Developing (40-69)",
    "weak": "Weak (0-39)",
}

# --------------------------------------------------------------------------- #
# Dimension metadata (static, shared across frontend & /stats)
# --------------------------------------------------------------------------- #

LABELS: dict[str, str] = {
    "website": "Website quality",
    "seo": "SEO readiness",
    "marketing": "Marketing maturity",
    "brand": "Brand strength",
    "social": "Social presence",
    "content": "Content quality",
    "customer_experience": "Customer experience",
    "trust": "Trust signals",
    "technical": "Technical health",
    "product_trend": "Product trend",
    "growth_potential": "Growth potential",
    "lead_qualification": "Lead qualification",
    "business_health": "Business health",
    "ai_opportunity": "AI opportunity",
}

# Human-readable labels for raw sub-score keys.
INPUT_LABELS: dict[str, str] = {
    "homepage_quality": "Homepage quality",
    "navigation": "Navigation",
    "user_experience": "User experience",
    "mobile_responsiveness": "Mobile responsiveness",
    "website_speed": "Website speed",
    "performance": "Performance",
    "product_pages": "Product pages",
    "image_quality": "Image quality",
    "content_quality": "Content quality",
    "conversion_optimization": "Conversion optimization",
    "call_to_actions": "Calls to action",
    "landing_pages": "Landing pages",
    "seo": "SEO basics",
    "technical_seo": "Technical SEO",
    "schema_markup": "Schema markup",
    "metadata": "Metadata",
    "internal_linking": "Internal linking",
    "page_structure": "Page structure",
    "indexability": "Indexability",
    "core_web_vitals": "Core Web Vitals",
    "broken_links": "Broken links",
    "trust_signals": "Trust signals",
    "return_policy": "Return policy",
    "privacy_policy": "Privacy policy",
    "security": "Security",
    "ssl": "SSL / HTTPS",
    "reviews": "Reviews",
    "blog_activity": "Blog activity",
    "checkout_experience": "Checkout experience",
    "payment_options": "Payment options",
    "search_functionality": "Search functionality",
    "filtering": "Filtering",
    "faq": "FAQ",
    "live_chat": "Live chat",
    "contact_information": "Contact information",
    "brand_positioning": "Brand positioning",
    "brand_consistency": "Brand consistency",
    "content_marketing": "Content marketing",
    "reputation_score": "Reputation (sentiment)",
    "demand": "Product demand",
    "search_interest": "Search interest",
    "popularity": "Popularity",
    "competition": "Competition",
    "inventory_risk": "Inventory risk",
    "product_trend": "Product trend",
    "social": "Social audience",
    "active signal": "Active-seller signal",
    "100 − website": "Untapped website headroom",
    "100 − seo": "Untapped SEO headroom",
    "100 − marketing": "Untapped marketing headroom",
    "100 − business_health": "Untapped health headroom",
    "100 − competitor": "Competitive headroom",
}

DIMENSION_META: dict[str, dict[str, str]] = {
    "website": {
        "label": "Website quality",
        "what": "Quality of the online storefront itself.",
        "basis": (
            "Average of 12 website-audit categories: homepage_quality, "
            "navigation, user_experience, mobile_responsiveness, website_speed, "
            "performance, product_pages, image_quality, content_quality, "
            "conversion_optimization, call_to_actions, landing_pages."
        ),
    },
    "seo": {
        "label": "SEO readiness",
        "what": "Organic search readiness.",
        "basis": (
            "Average of 9 SEO categories: seo, technical_seo, schema_markup, "
            "metadata, internal_linking, page_structure, indexability, "
            "core_web_vitals, broken_links."
        ),
    },
    "marketing": {
        "label": "Marketing maturity",
        "what": "Marketing maturity — rollout, channels, funnel, retention.",
        "basis": (
            "Direct Agent 3 maturity_score (0-100) based on active channels, "
            "lifecycle stage, funnel, retention, and automation."
        ),
    },
    "brand": {
        "label": "Brand strength",
        "what": "Brand consistency and positioning strength.",
        "basis": (
            "Average of Agent 3 brand_positioning, Agent 4 brand_consistency, "
            "and the website's trust_signals category."
        ),
    },
    "social": {
        "label": "Social presence",
        "what": "Social media presence across platforms.",
        "basis": (
            "Agent 4 overall_score across all platforms, scored from posting "
            "frequency, follower growth, engagement rate, content quality, "
            "customer interaction, and response time."
        ),
    },
    "content": {
        "label": "Content quality",
        "what": "Content quality and blog / creative strength.",
        "basis": (
            "Average of the website's content_quality, blog_activity, and "
            "Agent 3 content_marketing channel score."
        ),
    },
    "customer_experience": {
        "label": "Customer experience",
        "what": "Usability, checkout and support experience.",
        "basis": (
            "Average of 10 categories: user_experience, checkout_experience, "
            "payment_options, search_functionality, filtering, faq, live_chat, "
            "contact_information, reviews, mobile_responsiveness."
        ),
    },
    "trust": {
        "label": "Trust signals",
        "what": "Trust signals, policies, security and reputation.",
        "basis": (
            "Average of trust_signals, return_policy, privacy_policy, security, "
            "ssl, reviews, plus Agent 6 reputation_score."
        ),
    },
    "technical": {
        "label": "Technical health",
        "what": "Performance, core web vitals, indexability, security.",
        "basis": (
            "Average of performance, website_speed, core_web_vitals, "
            "technical_seo, indexability, security, ssl."
        ),
    },
    "product_trend": {
        "label": "Product trend",
        "what": "Product-line market opportunity.",
        "basis": (
            "Agent 5 overall_score built from demand, search_interest, "
            "popularity, competition, seasonality, price positioning, "
            "and lifecycle stage."
        ),
    },
    "growth_potential": {
        "label": "Growth potential",
        "what": "Headroom / upside for the business.",
        "basis": (
            "Combination: product_trend + (100 − website) + "
            "(100 − marketing) + social + (100 − competitor). "
            "Lower current website/marketing scores increase growth headroom."
        ),
    },
    "lead_qualification": {
        "label": "Lead qualification",
        "what": "How good a sales prospect this is.",
        "basis": (
            "High when the business is weak at website/SEO/marketing yet "
            "shows demand and an audience: (100 − website) + (100 − seo) + "
            "(100 − marketing) + product demand + social + active signal."
        ),
    },
    "business_health": {
        "label": "Business health",
        "what": "Overall digital maturity.",
        "basis": (
            "Average of the 9 capability scores: website, seo, marketing, "
            "brand, social, content, customer_experience, trust, technical."
        ),
    },
    "ai_opportunity": {
        "label": "AI opportunity",
        "what": "Overall AI-driven service opportunity.",
        "basis": (
            "Average of lead_qualification + (100 − business_health) + "
            "(100 − competitor) + product_trend."
        ),
    },
}

CAPABILITY_DIMS: list[str] = [
    "website", "seo", "marketing", "brand", "social", "content",
    "customer_experience", "trust", "technical",
]

SCORE_DIMENSIONS: list[str] = list(DIMENSION_META.keys())

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _label(key: str) -> str:
    return INPUT_LABELS.get(key, key.replace("_", " ").strip().capitalize())


def _band(v: int) -> str:
    if v >= STRONG:
        return "strong"
    if v >= OK:
        return "ok"
    return "weak"


def _role(v: int) -> str:
    if v < OK:
        return "drag"
    if v >= STRONG:
        return "support"
    return "neutral"


def _v(analysis, key: str) -> int | None:
    """Read a 0-100 category from a WebsiteAnalysis, returning None when absent."""
    if analysis is None or getattr(analysis, "categories", None) is None:
        return None
    val = getattr(analysis.categories, key, None)
    return None if val is None else int(val or 0)


def _cat_inputs(analysis, keys: list[str]) -> list[tuple[str, str, int | None]]:
    return [(k, _label(k), _v(analysis, k)) for k in keys]


def _explain(
    dim: str,
    score: int,
    method: str,
    formula: str,
    inputs: list[tuple[str, str, int | None]] | None = None,
    context: list[str] | None = None,
) -> dict:
    """Build one structured explanation from the final score + raw inputs.

    ``method`` is one of: average (equal-weight sub-scores), single (a direct
    agent roll-up), composed (built from other final scores), or derived
    (reconstructed from a persisted row without agent detail).
    """
    meta = DIMENSION_META.get(dim, {})
    band = _band(score)
    present = [(k, lbl, int(v)) for k, lbl, v in (inputs or []) if v is not None]

    contributors = [
        {
            "key": k,
            "label": lbl,
            "value": v,
            "band": _band(v),
            "role": _role(v),
            "delta": v - score,
            "note": "weak" if v < OK else "strong" if v >= STRONG else "",
        }
        for k, lbl, v in present
    ]
    drags = sorted([c for c in contributors if c["role"] == "drag"], key=lambda c: c["value"])
    supports = sorted([c for c in contributors if c["role"] == "support"], key=lambda c: -c["value"])

    # -- explicit, grouped reasons --------------------------------------
    reasons: list[dict] = []
    method_text = {
        "average": f"Equal-weight average of {len(present)} inputs.",
        "single": "Direct AI-agent roll-up (not an average of sub-scores).",
        "composed": f"Built by averaging {len(present)} component scores.",
        "derived": "Reconstructed from the saved scan record.",
    }.get(method, "Deterministic computation.")
    reasons.append({"kind": "method", "text": method_text})

    for c in drags:
        reasons.append({
            "kind": "drag",
            "text": (
                f"{c['label']} scored {c['value']}/100 — under the 40 threshold, "
                f"dragging this score down by {abs(c['delta'])} pts vs the average."
            ),
        })
    for c in supports:
        reasons.append({
            "kind": "support",
            "text": (
                f"{c['label']} scored {c['value']}/100 — a strong input lifting "
                f"this score by {c['delta']} pts vs the average."
            ),
        })
    if present and not drags and not supports:
        reasons.append({
            "kind": "context",
            "text": "Every input sits in the 40-69 developing band — no single dominant weak or strong factor.",
        })
    for text in context or []:
        reasons.append({"kind": "context", "text": text})

    # -- clean fallback summary -----------------------------------------
    summary = f"{score}/100 — {band} band. {method_text}"
    if drags:
        summary += " Dragged down by " + ", ".join(f"{c['label']} ({c['value']})" for c in drags[:3]) + "."
    if supports:
        summary += " Lifted by " + ", ".join(f"{c['label']} ({c['value']})" for c in supports[:3]) + "."

    return {
        "label": meta.get("label", dim),
        "what": meta.get("what", ""),
        "basis": meta.get("basis", ""),
        "score": score,
        "verdict": band,
        "band": band,
        "band_label": BAND_LABELS[band],
        "method": method,
        "formula": formula,
        "input_count": len(present),
        "inputs": contributors,
        "contributors": contributors,
        "reasons": reasons,
        "summary": summary,
    }


# --------------------------------------------------------------------------- #
# Public — live explanations from full BusinessIntelligence
# --------------------------------------------------------------------------- #


def explain_scores(intel: BusinessIntelligence, scores: Scores) -> dict[str, dict]:
    """Return a 14-entry dict mapping each dimension to its explanation.

    The score inside each dict equals ``getattr(scores, dim)`` — explanations
    never disagree with the numbers the user sees.
    """
    w = intel.website
    m = intel.marketing
    s = intel.social
    p = intel.product_trend
    se = intel.sentiment
    c = intel.competitor

    out: dict[str, dict] = {}

    out["website"] = _explain(
        "website", scores.website, "average", "average of 12 website-audit categories",
        _cat_inputs(w, [
            "homepage_quality", "navigation", "user_experience", "mobile_responsiveness",
            "website_speed", "performance", "product_pages", "image_quality",
            "content_quality", "conversion_optimization", "call_to_actions", "landing_pages",
        ]),
    )

    out["seo"] = _explain(
        "seo", scores.seo, "average", "average of 9 SEO categories",
        _cat_inputs(w, [
            "seo", "technical_seo", "schema_markup", "metadata", "internal_linking",
            "page_structure", "indexability", "core_web_vitals", "broken_links",
        ]),
    )

    out["marketing"] = _explain(
        "marketing", scores.marketing, "single",
        "Agent 3 maturity_score (single roll-up of channels, lifecycle, funnel, retention)",
    )

    out["brand"] = _explain(
        "brand", scores.brand, "average",
        "average of Agent 3 brand_positioning, Agent 4 brand_consistency, and website trust_signals",
        [
            ("brand_positioning", _label("brand_positioning"),
             (m.channel_scores or {}).get("brand_positioning") if m else None),
            ("brand_consistency", _label("brand_consistency"), s.brand_consistency if s else None),
            ("trust_signals", _label("trust_signals"), _v(w, "trust_signals")),
        ],
    )

    out["social"] = _explain(
        "social", scores.social, "single",
        "Agent 4 overall_score across all social platforms",
    )

    out["content"] = _explain(
        "content", scores.content, "average",
        "average of content_quality, blog_activity, content_marketing",
        [
            ("content_quality", _label("content_quality"), _v(w, "content_quality")),
            ("blog_activity", _label("blog_activity"), _v(w, "blog_activity")),
            ("content_marketing", _label("content_marketing"),
             (m.channel_scores or {}).get("content_marketing") if m else None),
        ],
    )

    out["customer_experience"] = _explain(
        "customer_experience", scores.customer_experience, "average",
        "average of 10 CX categories",
        _cat_inputs(w, [
            "user_experience", "checkout_experience", "payment_options",
            "search_functionality", "filtering", "faq", "live_chat",
            "contact_information", "reviews", "mobile_responsiveness",
        ]),
    )

    out["trust"] = _explain(
        "trust", scores.trust, "average",
        "average of trust_signals, return_policy, privacy_policy, security, ssl, reviews, reputation_score",
        _cat_inputs(w, [
            "trust_signals", "return_policy", "privacy_policy",
            "security", "ssl", "reviews",
        ]) + [
            ("reputation_score", _label("reputation_score"),
             se.reputation_score if se else None),
        ],
    )

    out["technical"] = _explain(
        "technical", scores.technical, "average",
        "average of performance, website_speed, core_web_vitals, technical_seo, indexability, security, ssl",
        _cat_inputs(w, [
            "performance", "website_speed", "core_web_vitals",
            "technical_seo", "indexability", "security", "ssl",
        ]),
    )

    product_inputs: list[tuple[str, str, int | None]] = []
    context: list[str] = []
    if p:
        product_inputs = [
            ("demand", _label("demand"), p.demand),
            ("search_interest", _label("search_interest"), p.search_interest),
            ("popularity", _label("popularity"), p.popularity),
            ("competition", _label("competition"), p.competition),
        ]
        if p.inventory_risk:
            product_inputs.append(("inventory_risk", _label("inventory_risk"), p.inventory_risk))
        bits = []
        if p.trend_direction:
            bits.append(f"trend {p.trend_direction}")
        if p.seasonality:
            bits.append(f"seasonality {p.seasonality}")
        if p.price_positioning:
            bits.append(f"pricing {p.price_positioning}")
        if p.lifecycle_stage:
            bits.append(f"lifecycle {p.lifecycle_stage}")
        if bits:
            context.append("Market context: " + ", ".join(bits) + ".")
    out["product_trend"] = _explain(
        "product_trend", scores.product_trend, "average",
        "Agent 5 overall_score (demand, search, popularity, competition)",
        product_inputs, context,
    )

    out["growth_potential"] = _explain(
        "growth_potential", scores.growth_potential, "composed",
        "product_trend + (100 − website) + (100 − marketing) + social + (100 − competitor)",
        [
            ("product_trend", _label("product_trend"), scores.product_trend),
            ("100 − website", _label("100 − website"), 100 - scores.website if w else 100),
            ("100 − marketing", _label("100 − marketing"), 100 - scores.marketing if m else 100),
            ("social", _label("social"), scores.social),
            ("100 − competitor", _label("100 − competitor"), 100 - c.overall_score if c else 50),
        ],
        ["Higher when the business has untapped website/marketing headroom."],
    )

    active = 100 if (w or s or se) else 40
    out["lead_qualification"] = _explain(
        "lead_qualification", scores.lead_qualification, "composed",
        "(100 − website) + (100 − seo) + (100 − marketing) + demand + social + active",
        [
            ("100 − website", _label("100 − website"), 100 - scores.website if w else 90),
            ("100 − seo", _label("100 − seo"), 100 - scores.seo if w else 90),
            ("100 − marketing", _label("100 − marketing"), 100 - scores.marketing if m else 80),
            ("demand", _label("demand"), p.demand if p else 40),
            ("social", _label("social"), scores.social),
            ("active signal", _label("active signal"), active),
        ],
        ["High when the business is weak online but actively selling with an audience."],
    )

    out["business_health"] = _explain(
        "business_health", scores.business_health, "composed",
        "average of 9 capability scores: website, seo, marketing, brand, social, content, CX, trust, technical",
        [(d, _label(d), getattr(scores, d)) for d in CAPABILITY_DIMS],
    )

    out["ai_opportunity"] = _explain(
        "ai_opportunity", scores.ai_opportunity, "composed",
        "lead_qualification + (100 − business_health) + (100 − competitor) + product_trend",
        [
            ("lead_qualification", _label("lead_qualification"), scores.lead_qualification),
            ("100 − business_health", _label("100 − business_health"), 100 - scores.business_health),
            ("100 − competitor", _label("100 − competitor"), 100 - c.overall_score if c else 50),
            ("product_trend", _label("product_trend"), scores.product_trend),
        ],
        ["Higher when the business has headroom (low health) and proven product demand."],
    )

    return out


# --------------------------------------------------------------------------- #
# Fallback — from persisted row (no full agent outputs)
# --------------------------------------------------------------------------- #


def explain_from_record(record: dict[str, Any]) -> dict[str, dict]:
    """Structured per-dimension explanations derived from a stored row.

    Used when a row has no persisted explanations (legacy data). Capability
    scores have no stored sub-scores, so they carry band + cross-dimension
    context; the composite scores are rebuilt from the other stored scores.
    """
    scores = {k: int(record.get(k) or 0) for k in SCORE_DIMENSIONS}
    cap_vals = [(d, scores[d]) for d in CAPABILITY_DIMS if scores.get(d)]
    avg_cap = int(round(mean([v for _, v in cap_vals]))) if cap_vals else 0
    weakest = {d for d, _ in sorted(cap_vals, key=lambda x: x[1])[:3]}
    strongest = {d for d, _ in sorted(cap_vals, key=lambda x: -x[1])[:3]}
    qual_reason = str(record.get("notes", "") or "")

    out: dict[str, dict] = {}
    for dim in SCORE_DIMENSIONS:
        sc = scores[dim]
        ctx: list[str] = []
        method = "derived"
        inputs: list[tuple[str, str, int | None]] = []

        if dim in CAPABILITY_DIMS:
            method = "derived"
            if sc < OK:
                ctx.append("Sits in the weak band (<40) — a clear improvement area.")
            elif sc >= STRONG:
                ctx.append("Sits in the strong band (>=70) — a relative strength.")
            else:
                ctx.append("Sits in the developing band (40-69).")
            if dim in weakest and avg_cap and sc < avg_cap:
                ctx.append(f"Among the weakest capabilities vs this business's own average of {avg_cap}.")
            if dim in strongest and avg_cap and sc >= avg_cap:
                ctx.append(f"Among the strongest capabilities vs this business's own average of {avg_cap}.")
            ctx.append("Sub-score detail was not stored for this scan — rerun for a full component breakdown.")
        elif dim == "growth_potential":
            method = "composed"
            inputs = [
                ("product_trend", _label("product_trend"), scores["product_trend"]),
                ("100 − website", _label("100 − website"), 100 - scores["website"]),
                ("100 − marketing", _label("100 − marketing"), 100 - scores["marketing"]),
                ("social", _label("social"), scores["social"]),
            ]
            ctx.append("Competitor data absent for this stored scan; that term is excluded here.")
        elif dim == "lead_qualification":
            method = "composed"
            inputs = [
                ("100 − website", _label("100 − website"), 100 - scores["website"]),
                ("100 − seo", _label("100 − seo"), 100 - scores["seo"]),
                ("100 − marketing", _label("100 − marketing"), 100 - scores["marketing"]),
                ("social", _label("social"), scores["social"]),
            ]
            if qual_reason:
                ctx.append(f"Qualification note: {qual_reason}")
        elif dim == "business_health":
            method = "composed"
            inputs = [(d, _label(d), scores[d]) for d in CAPABILITY_DIMS]
        elif dim == "ai_opportunity":
            method = "composed"
            inputs = [
                ("lead_qualification", _label("lead_qualification"), scores["lead_qualification"]),
                ("100 − business_health", _label("100 − business_health"), 100 - scores["business_health"]),
                ("product_trend", _label("product_trend"), scores["product_trend"]),
            ]
            ctx.append("Competitor data absent for this stored scan; that term is excluded here.")

        formula = DIMENSION_META.get(dim, {}).get("basis", "")
        out[dim] = _explain(dim, sc, method, formula, inputs, ctx)

    return out


# --------------------------------------------------------------------------- #
# Aggregate summary across all businesses (for /stats)
# --------------------------------------------------------------------------- #


def dimension_summary(dim: str, avg: int, count: int, rows: list[dict]) -> dict:
    """Build a summary card for one dimension across all businesses (for /stats)."""
    meta = DIMENSION_META.get(dim, {})
    vals = [int(r.get(dim) or 0) for r in rows if r.get(dim)]
    weak_count = sum(1 for v in vals if v < OK)
    strong_count = sum(1 for v in vals if v >= STRONG)
    note = f"{weak_count} of {count} business{'es' if count != 1 else ''} below 40" if count and weak_count else ""
    return {
        "label": meta.get("label", dim),
        "what": meta.get("what", ""),
        "basis": meta.get("basis", ""),
        "avg": avg,
        "count": count,
        "weak_count": weak_count,
        "strong_count": strong_count,
        "note": note,
    }
