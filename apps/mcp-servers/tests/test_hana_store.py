"""HanaStore without a database: a fake hdbcli cursor records the SQL and parameters and returns rows.

The real statements were verified on northwind-hana on 2026-09-18 (apps/phase0/RESULTS.md). These tests
guard the wiring: parameter order, the audience placeholders, the shape of the result rows.
"""
from datetime import date
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hana_store import HanaStore, EMBEDDING_MODEL, SEARCH  # noqa: E402


class FakeCursor:
    def __init__(self, rows):
        self.rows, self.calls = rows, []
        self.description = [(c,) for c in ("CHUNK_ID", "DOC_ID", "VERSION", "TITLE", "SECTION", "STATUS",
                                            "EFFECTIVE_FROM", "EFFECTIVE_TO", "CLASSIFICATION", "AUDIENCE",
                                            "TEXT", "SCORE")]

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return (len(self.rows),)


class FakeConn:
    def __init__(self, rows):
        self.cur = FakeCursor(rows)

    def cursor(self):
        return self.cur

    def commit(self):
        pass


ROW = ("NW-POL-002@1.0#04", "NW-POL-002", "1.0", "Order Expedite and Shipping Policy",
       "4. When an order may be expedited", "current", date(2026, 2, 1), None, "internal", "all-staff",
       "An order may be expedited only when ...", 0.64812)


def test_search_binds_question_model_dates_and_audiences():
    conn = FakeConn([ROW])
    hits = HanaStore(conn).search("rush job?", ["all-staff", "sales", "sales-seattle"], date(2026, 5, 7), k=3)
    sql, params = conn.cur.calls[-1]
    assert sql.startswith("\nSELECT TOP 3 ")
    assert "AUDIENCE IN (?,?,?)" in sql and "STATUS = 'current'" in sql
    assert params == ("rush job?", EMBEDDING_MODEL, "2026-05-07", "2026-05-07", "all-staff", "sales", "sales-seattle")
    assert hits[0]["chunk_id"] == "NW-POL-002@1.0#04"
    assert hits[0]["effective_from"] == "2026-02-01" and hits[0]["effective_to"] is None
    assert hits[0]["score"] == 0.648
    assert set(hits[0]) >= {"doc_id", "version", "title", "section", "status", "text"}   # what policy_tools reads


def test_unfiltered_search_has_no_where_clause():
    conn = FakeConn([ROW])
    HanaStore(conn).search("rush job?", ["all-staff"], date(2026, 5, 7), k=6, strict=False)
    sql, params = conn.cur.calls[-1]
    assert "WHERE" not in sql and params == ("rush job?", EMBEDDING_MODEL)


def test_load_embeds_every_passage_inside_the_database(tmp_path):
    chunks = tmp_path / "chunks.jsonl"
    rec = {"chunk_id": "X@1.0#01", "doc_id": "X", "version": "1.0", "title": "T", "section": "S",
           "status": "current", "effective_from": "2026-01-01", "effective_to": None,
           "classification": "internal", "audience": "all-staff", "folder": "corpus", "text": "hello"}
    chunks.write_text(json.dumps(rec) + "\n" + json.dumps(rec | {"chunk_id": "X@1.0#02"}) + "\n")
    conn = FakeConn([])
    assert HanaStore(conn).load(str(chunks)) == 2
    inserts = [c for c in conn.cur.calls if "INSERT" in c[0]]
    assert len(inserts) == 2
    sql, params = inserts[0]
    assert "VECTOR_EMBEDDING(?, 'DOCUMENT', ?)" in sql
    assert params[-3:] == ("hello", "hello", EMBEDDING_MODEL)      # text stored, text embedded, model name
    assert conn.cur.calls[0][0].startswith("DELETE FROM POLICY_CHUNKS")


def test_policy_tools_switch_to_hana_uses_binding_when_present(monkeypatch):
    import policy_tools
    monkeypatch.setattr(policy_tools, "_store", None)
    monkeypatch.setenv("POLICY_STORE", "hana")
    monkeypatch.setenv("VCAP_SERVICES", json.dumps({"user-provided": [
        {"name": "policy-db", "credentials": {"host": "h", "port": 443, "user": "POLICY_READER", "password": "p"}}]}))
    seen = {}

    def fake_connect(creds):
        seen.update(creds); return FakeConn([])
    import hana_store
    monkeypatch.setattr(hana_store, "connect_from_binding", fake_connect)
    store = policy_tools.store()
    assert isinstance(store, HanaStore) and seen["user"] == "POLICY_READER"
    monkeypatch.setattr(policy_tools, "_store", None)
