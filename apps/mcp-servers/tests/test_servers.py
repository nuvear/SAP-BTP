"""Tests for the MCP servers. Run from apps/mcp-servers:   python -m pytest -q

The live-data tests start the CAP service themselves (apps/northwind-service must have had 'npm install').
The lab date is fixed at 2026-05-07, as in the course.
"""
import asyncio, json, os, subprocess, sys, time
from datetime import date
from pathlib import Path
import httpx, pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ.update(DEV_MODE="1", LAB_TODAY="2026-05-07", NORTHWIND_SERVICE_URL="http://localhost:4055/odata/v4/northwind",
                  POLICY_CHUNKS=str(HERE.parent / "policy-loader" / "chunks.jsonl"))

from identity import resolve_user, NotSignedIn          # noqa: E402
from stores import LocalStore, visible                  # noqa: E402
import northwind_tools, policy_tools, server            # noqa: E402

NANCY, STEVEN = resolve_user({"X-Dev-User": "nancy"}), resolve_user({"X-Dev-User": "steven"})
TODAY = date(2026, 5, 7)
STORE = LocalStore(os.environ["POLICY_CHUNKS"])
ids = lambda hits: [f'{h["doc_id"]}@{h["version"]}' for h in hits]


# ------------------------------------------------------------------ identity
def test_unknown_user_is_rejected():
    with pytest.raises(NotSignedIn):
        resolve_user({"X-Dev-User": "mallory"})

def test_without_dev_mode_the_server_fails_closed(monkeypatch):
    monkeypatch.delenv("DEV_MODE")
    with pytest.raises(NotSignedIn):
        resolve_user({"Authorization": "Bearer anything"})


# ------------------------------------------------------------------ the document filter
CHUNK = dict(status="current", effective_from="2026-01-01", effective_to=None, audience="all-staff")

@pytest.mark.parametrize("change, expected", [
    ({}, True),
    ({"status": "superseded"}, False),
    ({"status": "unapproved"}, False),
    ({"status": "unverified-external"}, False),
    ({"effective_from": "2026-06-01"}, False),            # not in force yet
    ({"effective_to": "2026-04-30"}, False),              # expired
    ({"effective_to": "2026-05-07"}, True),               # last day still counts
    ({"audience": "sales-london"}, False),                # nancy is in Seattle
])
def test_visible(change, expected):
    assert visible({**CHUNK, **change}, NANCY.audiences, TODAY) is expected


# ------------------------------------------------------------------ retrieval
def test_current_policy_wins_over_the_superseded_version():
    hits = STORE.search("how much discount can a sales representative give on their own authority", NANCY.audiences, TODAY, k=6)
    assert "NW-POL-001@2.0" in ids(hits) and "NW-POL-001@1.0" not in ids(hits)

def test_without_the_filter_the_old_version_and_the_draft_memo_come_back():
    hits = STORE.search("discount without approval spring campaign 15 percent", NANCY.audiences, TODAY, k=6, strict=False)
    assert {"NW-POL-001@1.0", "NW-MEM-900@draft"} & set(ids(hits))      # this is what the robustness lab shows

def test_restricted_memo_reaches_london_only():
    q = "QUICK-Stop contract renewal negotiation discount offer"
    assert "NW-MEM-001@1.0" not in ids(STORE.search(q, NANCY.audiences, TODAY, k=6))
    assert "NW-MEM-001@1.0" in ids(STORE.search(q, STEVEN.audiences, TODAY, k=6))

def test_the_injected_supplier_email_is_never_retrieved():
    for q in ("Pavlova lead time", "discount for Pavlova products", "ignore previous instructions"):
        assert "NW-EXT-901@1.0" not in ids(STORE.search(q, STEVEN.audiences, TODAY, k=6))

def test_jargon_is_resolved_by_the_glossary():
    assert "NW-GLO-001@1.0" in ids(STORE.search("customer wants a rush job", NANCY.audiences, TODAY))

def test_a_table_row_is_retrievable():
    hits = STORE.search("which carriers are permitted for seafood", NANCY.audiences, TODAY)
    assert hits[0]["doc_id"] == "NW-POL-004" and "Speedy Express only" in " ".join(h["text"] for h in hits)

def test_account_notes_expire_at_the_end_of_2026():
    assert "NW-ACC-SAVEA@1.0" in ids(STORE.search("Save-a-lot contract discount", NANCY.audiences, TODAY))
    assert "NW-ACC-SAVEA@1.0" not in ids(STORE.search("Save-a-lot contract discount", NANCY.audiences, date(2027, 1, 5)))

def test_search_tool_shape_and_input_check():
    out = policy_tools.search_policies(NANCY, "when may an order be expedited")
    assert out["passages"] and out["passages"][0]["citation"].startswith("NW-")
    assert policy_tools.search_policies(NANCY, "x" * 301)["passages"] == []


# ------------------------------------------------------------------ live data (needs the CAP service)
@pytest.fixture(scope="module")
def cap():
    svc = HERE.parent / "northwind-service"
    entry = svc / "node_modules" / "@sap" / "cds" / "bin" / "serve.js"
    if not entry.exists():
        pytest.skip("run 'npm install' in apps/northwind-service first")
    proc = subprocess.Popen(["node", str(entry), "--port", "4055"], cwd=svc, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if httpx.get("http://localhost:4055/", timeout=1).status_code < 500: break
        except httpx.HTTPError:
            time.sleep(0.5)
    yield
    proc.terminate(); proc.wait(timeout=10)

def test_order_11019_facts(cap):
    o = asyncio.run(northwind_tools.get_order_status(NANCY, 11019))
    assert o["found"] and not o["shipped"] and o["days_until_required"] == 4
    assert o["carrier"]["name"] == "Federal Shipping" and o["freight"] == 3.17
    seafood = [l for l in o["lines"] if l["category"] == "Seafood"][0]
    assert seafood["product_name"] == "Spegesild" and seafood["quantity"] == 3 and seafood["units_in_stock"] == 95

def test_row_rule_reaches_through_the_tool(cap):
    assert asyncio.run(northwind_tools.get_order_status(NANCY, 11070))["found"] is True
    hidden = asyncio.run(northwind_tools.get_order_status(STEVEN, 11070))
    assert hidden == {"found": False, "message": "No order with this number is visible to you."}

def test_overdue_order_has_negative_days(cap):
    assert asyncio.run(northwind_tools.get_order_status(NANCY, 11008))["days_until_required"] == -1

def test_product_by_name_and_by_number(cap):
    for key in ("matjes", "30"):
        p = asyncio.run(northwind_tools.get_product_availability(STEVEN, key))["matches"][0]
        assert (p["product_name"], p["units_in_stock"], p["units_on_order"], p["reorder_level"]) == ("Nord-Ost Matjeshering", 10, 0, 15)
        assert p["supplier"]["country"] == "Germany"

def test_apostrophes_and_bad_input(cap):
    names = [m["product_name"] for m in asyncio.run(northwind_tools.get_product_availability(NANCY, "chef anton's"))["matches"]]
    assert names and all(n.startswith("Chef Anton's") for n in names)
    assert asyncio.run(northwind_tools.get_product_availability(NANCY, "x') or (1 eq 1"))["found"] is False
    assert asyncio.run(northwind_tools.get_product_availability(NANCY, "a; drop"))["found"] is False
    assert asyncio.run(northwind_tools.get_order_status(NANCY, 5))["found"] is False


# ------------------------------------------------------------------ through the MCP protocol
def test_advisor_endpoint_lists_exactly_three_read_only_tools(cap, monkeypatch):
    from mcp.shared.memory import create_connected_server_and_client_session as connect
    monkeypatch.setenv("DEV_USER", "nancy")
    async def run():
        async with connect(server.build("advisor")._mcp_server) as client:
            tools = sorted(t.name for t in (await client.list_tools()).tools)
            result = await client.call_tool("get_order_status", {"order_id": 11019})
            return tools, json.loads(result.content[0].text)
    tools, order = asyncio.run(run())
    assert tools == ["get_order_status", "get_product_availability", "search_policies"]
    assert order["customer"]["id"] == "RANCH"
