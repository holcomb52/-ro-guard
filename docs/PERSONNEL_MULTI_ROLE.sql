-- Enable multiple roles per person (e.g. Advisor + Warranty Admin)
-- Run once in Supabase → SQL Editor

ALTER TABLE personnel ADD COLUMN IF NOT EXISTS roles JSONB DEFAULT '[]'::jsonb;

UPDATE personnel
SET roles = jsonb_build_array(role)
WHERE role IS NOT NULL
  AND trim(role) <> ''
  AND (
    roles IS NULL
    OR roles = '[]'::jsonb
    OR jsonb_typeof(roles) <> 'array'
    OR jsonb_array_length(roles) = 0
  );

-- Optional: merge duplicate rows for the same email into one multi-role record
-- (only if you accidentally created separate rows per role)
-- Review results before running DELETE steps manually.

SELECT id, name, role, roles, email, active FROM personnel ORDER BY name;
