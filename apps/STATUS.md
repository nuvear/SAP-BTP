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
| Northwind tools and Policy tool, as functions and over MCP | 28 of 28 tests pass (4 new for the HANA store wiring), plus a manual check over HTTP with two users and with no user |
| Deployment of the data service to BTP (`mta.yaml`, `xs-security.json`) | `northwind-service-srv` Started 1/1 at 256 MB; HDI container with 2 bindings; the service address answers 401 without a token |
| Cockpit roles for the two personas (DEPLOY.md step 5) | `SalesHQ` collection assigned to the account user; role `SalesRegion_UK` (country = UK) inside collection `Northwind SalesRegion UK`, unassigned until the Steven demo. Not yet exercised end to end: that needs a client that carries an XSUAA token |
| Policy store loaded in HANA | 86 passages, 13 documents in `POLICY_CHUNKS`, embedded in the database; 5 evaluation questions verified for Nancy and Steven, superseded/restricted/injected passages excluded (`phase0/RESULTS.md`) |
| SAP HANA Cloud vector engine and built-in embeddings (Phase 0) | All 7 checks pass on `northwind-hana`; `SAP_NEB.20240715` gives 768 dimensions; filtered search returns `expedite` first. See `phase0/RESULTS.md` |

## Written but not run

| Part | Why not | Needs |
|---|---|---|
| `mcp-servers/hana_store.py` Python wrapper and `policy-loader/load_to_hana.py` | The SQL is verified on the loaded table; the hdbcli path is covered by 4 fake-cursor tests, not yet by a live run | `POLICY_READER` user (Raj runs `hana/create_policy_reader.sql`) and one terminal run with the password prompted |

## Not started, because it needs your BTP account or a decision

1. XSUAA sign-in for the MCP server. Decision 2026-09-18: Option A, XSUAA directly as Claude's OAuth server
   (token validation + protected-resource metadata + Claude's callback in xs-security.json), one deploy, time-boxed;
   fallback Option C, App Router first. Until then `identity.py` refuses every call unless `DEV_MODE=1`. That is deliberate.
2. Deployment files for the MCP server. They wait for item 1: it must never be deployed without sign-in.
4. The Destination service lookup for the CAP service address. Locally it is an environment variable.
5. The LangGraph agent, the web chat and the audit table (Stage B).
6. Colab notebooks.

## Known limits of what exists

- The local policy store ranks by keywords (BM25), not by meaning. A question that shares no words with
  the right passage will miss it. That is the gap embeddings close, and a useful thing to show in Lab 2.
- Product search by name does not fold accents: "Rossle" does not find "Rössle Sauerkraut".
- `days_until_required` is the only derived figure the tools return. All policy reasoning is left to the
  model and the documents, on purpose.
