"""Phase 0 checks from a terminal (Cursor, or any shell), instead of the Database Explorer.

    pip install hdbcli
    export HANA_HOST=<instance id>.hana.prod-ap21.hanacloud.ondemand.com      # SQL endpoint, WITHOUT ':443'
    # (the hana-free instance created from Cloud Foundry lives on 'prod-ap21', not 'trial-ap21';
    #  copy it from HANA Cloud Central > Copy SQL Endpoint)
    export HANA_USER=DBADMIN
    read -s HANA_PASSWORD && export HANA_PASSWORD                             # typed, never stored, never pasted into a chat
    python hana_checks.py

The instance must be RUNNING (trial instances stop every night) and must allow your IP address.
The script creates one small table, PHASE0_CHUNKS, and drops it again.

RESULT 2026-09-18 on northwind-hana (HANA Cloud 4.00.000.00.1788856605, NLP enabled): all checks pass,
VECTOR_EMBEDDING with SAP_NEB.20240715 returns 768 dimensions. See RESULTS.md.
"""
import os, sys
from hdbcli import dbapi

MODEL = os.environ.get("HANA_EMBEDDING_MODEL", "SAP_NEB.20240715")
DOCS = [
    ("expedite", "current", "all-staff", "An order may be expedited when it has not shipped and its required date is within 5 calendar days."),
    ("seafood", "current", "all-staff", "Seafood may ship only with Speedy Express, with a maximum transit of 3 days."),
    ("old-discount", "superseded", "all-staff", "A sales representative may give a discount of up to 5 percent on their own authority."),
    ("london-memo", "current", "sales-london", "We are prepared to go as far as 20 percent to keep the QUICK-Stop account."),
]

def main() -> int:
    missing = [k for k in ("HANA_HOST", "HANA_USER", "HANA_PASSWORD") if not os.environ.get(k)]
    if missing:
        print("Set these environment variables first:", ", ".join(missing)); return 2
    conn = dbapi.connect(address=os.environ["HANA_HOST"], port=int(os.environ.get("HANA_PORT", "443")),
                         user=os.environ["HANA_USER"], password=os.environ["HANA_PASSWORD"],
                         encrypt=True, sslValidateCertificate=True)
    cur, results = conn.cursor(), []

    def check(name, fn):
        try:
            results.append((name, "PASS", fn()))
        except Exception as e:                                  # report every check, do not stop at the first failure
            results.append((name, "FAIL", str(e).replace("\n", " ")[:300]))

    def one(sql, params=()):
        cur.execute(sql, params); return cur.fetchone()[0]

    check("1 version", lambda: one("SELECT VERSION FROM M_DATABASE"))
    check("2 vector type", lambda: str(one("SELECT TO_REAL_VECTOR('[1,2,3]') FROM DUMMY")))
    check("3 cosine similarity", lambda: one("SELECT COSINE_SIMILARITY(TO_REAL_VECTOR('[1,0,0]'), TO_REAL_VECTOR('[1,0,0]')) FROM DUMMY"))
    check(f"4 VECTOR_EMBEDDING with {MODEL}", lambda: f"{one('SELECT CARDINALITY(VECTOR_EMBEDDING(?, ?, ?)) FROM DUMMY', ('Can order 11019 be expedited?', 'QUERY', MODEL))} dimensions")

    def mini_store():
        try: cur.execute("DROP TABLE PHASE0_CHUNKS")
        except dbapi.Error: pass
        cur.execute("CREATE TABLE PHASE0_CHUNKS (CHUNK_ID NVARCHAR(40) PRIMARY KEY, STATUS NVARCHAR(30), AUDIENCE NVARCHAR(40), TEXT NCLOB, VEC REAL_VECTOR(768))")
        for cid, status, aud, text in DOCS:
            cur.execute("INSERT INTO PHASE0_CHUNKS VALUES (?,?,?,?, VECTOR_EMBEDDING(?, 'DOCUMENT', ?))", (cid, status, aud, text, text, MODEL))
        cur.execute("""SELECT TOP 3 CHUNK_ID, ROUND(COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING(?, 'QUERY', ?)), 3) AS SCORE
                       FROM PHASE0_CHUNKS WHERE STATUS = 'current' AND AUDIENCE IN (?,?,?) ORDER BY SCORE DESC""",
                    ("customer wants a rush job, is that allowed?", MODEL, "all-staff", "sales", "sales-seattle"))
        rows = cur.fetchall()
        cur.execute("DROP TABLE PHASE0_CHUNKS"); conn.commit()
        ids = [r[0] for r in rows]
        assert ids and ids[0] == "expedite", f"expected 'expedite' first, got {rows}"
        assert not {"old-discount", "london-memo"} & set(ids), f"the filter leaked: {rows}"
        return [(r[0], float(r[1])) for r in rows]

    check("5-7 mini store: insert, filtered semantic search, clean up", mini_store)

    print()
    for name, status, detail in results:
        print(f"{status}  {name}: {detail}")
    print("\nCopy the lines above to Claude. They contain no password.")
    return 0 if all(s == "PASS" for _, s, _ in results) else 1

if __name__ == "__main__":
    sys.exit(main())
