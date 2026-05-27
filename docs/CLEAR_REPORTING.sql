-- Run once in Supabase → SQL Editor → New query → Run
-- Clears all saved reviews from Reporting and enables the in-app clear button.

ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "reviews_read" ON reviews;
DROP POLICY IF EXISTS "reviews_write" ON reviews;

CREATE POLICY "reviews_read" ON reviews
    FOR SELECT USING (true);

CREATE POLICY "reviews_write" ON reviews
    FOR ALL USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION clear_all_reviews()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE cnt integer;
BEGIN
  DELETE FROM reviews;
  GET DIAGNOSTICS cnt = ROW_COUNT;
  RETURN cnt;
END;
$$;

GRANT EXECUTE ON FUNCTION clear_all_reviews() TO anon, authenticated;

SELECT clear_all_reviews() AS reviews_removed;
