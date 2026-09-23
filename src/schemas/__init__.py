"""Shared data models.

Every value passed between agents and stored in the knowledge base is typed
with pydantic so the system's inputs and outputs are explicit and easy to
follow. Models map 1:1 to the eight agents, the 14-score system, and the
Google Sheets export columns.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Platform(str, enum.Enum):
    UNKNOWN = "unknown"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    MAGENTO = "magento"
    BIGCOMMERCE = "bigcommerce"
    ETSY = "etsy"
    AMAZON = "amazon"
    WIX = "wix"
    SQUARESPACE = "squarespace"
    FACEBOOK_SHOP = "facebook_shop"
    INSTAGRAM_SHOP = "instagram_shop"
    CUSTOM = "custom"
    NO_WEBSITE = "no_website"


class LeadPriority(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Agent 1 — Business Discovery
# ---------------------------------------------------------------------------


class BusinessLead(BaseModel):
    """A discovered ecommerce business with all extracted contact data."""

    id: str = Field(description="Stable identifier (slug of the name).")
    name: str
    country: str
    region: str = Field(description="Geographic region of the business.")
    city: str = ""
    industry: str = Field(default="", description="Product/service vertical.")
    products: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    email: str = ""
    phone: str = ""
    platform: Platform = Platform.UNKNOWN
    social_handles: dict[str, str] = Field(
        default_factory=dict,
        description="Platform name -> handle, e.g. {'instagram': '@shopx'}.",
    )
    description: str = ""
    source: str = Field(default="web_search", description="Where the lead was found.")
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class DiscoveryResult(BaseModel):
    """Output of Agent 1: leads plus a summary."""

    leads: list[BusinessLead] = Field(default_factory=list)
    summary: str = Field(
        default="",
        description="Note on the discovery run (sources searched, gaps).",
    )


# ---------------------------------------------------------------------------
# Agent 2 — Website Intelligence
# ---------------------------------------------------------------------------


class WebsiteCategoryScores(BaseModel):
    """0-100 score for every website dimension the spec lists."""

    homepage_quality: int = 0
    navigation: int = 0
    user_experience: int = 0
    mobile_responsiveness: int = 0
    website_speed: int = 0
    performance: int = 0
    seo: int = 0
    accessibility: int = 0
    broken_links: int = 100
    security: int = 0
    ssl: int = 0
    checkout_experience: int = 0
    payment_options: int = 0
    search_functionality: int = 0
    filtering: int = 0
    product_pages: int = 0
    image_quality: int = 0
    content_quality: int = 0
    trust_signals: int = 0
    return_policy: int = 0
    privacy_policy: int = 0
    faq: int = 0
    live_chat: int = 0
    contact_information: int = 0
    reviews: int = 0
    conversion_optimization: int = 0
    call_to_actions: int = 0
    landing_pages: int = 0
    blog_activity: int = 0
    technical_seo: int = 0
    schema_markup: int = 0
    metadata: int = 0
    internal_linking: int = 0
    page_structure: int = 0
    indexability: int = 0
    core_web_vitals: int = 0


class WebsiteAnalysis(BaseModel):
    """Full website audit output of Agent 2."""

    business_id: str
    categories: WebsiteCategoryScores
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    broken_links_found: int = 0
    has_ssl: bool = False
    page_load_ms: Optional[int] = None
    contact_email: str = ""
    contact_phone: str = ""
    summary: str = Field(default="", description="One-paragraph website verdict.")


# ---------------------------------------------------------------------------
# Agent 3 — Marketing Intelligence
# ---------------------------------------------------------------------------


class MarketingAnalysis(BaseModel):
    """Marketing maturity evaluation output of Agent 3."""

    business_id: str
    maturity_score: int = Field(ge=0, le=100)
    channel_scores: dict[str, int] = Field(
        default_factory=dict,
        description="Channel -> 0-100 maturity, e.g. {'google_ads': 40}.",
    )
    active_channels: list[str] = Field(
        default_factory=list,
        description="Channels the business demonstrably uses.",
    )
    lifecycle_stage: str = Field(default="", description="e.g. seed | growth | mature.")
    sales_funnel: str = Field(default="", description="Strength of the funnel, one line.")
    retention: str = Field(default="", description="Retention/repeat-purchase read, one line.")
    automation: str = Field(default="", description="Marketing automation read, one line.")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent 4 — Social Media Intelligence
# ---------------------------------------------------------------------------


class PlatformSocial(BaseModel):
    """Compact per-platform snapshot for one social network."""

    posting_frequency: int = Field(default=0, ge=0, le=100)
    follower_growth: int = Field(default=0, ge=0, le=100)
    engagement_rate: int = Field(default=0, ge=0, le=100)
    content_quality: int = Field(default=0, ge=0, le=100)
    customer_interaction: int = Field(default=0, ge=0, le=100)
    response_time: int = Field(default=0, ge=0, le=100, description="Higher = faster.")
    notes: str = ""


class SocialMediaAnalysis(BaseModel):
    """Social intelligence output of Agent 4."""

    business_id: str
    platforms: dict[str, PlatformSocial] = Field(default_factory=dict)
    brand_consistency: int = Field(default=0, ge=0, le=100)
    community_management: int = Field(default=0, ge=0, le=100)
    social_commerce_ready: bool = False
    overall_score: int = Field(default=0, ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent 5 — Product Trend Intelligence
# ---------------------------------------------------------------------------


class ProductTrendAnalysis(BaseModel):
    """Product/market trend evaluation output of Agent 5."""

    business_id: str
    demand: int = Field(default=0, ge=0, le=100)
    trend_direction: str = Field(default="", description="rising | stable | falling")
    seasonality: str = Field(default="", description="Low | Moderate | High")
    competition: int = Field(default=0, ge=0, le=100, description="Higher = more competitors.")
    price_positioning: str = Field(default="", description="premium | mid | budget")
    search_interest: int = Field(default=0, ge=0, le=100)
    popularity: int = Field(default=0, ge=0, le=100)
    lifecycle_stage: str = Field(default="", description="intro | growth | maturity | decline")
    new_product_ideas: list[str] = Field(default_factory=list)
    upsell_opportunities: list[str] = Field(default_factory=list)
    cross_sell_opportunities: list[str] = Field(default_factory=list)
    replacement_opportunities: list[str] = Field(default_factory=list)
    inventory_risk: int = Field(default=0, ge=0, le=100)
    overall_score: int = Field(default=0, ge=0, le=100)
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Agent 6 — Customer Sentiment
# ---------------------------------------------------------------------------


class ReviewSource(BaseModel):
    """Summary of reviews collected from one public source."""

    source: str = Field(default="", description="google | facebook | trustpilot | site_reviews...")
    review_count: int = 0
    average_rating: float = 0.0
    positive_themes: list[str] = Field(default_factory=list)
    negative_themes: list[str] = Field(default_factory=list)


class SentimentAnalysis(BaseModel):
    """Reputation & sentiment output of Agent 6."""

    business_id: str
    sources: list[ReviewSource] = Field(default_factory=list)
    complaints: list[str] = Field(default_factory=list)
    common_issues: list[str] = Field(default_factory=list)
    satisfaction_score: int = Field(default=0, ge=0, le=100)
    response_quality: int = Field(default=0, ge=0, le=100)
    reputation_score: int = Field(default=0, ge=0, le=100)
    evidence_note: str = Field(
        default="",
        description="Where review evidence came from (e.g. search snippets only).",
    )


# ---------------------------------------------------------------------------
# Agent 7 — Competitor Intelligence
# ---------------------------------------------------------------------------


class Competitor(BaseModel):
    """A single named competitor with a quick profile."""

    name: str
    url: str = ""
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class CompetitorAnalysis(BaseModel):
    """Competitive benchmarking output of Agent 7."""

    business_id: str
    competitors: list[Competitor] = Field(default_factory=list)
    comparisons: dict[str, str] = Field(
        default_factory=dict,
        description="Dimension -> 'focal vs competitor' note, e.g. pricing comparisons.",
    )
    competitive_gaps: list[str] = Field(
        default_factory=list,
        description="Dimensions where the focal business clearly trails.",
    )
    position: str = Field(default="unknown", pattern="^(strong|moderate|weak|unknown)$")
    tech_stack: list[str] = Field(default_factory=list)
    overall_score: int = Field(default=0, ge=0, le=100, description="Higher = weaker (more gap).")
    summary: str = ""


# ---------------------------------------------------------------------------
# Agent 8 — AI Recommendation Engine + Lead Qualification
# ---------------------------------------------------------------------------


class RecommendationPlan(BaseModel):
    """Time-horizon recommendations for ONE business."""

    business_id: str
    ai_summary: str = Field(default="", description="One-sentence AI consultant summary.")
    daily: list[str] = Field(default_factory=list)
    weekly: list[str] = Field(default_factory=list)
    monthly: list[str] = Field(default_factory=list)
    quarterly: list[str] = Field(default_factory=list)
    yearly: list[str] = Field(default_factory=list)


class LeadQualification(BaseModel):
    """Priority classification computed for ONE business."""

    business_id: str
    lead_qualification_score: int = Field(ge=0, le=100)
    priority: LeadPriority = LeadPriority.LOW
    reason: str = Field(default="", description="Why this tier (weakness x potential).")


class SecurityFinding(BaseModel):
    """One security issue found during a live website scan."""

    severity: str = Field(default="info", description="critical | high | medium | low | info")
    category: str = Field(default="general", description="https | ssl_tls | authentication | input_validation | file_permissions | headers | cookies | general")
    title: str
    detail: str = ""
    remediation: str = ""


class SecurityGap(BaseModel):
    """Something the website lacks, with the reason and an AI fix."""

    topic: str = Field(description="Area that is missing/weak, e.g. SSL certificate, contact page.")
    status: str = Field(default="lacking", description="present | weak | lacking")
    reason: str = Field(default="", description="Why it matters / why it's judged lacking.")
    recommendation: str = Field(default="", description="Concrete AI recommendation to fix it.")


class SecurityAnalysis(BaseModel):
    """Real website security audit (Agent 9)."""

    business_id: str
    url: str = ""
    overall_score: int = Field(default=0, ge=0, le=100, description="100 = most secure.")
    risk_level: str = Field(default="unknown", description="low | medium | high | critical | unknown")
    https_enforced: bool = False
    https: int = Field(default=0, ge=0, le=100, description="HTTPS enforcement score.")
    ssl_tls: int = Field(default=0, ge=0, le=100, description="SSL/TLS configuration score.")
    authentication: int = Field(default=0, ge=0, le=100, description="Auth & access-control score.")
    input_validation: int = Field(default=0, ge=0, le=100, description="Input validation score.")
    file_permissions: int = Field(default=0, ge=0, le=100, description="File-permission & config exposure score.")
    security_headers: int = Field(default=0, ge=0, le=100, description="Security-header hardening score.")
    protocol: str = Field(default="", description="Negotiated TLS protocol, e.g. TLSv1.3.")
    cipher: str = Field(default="", description="Negotiated TLS cipher.")
    cert_issuer: str = ""
    cert_expires_days: int = Field(default=0, description="Days until cert expiry; -1 if missing.")
    security_headers_found: dict[str, bool] = Field(default_factory=dict)
    cookies_secure: bool = False
    cookies_httponly: bool = False
    exposed_paths: list[str] = Field(default_factory=list, description="Probed paths that returned content (not 403/404).")
    findings: list[SecurityFinding] = Field(default_factory=list)
    gaps: list[SecurityGap] = Field(default_factory=list)
    checks_performed: list[str] = Field(default_factory=list)
    outreach_message: str = Field(default="", description="Friendly message to the website owner.")
    summary: str = ""


# ---------------------------------------------------------------------------
# 14-score model (deterministic)
# ---------------------------------------------------------------------------


class Scores(BaseModel):
    """Standardized 0-100 scores assembled deterministically from agent outputs."""

    website: int = 0
    seo: int = 0
    marketing: int = 0
    brand: int = 0
    social: int = 0
    content: int = 0
    customer_experience: int = 0
    trust: int = 0
    technical: int = 0
    product_trend: int = 0
    growth_potential: int = 0
    lead_qualification: int = 0
    business_health: int = 0
    ai_opportunity: int = 0


# ---------------------------------------------------------------------------
# Merged per-business intelligence (the analytics "record")
# ---------------------------------------------------------------------------


class BusinessIntelligence(BaseModel):
    """Everything the ecosystem knows about one business in one package."""

    lead: BusinessLead
    website: Optional[WebsiteAnalysis] = None
    marketing: Optional[MarketingAnalysis] = None
    social: Optional[SocialMediaAnalysis] = None
    product_trend: Optional[ProductTrendAnalysis] = None
    sentiment: Optional[SentimentAnalysis] = None
    competitor: Optional[CompetitorAnalysis] = None
    security: Optional[SecurityAnalysis] = None
    scores: Scores = Field(default_factory=Scores)
    qualification: Optional[LeadQualification] = None
    recommendation_plan: Optional[RecommendationPlan] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Monitoring / history
# ---------------------------------------------------------------------------


class ScoreDelta(BaseModel):
    """Change in one score between two scans of the same business."""

    score_name: str
    previous: int
    current: int
    delta: int


class ChangeSummary(BaseModel):
    """Change-since-previous-scan for one business."""

    business_id: str
    deltas: list[ScoreDelta] = Field(default_factory=list)
    headline: str = Field(default="", description="Human summary of what changed.")
    is_first_scan: bool = False


class HistoryRecord(BaseModel):
    """One row in the knowledge base (Google Sheets -> one spreadsheet row)."""

    business_id: str
    business_name: str
    region: str
    website: str
    industry: str
    contact_email: str
    phone: str
    social_links: str
    platform: str
    scores: Scores
    lead_priority: str
    ai_summary: str
    daily: str
    weekly: str
    monthly: str
    quarterly: str
    yearly: str
    last_analysis_date: str
    next_scheduled_analysis: str
    change_since_previous: str
    overall_business_health: int
    overall_ai_opportunity: int
    sales_status: str = "new"
    outreach_status: str = "not_contacted"
    notes: str = ""
    score_explanations: dict[str, dict] = Field(
        default_factory=dict,
        description="Per-dimension reasoning for the 14-score model, captured at analysis time.",
    )


# ---------------------------------------------------------------------------
# Pipeline output
# ---------------------------------------------------------------------------


class PipelineResult(BaseModel):
    """End-to-end output of a full run."""

    run_id: str
    discovery: DiscoveryResult
    intelligence: list[BusinessIntelligence] = Field(default_factory=list)
    records: list[HistoryRecord] = Field(default_factory=list)
    finished_at: datetime = Field(default_factory=datetime.utcnow)
    report_path: str = ""
    sheets_written: bool = False