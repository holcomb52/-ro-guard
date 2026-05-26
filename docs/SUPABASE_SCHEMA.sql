-- RO Shield — run once in Supabase SQL Editor
-- Dashboard → SQL → New query → paste → Run

-- Reviews (team-wide audit history + reporting)
CREATE TABLE IF NOT EXISTS reviews (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ro_number TEXT,
    vin TEXT,
    ro_invoiced TEXT,
    day_submitted TEXT,
    days_to_submit INTEGER DEFAULT 0,
    advisor TEXT,
    technician TEXT,
    warranty_admin TEXT,
    manager TEXT,
    entered_by TEXT,
    score INTEGER DEFAULT 0,
    status TEXT,
    total_claim_value NUMERIC DEFAULT 0,
    hard_stop_value NUMERIC DEFAULT 0,
    hard_stop_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    time_bypass BOOLEAN DEFAULT FALSE,
    time_bypass_user TEXT,
    first_pass_paid BOOLEAN DEFAULT FALSE,
    rejected BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    outcome_updated_at TIMESTAMPTZ,
    outcome_updated_by TEXT,
    jobs JSONB DEFAULT '[]'::jsonb,
    vin_recall_identified INTEGER DEFAULT 0,
    vin_recall_count INTEGER DEFAULT 0,
    vin_recall_campaigns TEXT,
    vin_recall_acknowledged INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_ro_number ON reviews (ro_number);
CREATE INDEX IF NOT EXISTS idx_reviews_advisor ON reviews (advisor);

-- If reviews table already exists from an older build, add missing columns:
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS ro_invoiced TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS day_submitted TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS days_to_submit INTEGER DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS total_claim_value NUMERIC DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS hard_stop_value NUMERIC DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS hard_stop_count INTEGER DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS warning_count INTEGER DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS time_bypass BOOLEAN DEFAULT FALSE;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS time_bypass_user TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS first_pass_paid BOOLEAN DEFAULT FALSE;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS rejected BOOLEAN DEFAULT FALSE;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS rejection_reason TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS outcome_updated_at TIMESTAMPTZ;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS outcome_updated_by TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS jobs JSONB DEFAULT '[]'::jsonb;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS status TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vin_recall_identified INTEGER DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vin_recall_count INTEGER DEFAULT 0;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vin_recall_campaigns TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vin_recall_acknowledged INTEGER DEFAULT 0;

-- Service bulletins / rules (moved off local SQLite)
CREATE TABLE IF NOT EXISTS bulletins (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title TEXT NOT NULL,
    keywords TEXT,
    notes TEXT,
    source_file TEXT,
    bulletin_number TEXT,
    content TEXT
);

ALTER TABLE bulletins ADD COLUMN IF NOT EXISTS source_file TEXT;
ALTER TABLE bulletins ADD COLUMN IF NOT EXISTS bulletin_number TEXT;
ALTER TABLE bulletins ADD COLUMN IF NOT EXISTS content TEXT;

ALTER TABLE bulletins ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "bulletins_read" ON bulletins;
DROP POLICY IF EXISTS "bulletins_write" ON bulletins;

CREATE POLICY "bulletins_read" ON bulletins
    FOR SELECT USING (true);

CREATE POLICY "bulletins_write" ON bulletins
    FOR ALL USING (true) WITH CHECK (true);

-- Optional: allow anon/authenticated app access (adjust for your security model)
-- ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow all for service role" ON reviews FOR ALL USING (true);

-- Dealer-wide settings (Smart Warranty level, etc.)
CREATE TABLE IF NOT EXISTS dealer_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    smart_warranty_level TEXT NOT NULL DEFAULT 'base',
    updated_by TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO dealer_settings (id, smart_warranty_level)
VALUES (1, 'base')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE dealer_settings ADD COLUMN IF NOT EXISTS audit_rules JSONB DEFAULT '{}'::jsonb;
ALTER TABLE dealer_settings ADD COLUMN IF NOT EXISTS rejection_reasons JSONB DEFAULT '{}'::jsonb;

-- If save fails with "row-level security policy", run this block:
ALTER TABLE dealer_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "dealer_settings_read" ON dealer_settings;
DROP POLICY IF EXISTS "dealer_settings_write" ON dealer_settings;

CREATE POLICY "dealer_settings_read" ON dealer_settings
    FOR SELECT USING (true);

CREATE POLICY "dealer_settings_write" ON dealer_settings
    FOR ALL USING (true) WITH CHECK (true);

-- Personnel (Review selectboxes + auth role linking)
CREATE TABLE IF NOT EXISTS personnel (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    employee_number TEXT,
    email TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE personnel ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE personnel ADD COLUMN IF NOT EXISTS employee_number TEXT;
ALTER TABLE personnel ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
ALTER TABLE personnel ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE personnel ADD COLUMN IF NOT EXISTS display_prefs JSONB DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS idx_personnel_email_unique
    ON personnel (lower(email))
    WHERE email IS NOT NULL AND email <> '';
