-- RO Shield — add per-schedule report checkboxes (Reporting / ROI)
-- Run once in Supabase → SQL Editor after docs/EMAIL_SCHEDULES.sql

ALTER TABLE email_schedules ADD COLUMN IF NOT EXISTS include_reporting BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE email_schedules ADD COLUMN IF NOT EXISTS include_roi BOOLEAN NOT NULL DEFAULT TRUE;
