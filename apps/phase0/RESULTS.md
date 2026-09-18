# Phase 0 results — 2026-09-18

Instance `northwind-hana` (SAP HANA Cloud, plan hana-free, created from Cloud Foundry by the deployment),
subaccount `trial`, org `cab3acb2trial`, space `dev`. Run as DBADMIN in the SQL console of SAP HANA Cloud Central.

| Block | Check | Result |
|---|---|---|
| 1 | `SELECT VERSION FROM M_DATABASE` | 4.00.000.00.1788856605 (HANA Cloud 2026.14.19, QRC 2/2026) |
| 2 | `TO_REAL_VECTOR('[1,2,3]')` | `[1,2,3]` |
| 3 | `COSINE_SIMILARITY` same / perpendicular | 1 / 0 |
| 4 | `CARDINALITY(VECTOR_EMBEDDING(…, 'QUERY', 'SAP_NEB.20240715'))` | **768** |
| 5 | Create PHASE0_CHUNKS, insert 4 passages embedded with `VECTOR_EMBEDDING(…, 'DOCUMENT', …)` | Success |
| 6 | Filtered TOP 3 search for "customer wants a rush job, is that allowed?" | `expedite` 0.511, `seafood` 0.498 — 2 rows; `old-discount` and `london-memo` excluded by the WHERE clause |
| 7 | `DROP TABLE PHASE0_CHUNKS` | Success |

Unfiltered ranking of the same question, for the course (not part of the checks):
`expedite` 0.511, `seafood` 0.498, `old-discount` 0.493, `london-memo` 0.434.

What this shows, and why it matters for Lab 2: the superseded discount policy scores 0.493, only 0.018 below the
right answer. Similarity alone would not have kept it out; the status and audience filter in the WHERE clause did.
Rules live in the filter, meaning lives in the vector.

Conclusions for the code:
- `mcp-servers/hana_store.py` keeps `EMBEDDING_MODEL = "SAP_NEB.20240715"` and `DIMENSION = 768`, both confirmed.
- SQL endpoint host pattern for this instance: `<id>.hana.prod-ap21.hanacloud.ondemand.com`, port 443
  (copy it from HANA Cloud Central > Copy SQL Endpoint). It is `prod-ap21` even on a trial account.
- Allowed connections is already "Allow all IP addresses", so Colab and the Mac can reach it.

Environment fixes made the same day (BTP cockpit):
- Subscribed to SAP HANA Cloud, plan `tools` (was missing; without it there is no HANA Cloud Central and no
  DBADMIN password reset).
- Assigned role collections `SAP HANA Cloud Administrator` and `SAP HANA Cloud Security Administrator` to the
  account user. The second one is what shows the "Reset DBADMIN Password" action.
- DBADMIN password was reset by the account owner in HANA Cloud Central (instance "..." menu > Reset DBADMIN
  Password). The first sign-in with the temporary password forces a change. The password is not recorded anywhere.

Deployment state seen in the cockpit: `northwind-service-srv` Started 1/1 (256 MB, CAP server v10.1.1),
`northwind-service-db-deployer` Stopped (ran once, as intended), service instances `northwind-service-auth` (XSUAA)
and `northwind-service-db` (HDI, 2 bindings) Usable. The service address
`https://cab3acb2trial-dev-northwind-service-srv.cfapps.ap21.hana.ondemand.com/odata/v4/northwind/Orders`
answers 401 without a token, which is the correct production behaviour.

## Policy store load and search — same day, later

`POLICY_CHUNKS` was created in the DBADMIN schema and all 86 passages inserted through the SQL console
(`apps/hana/load_policy_chunks.sql`), then embedded in one statement:
`UPDATE POLICY_CHUNKS SET VEC = VECTOR_EMBEDDING(TO_NVARCHAR(TEXT), 'DOCUMENT', 'SAP_NEB.20240715')`.
Result: 86 loaded, 86 embedded, 13 documents. (`COUNT(VEC)` is not supported on REAL_VECTOR; count with
`SUM(CASE WHEN VEC IS NULL THEN 0 ELSE 1 END)`.)

The exact SEARCH statement of `mcp-servers/hana_store.py`, lab date 2026-05-07, k = 4:

| Question | Audiences | Top result (score) | Check |
|---|---|---|---|
| customer wants a rush job, is that allowed? | Nancy: all-staff, sales, sales-seattle | NW-RUN-001 Situation 1 (0.672), NW-POL-002 §4 (0.648), NW-GLO-001 glossary (0.641) | semantic match, no shared words needed |
| How much discount can I give a customer on my own authority? | Nancy | NW-POL-001 v2.0 §8 (0.720), NW-RUN-001 Situation 6 (0.719), v2.0 §4, §1 | superseded v1.0 excluded; unfiltered, v1.0 §4 scores 0.685 |
| How far are we prepared to go on the QUICK-Stop contract discount? | Nancy | NW-ACC-QUICK §Expedite terms (0.642) … | London memo absent |
| same | Steven: all-staff, sales, sales-london | NW-MEM-001 §2 (0.727) | memo visible to London only |
| Has the lead time for Pavlova products changed? | Nancy | NW-POL-005 lead times (0.637) | supplier email with the injection absent (unverified-external) |

Conclusion: `hana_store.py` is correct as written; `POLICY_STORE=hana` is wired in `policy_tools.py`
(credentials from a user-provided service `policy-db` on BTP or `HANA_*` variables on a laptop). Still to do:
create `POLICY_READER` (`apps/hana/create_policy_reader.sql`, run by Raj) and run `policy-loader/load_to_hana.py`
once from a terminal to prove the Python path end to end.
