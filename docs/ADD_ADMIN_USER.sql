-- Grant yourself (or another owner) the RO Shield Admin role
-- Run once in Supabase → SQL Editor
--
-- Admin = full access including Admin → Pricing & ROI (platform owner only).
-- Manager and Warranty Admin keep their current dealership roles.
--
-- 1. Replace the email and name below with YOUR Supabase login email.
-- 2. Run this entire script.
-- 3. Sign out of RO Shield and sign back in so the role refreshes.

UPDATE personnel
SET
    role = 'Admin',
    active = true,
    name = COALESCE(NULLIF(trim(name), ''), 'Platform Admin')
WHERE lower(trim(email)) = lower(trim('holcomb52@yahoo.com'));

INSERT INTO personnel (name, role, email, active)
SELECT
    'Platform Admin',
    'Admin',
    lower(trim('holcomb52@yahoo.com')),
    true
WHERE NOT EXISTS (
    SELECT 1
    FROM personnel
    WHERE lower(trim(email)) = lower(trim('holcomb52@yahoo.com'))
);

-- Verify:
SELECT id, name, role, email, active
FROM personnel
WHERE lower(trim(email)) = lower(trim('holcomb52@yahoo.com'));
