"""SAP HANA Cloud store for policy passages: stage 3 (embed) and stage 4 (retrieve) of RAG.

STATUS 2026-09-18: the table POLICY_CHUNKS on northwind-hana holds all 86 passages, embedded with
VECTOR_EMBEDDING(..., 'SAP_NEB.20240715') = 768 dimensions. The SEARCH statement below was verified on that
data for five evaluation questions (apps/phase0/RESULTS.md). The Python wrapper connects with hdbcli.

Design points to notice:
  1. The text never leaves the database to be embedded: VECTOR_EMBEDDING runs inside HANA, for the passages
     (DOCUMENT) and for the question (QUERY).
  2. The access filter is part of the WHERE clause, so a restricted passage is never even scored.
     These are the same four conditions as stores.visible(). Unfiltered, the superseded discount policy
     scores within 0.04 of the current one: the rule lives in the filter, not in the similarity.
  3. Credentials come from the environment (a technical user with SELECT only) or, on BTP, from a
     user-provided service binding. Never from code, never from a file in the repository.

Environment for a laptop or Colab:
    HANA_HOST=<id>.hana.prod-ap21.hanacloud.ondemand.com   HANA_PORT=443
    HANA_USER=POLICY_READER   HANA_PASSWORD=<typed at a prompt, or a Colab secret>
    HANA_SCHEMA=DBADMIN       (the schema that owns POLICY_CHUNKS; default DBADMIN)
"""
from __future__ import annotations
import json
import os
from datetime import date

EMBEDDING_MODEL = "SAP_NEB.20240715"      # confirmed on northwind-hana, 2026-09-18
DIMENSION = 768
TABLE = "POLICY_CHUNKS"

DDL = f"""
CREATE TABLE {TABLE} (
  CHUNK_ID        NVARCHAR(80) PRIMARY KEY,
  DOC_ID          NVARCHAR(40),  VERSION NVARCHAR(20),  TITLE NVARCHAR(200),  SECTION NVARCHAR(200),
  STATUS          NVARCHAR(30),  EFFECTIVE_FROM DATE,   EFFECTIVE_TO DATE,
  CLASSIFICATION  NVARCHAR(30),  AUDIENCE NVARCHAR(40), FOLDER NVARCHAR(20),
  TEXT            NCLOB,
  VEC             REAL_VECTOR({DIMENSION})
)"""

INSERT = f"""
INSERT INTO {TABLE} (CHUNK_ID, DOC_ID, VERSION, TITLE, SECTION, STATUS, EFFECTIVE_FROM, EFFECTIVE_TO,
                     CLASSIFICATION, AUDIENCE, FOLDER, TEXT, VEC)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?, VECTOR_EMBEDDING(?, 'DOCUMENT', ?))"""

SEARCH = """
SELECT TOP {k} CHUNK_ID, DOC_ID, VERSION, TITLE, SECTION, STATUS, EFFECTIVE_FROM, EFFECTIVE_TO, CLASSIFICATION,
       AUDIENCE, TO_NVARCHAR(TEXT) AS TEXT,
       COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING(?, 'QUERY', ?)) AS SCORE
FROM {table}
WHERE STATUS = 'current'
  AND (EFFECTIVE_FROM IS NULL OR EFFECTIVE_FROM <= ?)
  AND (EFFECTIVE_TO   IS NULL OR EFFECTIVE_TO   >= ?)
  AND AUDIENCE IN ({audience_marks})
ORDER BY SCORE DESC"""

# The robustness lab (STRICT_FILTERS=0) shows what happens without the WHERE clause.
SEARCH_UNFILTERED = """
SELECT TOP {k} CHUNK_ID, DOC_ID, VERSION, TITLE, SECTION, STATUS, EFFECTIVE_FROM, EFFECTIVE_TO, CLASSIFICATION,
       AUDIENCE, TO_NVARCHAR(TEXT) AS TEXT,
       COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING(?, 'QUERY', ?)) AS SCORE
FROM {table}
ORDER BY SCORE DESC"""


def connect_from_env():
    """hdbcli connection from HANA_* variables. Import is local so that tests without hdbcli still run."""
    from hdbcli import dbapi
    missing = [k for k in ("HANA_HOST", "HANA_USER", "HANA_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise RuntimeError("Set " + ", ".join(missing) + " (the password at a prompt, never in a file)")
    return dbapi.connect(address=os.environ["HANA_HOST"], port=int(os.environ.get("HANA_PORT", "443")),
                         user=os.environ["HANA_USER"], password=os.environ["HANA_PASSWORD"],
                         encrypt=True, sslValidateCertificate=True,
                         currentSchema=os.environ.get("HANA_SCHEMA", "DBADMIN"))


def connect_from_binding(credentials: dict):
    """hdbcli connection from a user-provided service binding on Cloud Foundry
    (cf create-user-provided-service policy-db -p '{"host":..,"port":443,"user":..,"password":..,"schema":..}')."""
    from hdbcli import dbapi
    return dbapi.connect(address=credentials["host"], port=int(credentials.get("port", 443)),
                         user=credentials["user"], password=credentials["password"],
                         encrypt=True, sslValidateCertificate=True,
                         currentSchema=credentials.get("schema", "DBADMIN"))


class HanaStore:
    def __init__(self, connection, table: str = TABLE):
        """connection: an hdbcli.dbapi connection (see connect_from_env / connect_from_binding)."""
        self.conn = connection
        self.table = table

    def create_table(self):
        self.conn.cursor().execute(DDL.replace(TABLE, self.table))

    def load(self, chunks_file: str) -> int:
        rows = [json.loads(line) for line in open(chunks_file, encoding="utf-8") if line.strip()]
        cur = self.conn.cursor()
        cur.execute(f"DELETE FROM {self.table}")
        for c in rows:
            cur.execute(INSERT.replace(TABLE, self.table),
                        (c["chunk_id"], c["doc_id"], c["version"], c["title"], c["section"], c["status"],
                         c["effective_from"], c["effective_to"], c["classification"], c["audience"],
                         c["folder"], c["text"], c["text"], EMBEDDING_MODEL))
        self.conn.commit()
        return len(rows)

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {self.table}")
        return int(cur.fetchone()[0])

    def search(self, question: str, audiences, today: date, k: int = 4, strict: bool = True) -> list[dict]:
        cur = self.conn.cursor()
        if strict:
            sql = SEARCH.format(k=int(k), table=self.table, audience_marks=",".join("?" * len(audiences)))
            cur.execute(sql, (question, EMBEDDING_MODEL, today.isoformat(), today.isoformat(), *audiences))
        else:
            cur.execute(SEARCH_UNFILTERED.format(k=int(k), table=self.table), (question, EMBEDDING_MODEL))
        cols = [d[0].lower() for d in cur.description]
        out = []
        for row in cur.fetchall():
            r = dict(zip(cols, row))
            for key in ("effective_from", "effective_to"):        # same shape as LocalStore: ISO strings or None
                r[key] = r[key].isoformat() if r[key] else None
            r["score"] = round(float(r["score"]), 3)
            out.append(r)
        return out
