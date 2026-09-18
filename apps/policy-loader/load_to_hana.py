"""Load chunks.jsonl into POLICY_CHUNKS on SAP HANA Cloud and run one search, from a terminal or Colab.

    pip install hdbcli
    export HANA_HOST=<id>.hana.prod-ap21.hanacloud.ondemand.com HANA_USER=DBADMIN HANA_SCHEMA=DBADMIN
    read -s HANA_PASSWORD && export HANA_PASSWORD        # typed, never stored
    python load_to_hana.py [--create] [chunks.jsonl]

--create makes the table first (drop it yourself if it exists). Loading needs INSERT on the table, so it runs
as DBADMIN or the owner; the MCP server later reads with POLICY_READER (hana/create_policy_reader.sql).
The same load was done once through the SQL console: hana/load_policy_chunks.sql.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))
from hana_store import HanaStore, connect_from_env  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chunks = args[0] if args else str(Path(__file__).with_name("chunks.jsonl"))
    store = HanaStore(connect_from_env())
    if "--create" in sys.argv:
        store.create_table(); print("table created")
    n = store.load(chunks)
    print(f"loaded {n} passages; table now holds {store.count()}")
    for r in store.search("customer wants a rush job, is that allowed?", ["all-staff", "sales", "sales-seattle"],
                          date(2026, 5, 7), k=3):
        print(f'{r["score"]:.3f}  {r["chunk_id"]:22}  {r["section"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
