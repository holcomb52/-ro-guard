-- Manager login for bholcomb@newsmyrnacjd.com
-- Run AFTER: Supabase → Authentication → Users → Add user (same email + password)

UPDATE personnel
SET
    role = 'Manager',
    active = true,
    name = COALESCE(NULLIF(trim(name), ''), 'B Holcomb')
WHERE lower(trim(email)) = lower(trim('bholcomb@newsmyrnacjd.com'));

INSERT INTO personnel (name, role, email, active)
SELECT
    'B Holcomb',
    'Manager',
    lower(trim('bholcomb@newsmyrnacjd.com')),
    true
WHERE NOT EXISTS (
    SELECT 1
    FROM personnel
    WHERE lower(trim(email)) = lower(trim('bholcomb@newsmyrnacjd.com'))
);

SELECT id, name, role, email, active
FROM personnel
WHERE lower(trim(email)) = lower(trim('bholcomb@newsmyrnacjd.com'));
