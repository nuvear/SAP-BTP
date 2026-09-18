-- Technical database user for the Policy MCP server and for Colab: read access to POLICY_CHUNKS and nothing else.
-- Run as DBADMIN in the SQL console. Replace <choose-a-password> with a password YOU choose and keep
-- (Colab Secrets, or a terminal prompt). Never put it in a file in the repository. The console history keeps
-- the statement text, so clear the console history afterwards (History > Clear All).
CREATE USER POLICY_READER PASSWORD "<choose-a-password>" NO FORCE_FIRST_PASSWORD_CHANGE;
ALTER USER POLICY_READER DISABLE PASSWORD LIFETIME;
GRANT SELECT ON DBADMIN.POLICY_CHUNKS TO POLICY_READER;

-- Check from the reader's point of view (run after signing in as POLICY_READER):
-- SELECT COUNT(*) FROM DBADMIN.POLICY_CHUNKS;                      -- expected 86
-- SELECT TOP 1 CHUNK_ID FROM DBADMIN.POLICY_CHUNKS
--   WHERE STATUS='current' AND AUDIENCE IN ('all-staff')
--   ORDER BY COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING('rush job', 'QUERY', 'SAP_NEB.20240715')) DESC;
