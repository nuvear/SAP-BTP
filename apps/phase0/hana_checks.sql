-- Phase 0: does this SAP HANA Cloud instance support what the Policy server needs?
-- Run in the SAP HANA Database Explorer (SQL console), one block at a time, as DBADMIN.
-- Each block says what a good result looks like. Copy any error text back to Claude exactly as shown.

-- 1. Database version (for the record).
SELECT VERSION FROM M_DATABASE;

-- 2. Vector type. Expected: one row showing [1,2,3].
SELECT TO_REAL_VECTOR('[1,2,3]') AS V FROM DUMMY;

-- 3. Similarity function. Expected: 1 for identical vectors, 0 for perpendicular ones.
SELECT COSINE_SIMILARITY(TO_REAL_VECTOR('[1,0,0]'), TO_REAL_VECTOR('[1,0,0]')) AS SAME,
       COSINE_SIMILARITY(TO_REAL_VECTOR('[1,0,0]'), TO_REAL_VECTOR('[0,1,0]')) AS PERPENDICULAR
FROM DUMMY;

-- 4. THE IMPORTANT ONE: built-in embeddings. Expected: DIMENSIONS = 768.
--    If this fails, stop here and send the error text. Blocks 5 to 7 depend on it.
SELECT CARDINALITY(VECTOR_EMBEDDING('Can order 11019 be expedited?', 'QUERY', 'SAP_NEB.20240715')) AS DIMENSIONS
FROM DUMMY;

-- 5. A miniature policy store, using exactly the statements of apps/mcp-servers/hana_store.py.
CREATE TABLE PHASE0_CHUNKS (
  CHUNK_ID NVARCHAR(40) PRIMARY KEY,
  STATUS   NVARCHAR(30),
  AUDIENCE NVARCHAR(40),
  TEXT     NCLOB,
  VEC      REAL_VECTOR(768)
);

INSERT INTO PHASE0_CHUNKS VALUES ('expedite', 'current', 'all-staff',
  'An order may be expedited when it has not shipped and its required date is within 5 calendar days.',
  VECTOR_EMBEDDING('An order may be expedited when it has not shipped and its required date is within 5 calendar days.', 'DOCUMENT', 'SAP_NEB.20240715'));
INSERT INTO PHASE0_CHUNKS VALUES ('seafood', 'current', 'all-staff',
  'Seafood may ship only with Speedy Express, with a maximum transit of 3 days.',
  VECTOR_EMBEDDING('Seafood may ship only with Speedy Express, with a maximum transit of 3 days.', 'DOCUMENT', 'SAP_NEB.20240715'));
INSERT INTO PHASE0_CHUNKS VALUES ('old-discount', 'superseded', 'all-staff',
  'A sales representative may give a discount of up to 5 percent on their own authority.',
  VECTOR_EMBEDDING('A sales representative may give a discount of up to 5 percent on their own authority.', 'DOCUMENT', 'SAP_NEB.20240715'));
INSERT INTO PHASE0_CHUNKS VALUES ('london-memo', 'current', 'sales-london',
  'We are prepared to go as far as 20 percent to keep the QUICK-Stop account.',
  VECTOR_EMBEDDING('We are prepared to go as far as 20 percent to keep the QUICK-Stop account.', 'DOCUMENT', 'SAP_NEB.20240715'));

-- 6. Semantic search WITH the access filter. The question shares almost no words with the right passage.
--    Expected: first row CHUNK_ID = 'expedite'. 'old-discount' and 'london-memo' must NOT appear at all.
SELECT TOP 3 CHUNK_ID, ROUND(COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING('customer wants a rush job, is that allowed?', 'QUERY', 'SAP_NEB.20240715')), 3) AS SCORE
FROM PHASE0_CHUNKS
WHERE STATUS = 'current' AND AUDIENCE IN ('all-staff', 'sales', 'sales-seattle')
ORDER BY SCORE DESC;

-- 7. Clean up.
DROP TABLE PHASE0_CHUNKS;
