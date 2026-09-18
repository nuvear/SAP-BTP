# apps: the Northwind Order Advisor, local build

Everything here runs on a laptop with no SAP BTP account, and the same code is deployed on BTP trial with SAP sign-in
(`DEPLOY.md`, `DEPLOY-MCP.md`). See `STATUS.md` for what is tested where. Students: start with the workbook's Setup section.

```text
apps/
  northwind-service/   CAP OData service over Northwind. Read-only. Holds THE row rule.
  policy-loader/       Parses the 14 policy documents into passages with metadata (chunks.jsonl).
  mcp-servers/         Two tool groups over MCP: live order data, and policy retrieval (RAG).
```

## Run it locally

Terminal 1, the data service (Node 20 or later):

```bash
cd apps/northwind-service
npm install
npm test          # 9 tests: same request, different users, different rows
npm start         # http://localhost:4004/odata/v4/northwind   users: nancy/nancy, steven/steven
```

Terminal 2, the passages and the MCP server (Python 3.11 or later):

```bash
cd apps/policy-loader
pip install -r requirements.txt
python loader.py --data ../../data/northwind --out chunks.jsonl     # 86 passages from 14 documents

cd ../mcp-servers
pip install -r requirements.txt
python -m pytest -q                                                 # 45 tests
DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 python server.py advisor   # http://localhost:8000/mcp
```

Try it with MCP Inspector (`npx @modelcontextprotocol/inspector`): connect to `http://localhost:8000/mcp`
with the header `X-Dev-User: nancy`, then again with `steven`, and ask both for order 11070.

## The two users

| User | Office | Orders visible | Document audiences |
|---|---|---|---|
| `nancy` | Seattle, role `SalesHQ` | all 830 | all-staff, sales, sales-seattle |
| `steven` | London, role `SalesRegion` | the 224 orders of UK salespeople | all-staff, sales, sales-london |

## Where each rule lives

| Rule | Lives in | Why there |
|---|---|---|
| Which order rows a user may read | `northwind-service/srv/northwind-service.cds` | The data service owns the data. The MCP server only forwards the identity. |
| Which documents a user may retrieve | `mcp-servers/stores.py`, function `visible()` | The Policy server owns the document store. The filter runs before ranking. |
| What the model may do | The tool list in `mcp-servers/server.py` | Three read-only tools with checked inputs. No generic query tool exists. |

## Switches used in the labs

| Variable | Meaning |
|---|---|
| `DEV_MODE=1` | Local users from `DEV_USER` or the `X-Dev-User` header. Without it the server verifies XSUAA tokens (`xsuaa.py`) and refuses every call that has none. Never deploy with it. |
| `LAB_TODAY=2026-05-07` | The fixed lab date. The sample data ends on 2026-05-06. |
| `STRICT_FILTERS=0` | Robustness lab only: switches the document filter off, to show what it protects against. |
| `POLICY_STORE=hana` | Use SAP HANA Cloud (semantic search with built-in embeddings) instead of the local keyword store. Credentials from `HANA_*` variables or the `policy-db` binding. |
