-- ═══════════════════════════════════════════════════════════
--  SADAK AI v3 — Supabase Cloud Schema
--  Run this in: Supabase Dashboard → SQL Editor → Run
-- ═══════════════════════════════════════════════════════════

-- ── USERS TABLE ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id               BIGINT PRIMARY KEY,
    full_name        TEXT NOT NULL,
    email            TEXT UNIQUE NOT NULL,
    state            TEXT,
    district         TEXT,
    role             TEXT DEFAULT 'citizen',
    is_active        BOOLEAN DEFAULT TRUE,
    complaints_count INTEGER DEFAULT 0,
    avatar_color     TEXT DEFAULT '#0EA5E9',
    created_at       TEXT,
    last_login       TEXT
);

-- ── COMPLAINTS TABLE ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id     TEXT PRIMARY KEY,
    status           TEXT DEFAULT 'FILED',
    severity         TEXT DEFAULT 'MEDIUM',
    state            TEXT,
    district         TEXT,
    description      TEXT,
    authority_name   TEXT,
    authority_type   TEXT,
    helpline         TEXT,
    latitude         REAL,
    longitude        REAL,
    ai_detected      BOOLEAN DEFAULT FALSE,
    ai_confidence    REAL,
    ai_pothole_count INTEGER DEFAULT 0,
    response_deadline TEXT,
    resolved_at      TEXT,
    resolution_note  TEXT,
    user_id          BIGINT REFERENCES users(id) ON DELETE SET NULL,
    user_name        TEXT,
    filed_at         TEXT,
    updated_at       TEXT
);

-- ── INDEXES for fast queries ──────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_complaints_status   ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_severity ON complaints(severity);
CREATE INDEX IF NOT EXISTS idx_complaints_state    ON complaints(state);
CREATE INDEX IF NOT EXISTS idx_complaints_user     ON complaints(user_id);
CREATE INDEX IF NOT EXISTS idx_complaints_filed    ON complaints(filed_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_role          ON users(role);

-- ── STATS VIEW (auto-refreshes) ───────────────────────────────
CREATE OR REPLACE VIEW sadak_stats AS
SELECT
    COUNT(*)                                              AS total_complaints,
    COUNT(*) FILTER (WHERE status = 'FILED')              AS pending,
    COUNT(*) FILTER (WHERE status = 'RESOLVED')           AS resolved,
    COUNT(*) FILTER (WHERE status = 'IN_PROGRESS')        AS in_progress,
    COUNT(*) FILTER (WHERE status = 'ESCALATED')          AS escalated,
    COUNT(*) FILTER (WHERE severity = 'CRITICAL')         AS critical,
    COUNT(*) FILTER (WHERE ai_detected = TRUE)            AS ai_detected,
    ROUND(AVG(ai_confidence) FILTER
          (WHERE ai_confidence IS NOT NULL) * 100, 1)     AS avg_ai_confidence_pct,
    COUNT(DISTINCT state)                                 AS states_reported,
    COUNT(DISTINCT district)                              AS districts_reported,
    MIN(filed_at)                                         AS first_complaint,
    MAX(filed_at)                                         AS latest_complaint
FROM complaints;

-- ── PER-STATE STATS VIEW ──────────────────────────────────────
CREATE OR REPLACE VIEW state_stats AS
SELECT
    state,
    COUNT(*)                                          AS total,
    COUNT(*) FILTER (WHERE status = 'RESOLVED')       AS resolved,
    COUNT(*) FILTER (WHERE severity = 'CRITICAL')     AS critical,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'RESOLVED')
        * 100.0 / NULLIF(COUNT(*), 0), 1
    )                                                 AS resolution_pct
FROM complaints
WHERE state IS NOT NULL
GROUP BY state
ORDER BY total DESC;

-- ── ENABLE ROW-LEVEL SECURITY ────────────────────────────────
ALTER TABLE users      ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaints ENABLE ROW LEVEL SECURITY;

-- Allow service role (backend) full access
CREATE POLICY "service_all_users"
    ON users FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "service_all_complaints"
    ON complaints FOR ALL
    USING (auth.role() = 'service_role');

-- ═══════════════════════════════════════════════════════════
--  DONE! Your SADAK AI cloud database is ready.
--  Now set environment variables and restart app.py
-- ═══════════════════════════════════════════════════════════