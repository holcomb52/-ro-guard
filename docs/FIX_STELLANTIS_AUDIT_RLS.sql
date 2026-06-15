-- Run once in Supabase → SQL Editor for OEM Audit Guide uploads
-- (Uses dealer_settings — same storage pattern as Audit Rules and POPPS)

ALTER TABLE dealer_settings ADD COLUMN IF NOT EXISTS stellantis_audit_library JSONB DEFAULT '{"active_id":"","documents":{}}'::jsonb;

-- dealer_settings should already allow app read/write (Audit Rules / POPPS work).
-- If saves still fail, re-apply dealer_settings policies from docs/SUPABASE_SCHEMA.sql.
