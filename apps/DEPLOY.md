# Deploying the Northwind data service to SAP BTP (trial)

Target: region Singapore (Azure), technical key `ap21` · org `cab3acb2trial` · space `Dev` · subaccount `trial`.

STATUS: deployed on 2026-09-18. `northwind-service-srv` is Started (1/1, 256 MB), the HDI container holds the
Northwind tables, and the service address answers 401 without a token. The HANA Cloud instance was created as a
Cloud Foundry service instance (`northwind-hana`, plan `hana-free`), so the org/space mapping came for free.
Phase 0 (vector engine, built-in embeddings) passed the same day: see `phase0/RESULTS.md`.

Only the data service is deployed at this stage. The MCP server is NOT deployed yet, because it has no
XSUAA sign-in. Never deploy it with `DEV_MODE=1`: that would publish an open endpoint.

## 0. One-time tools on your Mac

```bash
brew install cloudfoundry/tap/cf-cli@8
cf install-plugin multiapps          # gives 'cf deploy'
npm install -g mbt                   # builds the .mtar archive
```

## 1. SAP HANA Cloud instance (BTP cockpit, once)

1. Subaccount `trial` > Instances and Subscriptions > Create: service **SAP HANA Cloud**, plan **tools**
   (a subscription, free). Without it the instance's management link says "No subscription" and there is no
   HANA Cloud Central, no SQL console and no way to reset the DBADMIN password.
2. Security > Users > your user > Role Collections > Assign: **SAP HANA Cloud Administrator** and
   **SAP HANA Cloud Security Administrator** (the second one shows the "Reset DBADMIN Password" action).
3. Create the database instance, either way:
   - from the terminal, as a Cloud Foundry service instance (what was done here, by Cursor):
     `cf create-service hana-cloud hana-free northwind-hana -c params.json`, where the parameters JSON
     switches on NLP and allows all IP addresses (exact keys: SAP HANA Cloud documentation, "Create an
     instance using the CF CLI") — no instance mapping needed, the instance belongs to the space;
   - or in HANA Cloud Central > Create Instance, with Advanced Settings > **Natural Language Processing (NLP)**
     on, Allowed connections **Allow all IP addresses**, and Instance mapping to org `cab3acb2trial`, space `Dev`.
   Both are free tier: 16 GB memory, 80 GB disk, 1 vCPU, no backup.
4. DBADMIN password: the instance is created with a generated password nobody has. In HANA Cloud Central,
   instance "..." menu > **Reset DBADMIN Password**, set a temporary one; the first sign-in forces a change.
   The account owner does this and keeps the password. It is never written into a file or a chat.
5. Trial instances stop every night. Start the instance before each working session.
   SQL endpoint: HANA Cloud Central > Copy SQL Endpoint. The host ends in `hana.prod-ap21.hanacloud.ondemand.com`
   (yes, `prod`, even on trial), port 443.

## 2. Log in

```bash
cf login --sso -a https://api.cf.ap21.hana.ondemand.com
cf target -o cab3acb2trial -s Dev
```

## 3. Build and deploy

```bash
cd apps/northwind-service
npm ci
mbt build                                   # writes mta_archives/northwind-service_0.1.0.mtar
cf deploy mta_archives/northwind-service_0.1.0.mtar
```

This creates: the XSUAA instance `northwind-service-auth`, the HDI container `northwind-service-db`
(tables, views and the Northwind rows with shifted dates), and the app `northwind-service-srv` (256 MB).

## 4. Check

```bash
cf apps                                     # northwind-service-srv should be 'started'
cf logs northwind-service-srv --recent
```

Opening the app address in a browser must answer **401 Unauthorized**. That is correct: in production the
mocked users are gone and only a valid XSUAA token is accepted.

## 5. Roles (BTP cockpit, once) — DONE 2026-09-18

- `SalesHQ (northwind-service cab3acb2trial-dev)` is the role collection the deployment generated. It is
  assigned to the account user, so the user currently plays Nancy (head office, all 830 orders).
- Role `SalesRegion_UK` was created from the template `SalesRegion` with attribute `country` = static `UK`,
  and put into the role collection `Northwind SalesRegion UK`. That collection is NOT assigned yet.
  (Cockpit note: the attribute value box needs a real Enter key press to turn the text into a token;
  the Next button stays disabled until it does.)
- A trial account has one real user. To play Steven, remove `SalesHQ` from the user, assign
  `Northwind SalesRegion UK`, sign out and in again (the token must be re-issued), and compare: 224 orders,
  and order 11070 answers 404. Swap back the same way. Never leave both assigned during a demo:
  CAP unions the grants, so SalesHQ would win and the row rule would look broken.
- The service itself has no browser sign-in (no App Router yet), so the role test happens through the
  first client that carries an XSUAA token: the MCP server's sign-in layer, or a small App Router.

## Memory budget on trial (4 GB in total)

| App | Memory |
|---|---|
| northwind-service-srv | 256 MB |
| northwind-service-db-deployer (runs once, then stops) | 256 MB |
| MCP server, later | 256 MB |
| App Router and agent, later (Stage B) | about 768 MB |
