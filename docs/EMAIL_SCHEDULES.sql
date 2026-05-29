-- RO Shield — scheduled Reporting email schedules
-- Run once in Supabase → SQL Editor

CREATE TABLE IF NOT EXISTS email_schedules (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    frequency TEXT NOT NULL CHECK (frequency IN ('daily', 'monthly', 'yearly')),
    report_type TEXT NOT NULL DEFAULT 'reporting' CHECK (report_type IN ('reporting')),
    recipients TEXT NOT NULL DEFAULT '',
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    last_sent_at TIMESTAMPTZ,
    last_error TEXT,
    updated_by TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_schedules_frequency
    ON email_schedules (frequency);

ALTER TABLE email_schedules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "email_schedules_read" ON email_schedules;
DROP POLICY IF EXISTS "email_schedules_write" ON email_schedules;

CREATE POLICY "email_schedules_read" ON email_schedules
    FOR SELECT USING (true);

CREATE POLICY "email_schedules_write" ON email_schedules
    FOR ALL USING (true) WITH CHECK (true);
