-- Run once in Supabase → SQL Editor if OEM Audit Guide upload fails with:
-- "new row violates row-level security policy for table stellantis_audit_documents"

ALTER TABLE stellantis_audit_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "stellantis_audit_documents_read" ON stellantis_audit_documents;
DROP POLICY IF EXISTS "stellantis_audit_documents_write" ON stellantis_audit_documents;

CREATE POLICY "stellantis_audit_documents_read" ON stellantis_audit_documents
    FOR SELECT USING (true);

CREATE POLICY "stellantis_audit_documents_write" ON stellantis_audit_documents
    FOR ALL USING (true) WITH CHECK (true);

-- Allow the Streamlit app (anon / authenticated keys) to insert rows and use the id sequence
GRANT SELECT, INSERT, UPDATE, DELETE ON stellantis_audit_documents TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE stellantis_audit_documents_id_seq TO anon, authenticated;
