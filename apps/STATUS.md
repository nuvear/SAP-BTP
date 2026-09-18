# Build status

Last updated: 2026-09-18 (evening). Data layer built and tested in a sandbox, then deployed to SAP BTP trial and checked in the cockpit.

Target account: region Singapore (Azure, `ap21`), org `cab3acb2trial`, space `Dev`.

## Done and tested

| Part | Evidence |
|---|---|
| Northwind as CAP-ready CSV, all dates shifted forward 28 years | 8 files, 830 orders and 2,155 order lines; order 10248 dated 2024-07-04 |
| CAP service (CAP 10), read-only, row rule per user | 9 of 9 tests pass: nancy sees 830 orders, steven sees 224; steven gets 404 on order 11070; writes return 405 |
| Policy loader | 86 passages from 14 documents; PDF tables kept row by row; sections kept whole |
| Document filter (status, effective dates, audience) | Covered by 8 filter cases and 6 retrieval tests |
| Northwind tools and Policy tool, as functions and over MCP | 45 of 45 tests pass (17 new for XSUAA sign-in and OAuth metadata), plus a manual check over HTTP with two users and with no user |
| Deployment of the data service to BTP (`mta.yaml`, `xs-security.json`) | `northwind-service-srv` Started 1/1 at 256 MB; HDI container with 2 bindings; the service address answers 401 without a token |
| Cockpit roles for the two personas (DEPLOY.md step 5) | `SalesHQ` collection assigned to the account user; role `SalesRegion_UK` (country = UK) inside collection `Northwind SalesRegion UK`, unassigned until the Steven demo. Not yet exercised end to end: that needs a client that carries an XSUAA token |
| Policy store loaded in HANA | 86 passages, 13 documents in `POLICY_CHUNKS`, embedded in the database; 5 evaluation questions verified for Nancy and Steven, superseded/restricted/injected passages excluded (`phase0/RESULTS.md`) |
| SAP HANA Cloud vector engine and built-in embeddings (Phase 0) | All 7 checks pass on `northwind-hana`; `SAP_NEB.20240715` gives 768 dimensions; filtered search returns `expedite` first. See `phase0/RESULTS.md` |

## Written but not run

| Part | Why not | Needs |
|---|---|---|
| `mcp-servers/hana_store.py` Python wrapper and `policy-loader/load_to_hana.py` | The SQL is verified on the loaded table; the hdbcli path is covered by 4 fake-cursor tests, not yet by a live run | `POLICY_READER` user (Raj runs `hana/create_policy_reader.sql`) and one terminal run with the password prompted |

## Not started, because it needs your BTP account or a decision

1. DEPLOY the MCP server with sign-in (Option A; the code is complete, see `DEPLOY-MCP.md`). `xsuaa.py` verifies
   XSUAA tokens (signature from token_keys or the binding's verificationkey, expiry, issuer, audience);
   `identity.py` builds the user from the verified token and forwards it to the data service; `server.py` serves
   the OAuth metadata that Claude discovers and refuses to start without the XSUAA binding. `manifest.yml`,
   `Procfile`, `runtime.txt` are in `mcp-servers/`; `northwind-service/mta.yaml` now carries Claude's redirect URIs.
   Needs Raj: redeploy the data service (redirect URIs), `cf cups policy-db`, `cf push`, a service key, the
   connector in Claude. Time box: one attempt, then Option C (App Router first).
2. The Destination service lookup for the CAP service address. Today it is `NORTHWIND_SERVICE_URL` in the manifest.
3. The LangGraph agent, the web chat and the audit table (Stage B).
4. Colab notebooks.

## Known limits of what exists

- The local policy store ranks by keywords (BM25), not by meaning. A question that shares no words with
  the right passage will miss it. That is the gap embeddings close, and a useful thing to show in Lab 2.
- Product search by name does not fold accents: "Rossle" does not find "Rössle Sauerkraut".
- `days_until_required` is the only derived figure the tools return. All policy reasoning is left to the
  model and the documents, on purpose.
