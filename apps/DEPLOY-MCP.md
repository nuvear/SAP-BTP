# Deploying the MCP server with XSUAA sign-in (Option A: Claude signs in to BTP)

Target: org `cab3acb2trial`, space `dev`, region `ap21`. The data service (`DEPLOY.md`) must already be deployed
and `POLICY_READER` must exist on `northwind-hana` (`hana/create_policy_reader.sql`).

What gets deployed: one Python app, `northwind-mcp`, serving all three tools on `/mcp`, bound to the SAME XSUAA
instance as the data service (`northwind-service-auth`). One sign-in therefore covers both: the MCP server
verifies the user's token (`mcp-servers/xsuaa.py`), then forwards that token to the data service, which applies
the row rule. The MCP server never sees a password and never decides which orders a user may read.

How Claude signs in: Claude's custom connector asks the server where tokens come from
(`/.well-known/oauth-protected-resource`), reads the authorization-server metadata the server publishes
(`/.well-known/oauth-authorization-server`, which points at XSUAA's `/oauth/authorize` and `/oauth/token`),
sends the user to the XSUAA sign-in page, and exchanges the code for a token with the client id and secret
that you enter in Claude's connector settings. XSUAA has no dynamic client registration, which is why the
client id and secret are entered by hand.

Time box: this design is tried ONCE. If step 7 fails with an error from Claude's side that the notes below do not
explain, stop and switch to Option C (App Router first, `STATUS.md`). Do not debug Claude's OAuth client.

## 1. Allow Claude's callback in XSUAA (once)

`northwind-service/mta.yaml` now lists the redirect URIs Claude uses (and a wildcard for this CF domain, for the
App Router later). Apply it by redeploying the data service; the deployer re-runs harmlessly.

```bash
cd apps/northwind-service
npm ci && mbt build
cf deploy mta_archives/northwind-service_0.1.0.mtar
```

Check: `cf service northwind-service-auth` shows "update succeeded".

## 2. Give the MCP server its database credentials (once)

A user-provided service carries the `POLICY_READER` credentials. `cf cups` asks for each value interactively,
so the password is typed, not pasted into a file or a shell history line.

```bash
cf cups policy-db -p "host, port, user, password, schema"
# host:     <id>.hana.prod-ap21.hanacloud.ondemand.com   (HANA Cloud Central > Copy SQL Endpoint, without :443)
# port:     443
# user:     POLICY_READER
# password: <the POLICY_READER password>
# schema:   DBADMIN
```

## 3. Deploy

```bash
cd apps/mcp-servers
cf push
```

The manifest binds `northwind-service-auth` and `policy-db`, sets `MCP_PUBLIC_URL` to the app's route, points
`NORTHWIND_SERVICE_URL` at the data service, and sets `POLICY_STORE=hana`. There is no `DEV_MODE` in it, on purpose.

## 4. Check the server before touching Claude

```bash
BASE=https://northwind-mcp-cab3acb2trial.cfapps.ap21.hana.ondemand.com
curl -s $BASE/health                                              # {"status":"ok","signed_in_required":true}
curl -s $BASE/.well-known/oauth-protected-resource/mcp            # "authorization_servers":["$BASE/"]
curl -s $BASE/.well-known/oauth-authorization-server              # XSUAA authorize/token endpoints
curl -s -i -X POST $BASE/mcp -H 'content-type: application/json' -d '{}' | head -5   # 401 + WWW-Authenticate
```

The 401 is the point: without a token, nothing. `cf logs northwind-mcp --recent` shows the start-up.

## 5. Get the client id and secret for Claude

```bash
cf create-service-key northwind-service-auth claude-connector
cf service-key northwind-service-auth claude-connector
```

The second command prints JSON. You need two values: `clientid` and `clientsecret`. Copy them into your
password manager. They are entered ONLY into Claude's connector settings; never into a file in the repo or a chat.
(Delete the key later with `cf delete-service-key northwind-service-auth claude-connector` if the connector is retired.)

## 6. Add the connector in Claude

Claude (web or desktop) > Settings > Connectors > **Add custom connector**:

- Name: `Northwind Advisor`
- Remote MCP server URL: `https://northwind-mcp-cab3acb2trial.cfapps.ap21.hana.ondemand.com/mcp`
- Advanced settings: OAuth Client ID = `clientid`, OAuth Client Secret = `clientsecret` from step 5
- Add, then **Connect**. A browser window opens the SAP sign-in page (the XSUAA tenant of your trial
  subaccount); sign in with your BTP user. Claude returns with the connector marked connected.

## 7. Test as Nancy, then as Steven

Your user currently holds `SalesHQ`, so Claude acts as Nancy:

1. "What is the status of order 11019, and can it be expedited?" → `get_order_status` then `search_policies`;
   expect the expedite conditions cited as `NW-POL-002 v1.0, 4. When an order may be expedited`.
2. "How much discount can I give on my own authority?" → cited from `NW-POL-001 v2.0` (10 percent), never 5 percent.
3. "How far are we prepared to go on the QUICK-Stop contract?" → no London memo; the answer says the information
   is not available to you.

Then swap the role (DEPLOY.md step 5): remove `SalesHQ`, assign `Northwind SalesRegion UK`, sign out of Claude's
connector and reconnect (a new token is needed), and repeat: order 11019 (a US order) answers "no order with this
number is visible to you", and question 3 now cites `NW-MEM-001 v1.0, 2. QUICK-Stop contract renewal`.

## Known limits and what to watch

- Claude discovers the authorization server from the metadata this server publishes; if Claude insists on
  dynamic client registration despite the entered client id, that is the time-box exit (Option C).
- XSUAA tokens last 12 hours (`token-validity` in mta.yaml); Claude refreshes them with the refresh token.
- The trial HANA instance stops nightly. If `search_policies` returns a connection error, start the instance.
- `LAB_TODAY` is fixed to 2026-05-07 so the sample data stays "current" for the course.
