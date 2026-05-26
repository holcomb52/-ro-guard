-- Run once in Supabase → SQL Editor → New query → Run
-- Clears all declined claims and enables the "Clear all declined claims" button in RO Shield.

ALTER TABLE claims ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "claims_read" ON claims;
DROP POLICY IF EXISTS "claims_write" ON claims;

CREATE POLICY "claims_read" ON claims
    FOR SELECT USING (true);

CREATE POLICY "claims_write" ON claims
    FOR ALL USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION clear_declined_claims()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE cnt integer;
BEGIN
  DELETE FROM claims WHERE claim_status = 'declined';
  GET DIAGNOSTICS cnt = ROW_COUNT;
  RETURN cnt;
END;
$$;

GRANT EXECUTE ON FUNCTION clear_declined_claims() TO anon, authenticated;

SELECT clear_declined_claims() AS declined_rows_removed;
