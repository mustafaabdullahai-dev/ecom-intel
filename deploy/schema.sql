-- ecom-intel: PostgreSQL + pgvector schema
-- Apply with:  psql "$DATABASE_URL" -f deploy/schema.sql
--
-- Requires the pgvector extension (https://github.com/pgvector/pgvector).

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per discovered business (stable lead table).
CREATE TABLE IF NOT EXISTS businesses (
    id            TEXT PRIMARY KEY,            -- slug id, stable across scans
    name          TEXT NOT NULL,
    region        TEXT NOT NULL DEFAULT '',
    industry      TEXT NOT NULL DEFAULT '',
    platform      TEXT NOT NULL DEFAULT 'unknown',
    website       TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    phone         TEXT NOT NULL DEFAULT '',
    social_links  TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only per-scan record (mirrors the JSON/Google Sheets knowledge base).
CREATE TABLE IF NOT EXISTS records (
    id                    BIGSERIAL PRIMARY KEY,
    business_id           TEXT NOT NULL REFERENCES businesses(id),
    scanned_at            TIMESTAMPTZ NOT NULL,
    lead_priority         TEXT NOT NULL DEFAULT 'low',
    ai_summary            TEXT NOT NULL DEFAULT '',
    daily                 TEXT NOT NULL DEFAULT '',
    weekly                TEXT NOT NULL DEFAULT '',
    monthly               TEXT NOT NULL DEFAULT '',
    quarterly             TEXT NOT NULL DEFAULT '',
    yearly                TEXT NOT NULL DEFAULT '',
    change_since_previous TEXT NOT NULL DEFAULT '',
    notes                 TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_records_business_scanned
    ON records (business_id, scanned_at DESC);

-- A snapshot of the 14 scores per scan (kept denormalized for dashboards).
CREATE TABLE IF NOT EXISTS score_snapshots (
    record_id           BIGINT PRIMARY KEY REFERENCES records(id),
    website             INT NOT NULL DEFAULT 0,
    seo                 INT NOT NULL DEFAULT 0,
    marketing           INT NOT NULL DEFAULT 0,
    brand               INT NOT NULL DEFAULT 0,
    social              INT NOT NULL DEFAULT 0,
    content             INT NOT NULL DEFAULT 0,
    customer_experience INT NOT NULL DEFAULT 0,
    trust               INT NOT NULL DEFAULT 0,
    technical           INT NOT NULL DEFAULT 0,
    product_trend       INT NOT NULL DEFAULT 0,
    growth_potential    INT NOT NULL DEFAULT 0,
    lead_qualification  INT NOT NULL DEFAULT 0,
    business_health     INT NOT NULL DEFAULT 0,
    ai_opportunity      INT NOT NULL DEFAULT 0
);

-- Embeddings: semantic memory for Agent 6 (reviews) and Agent 7 (competitor).
CREATE TABLE IF NOT EXISTS embeddings (
    id           BIGSERIAL PRIMARY KEY,
    business_id  TEXT REFERENCES businesses(id),
    source       TEXT NOT NULL DEFAULT '',    -- 'site_copy' | 'reviews' | 'competitors'
    content      TEXT NOT NULL,
    embedding    vector(768),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
    USING hnsw (embedding vector_cosine_ops);