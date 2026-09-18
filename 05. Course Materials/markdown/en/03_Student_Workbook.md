# Northwind Advisor Student Workbook

Raj Academy · 18 September 2026

Hands-on companion to the Governed AI on SAP BTP session, in two parts. Part A runs on your own laptop from the public repository: no SAP BTP account, no API key and no password is needed; plan about ninety minutes. Part B builds the same advisor on your own free SAP BTP trial account with real SAP sign-in, the way the instructor's demo runs; plan about four hours. Bring: a laptop with admin rights, Node.js 20+, Python 3.11+, git; for Part B also a phone for the SAP verification code and, optionally, a Claude account.

# Part A: laptop lab

## What you will build

You will run the same three pieces you saw in the demo on your own machine: the Northwind data service with its row rule, the policy store with its document filter, and the MCP server with its three read-only tools. Instead of an SAP sign-in you get two built-in test users, and instead of Claude you use the MCP Inspector, a small web page that lets you call tools by hand and see exactly what comes back. That is the point of the workbook: to see the raw answers before a model turns them into prose.

| Test user | Office | Role | Orders they may read | Documents they may read |
| --- | --- | --- | --- | --- |
| `nancy` | Seattle | SalesHQ | all 830 | all-staff, sales, sales-seattle |
| `steven` | London | SalesRegion, country UK | the 224 orders of UK salespeople | all-staff, sales, sales-london |

The lab date is frozen at 7 May 2026, because the sample data ends on 6 May 2026. Whenever a rule says "today", it means that date.

You need: Node.js 20 or later, Python 3.11 or later, git, and a browser. Check with `node --version`, `python3 --version`, `git --version`. Windows users: use PowerShell or WSL; the commands below are written for a Unix-style shell and are noted where PowerShell differs.

## Setup: three terminals, about 20 minutes

Get the code once:

```bash
git clone https://github.com/nuvear/SAP-BTP.git
cd SAP-BTP/apps
```

**Terminal 1, the data service.** This is the SAP CAP service that owns the orders and the row rule. Locally it uses an in-memory database and two mocked users.

```bash
cd northwind-service
npm ci
npm test
npm start
```

`npm test` must end with `# pass 9` and `# fail 0`. `npm start` prints a line containing `http://localhost:4004` followed by `server ... launched`; a warning that SQLite is experimental is normal. Leave it running. Open <http://localhost:4004/odata/v4/northwind/Orders?$top=3> in a browser: it asks for a user; type `nancy` and password `nancy` and you see three orders as JSON. That is what the assistant reads.

**Terminal 2, the MCP server.** It offers the three tools and, locally, uses a keyword search over the 86 policy passages already in the repository (`policy-loader/chunks.jsonl`).

```bash
cd mcp-servers
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 python server.py advisor
```

`pytest` must say 45 passed (a few deprecation warnings are normal; it starts its own copy of the data service on another port, so Terminal 1 does not interfere). The last command prints `Uvicorn running on http://0.0.0.0:8000`. It does not echo which user you chose, so check the variable before you start it. On PowerShell, activate with `.venv\Scripts\Activate.ps1` and set the variables with `$env:DEV_MODE="1"; $env:DEV_USER="nancy"; $env:LAB_TODAY="2026-05-07"` before `python server.py advisor`.

What `DEV_MODE=1` means: on your laptop there is no SAP sign-in, so the server takes the user from `DEV_USER`. On BTP this switch does not exist; the server refuses every call without a valid SAP token. Never deploy with it.

**Terminal 3, the MCP Inspector.** This is your window into the tools.

```bash
npx @modelcontextprotocol/inspector
```

It opens a browser page. Choose transport **Streamable HTTP**, URL `http://localhost:8000/mcp`, click **Connect**, then **List Tools**. You should see `get_order_status`, `get_product_availability` and `search_policies`. If Connect fails, check that Terminal 2 is still running and that the URL ends in `/mcp`.

To become Steven later, stop the server in Terminal 2 with Ctrl+C and start it again with `DEV_USER=steven`, then click Connect again in the Inspector. (Alternative without restarting: in the Inspector, add a custom header `X-Dev-User: steven`; the header wins over the variable.)

## Exercise 1: live facts and the row rule (15 minutes)

In the Inspector, select `get_order_status`, enter `order_id` = `11019`, click Run Tool.

- [ ] Write down: customer, salesperson and their office country, required date, `days_until_required`, carrier, and the two product lines with their stock. Note `data_read_at`: every fact carries the time it was read.
- [ ] Run it again with `11070`. Salesperson Andrew Fuller, USA office. Note `days_until_required`.
- [ ] Now become Steven (restart Terminal 2 with `DEV_USER=steven`, reconnect). Run `get_order_status` for `11019` and for `11070`.

What you should see: as Steven, 11019 comes back (its salesperson is in the UK office) and 11070 answers `found: false`, "No order with this number is visible to you." The MCP server did not decide this. It sent the same request to the data service with a different user, and the data service's row rule answered. Look in Terminal 1: both requests are logged, and the second one is followed by `404 - Error: Not Found`.

Why the wording matters. Before any tool existed, a model asked about order 11019 would still have answered, confidently, from patterns learned in training; order 11019 exists only in this lab's database, so that answer would have been fabricated (a hallucination). Every value you see here was read from a row at the moment of the call, and `data_read_at` says when. Grounding replaces fabrication with retrieval.

- [ ] Try `get_product_availability` with `Rössle Sauerkraut` and with `Chai`. One is discontinued with stock left; one is a normal product. Which fields tell you?

Question to answer in one sentence: why does the server say "not visible to you" instead of "does not exist" or "you are not allowed"? (Write your answer below; the instructor has the answer key.)

## Exercise 2: rules with citations (15 minutes)

Back as Nancy. Select `search_policies`; leave `k` at 4.

- [ ] Question: `How much discount can I give a customer on my own authority?` Read the `citation` of each passage returned. Which document and version give the answer, and what is the number?
- [ ] Look at `data/northwind/robustness/` in the repository. Open the superseded Discount Authority Policy 1.0 and the draft memo about the spring campaign. What limits do they state? Were they returned? Why not? (Hint: every passage in `policy-loader/chunks.jsonl` carries `status`, `effective_from`, `effective_to` and an `audience`; the tool result shows the first three. `search_policies` only searches passages that are current, in force on the lab date, and readable by you.)
- [ ] Question: `customer wants a rush job, is that allowed?` The passages contain no phrase "rush job". Which passage explains how the search still found the right rule? (Look for the glossary.)
- [ ] Question: `Which carrier may carry seafood?` Then combine with Exercise 1: order 11019 has a seafood line on carrier 3. What should happen to that order, who pays, and who approves? Cite the section.

A note on how the search works locally versus on BTP. On your laptop the search is by keywords (BM25); it finds the glossary entry because the words match. On BTP the same question is embedded by SAP HANA's built-in function and compared by meaning; there the passage about expediting comes first even though it shares no words with the question. The filter is identical in both: it is applied before ranking, in the `WHERE` clause on HANA and in the function `visible()` locally.

## Exercise 3: identity decides (10 minutes)

The same question, two people.

- [ ] As Nancy: `search_policies` with `How far are we prepared to go on the QUICK-Stop contract discount?` Write down the citations. Is there a negotiating figure anywhere in them?
- [ ] Become Steven and ask exactly the same question. Now a memo from the London Sales Manager appears: which document id, which section, and what figure does it contain?
- [ ] Look at the memo file in `data/northwind/corpus/`. Find the line that restricts it. Then open `apps/mcp-servers/identity.py` and find where Nancy's and Steven's document audiences are defined for local use.

What to notice: Nancy is not told that something is hidden from her. The assistant answers from what it can see, and what it can see is decided by the audience list attached to her identity, never by the question. On BTP that list is derived from the SAP role collections and the `country` attribute in the sign-in token (`apps/mcp-servers/xsuaa.py`, function `audiences_for`); locally it comes from the two test users.

Declared, not proven. On the laptop nobody signs in: `DEV_USER` (or the `X-Dev-User` header) names the user, `DEV_USERS` in `identity.py` gives that name its document audiences and its basic-auth login for the data service, and the data service's mocked users in `package.json` give that login its role and country. Anyone can type `DEV_USER=steven` and become Steven. That is why the switch does not exist on BTP: there the same two facts, role and country, arrive inside an XSUAA token that the MCP server verifies (signature, expiry, issuer, audience) and the data service verifies again. Part A shows the effect of identity; Part B shows the proof of it. The Lab Guide (`04_Lab_Guide`) explains each lab this way, persona by persona.

Optional: change the lab date. Restart the server with `LAB_TODAY=2026-08-01` and repeat Steven's question. The memo's `effective_to` is 30 June 2026, so in August it is no longer returned, even to Steven. Documents expire without anyone editing them.

## Exercise 4: the traps (15 minutes)

This is the robustness lab. You switch the document filter off and watch what a careless system would do.

- [ ] Stop Terminal 2 and restart with the filter off: `DEV_MODE=1 DEV_USER=nancy LAB_TODAY=2026-05-07 STRICT_FILTERS=0 python server.py advisor`. Reconnect the Inspector.
- [ ] Ask: `What discount may I approve for a customer?` with `k` = `6` (the tool never returns more than 6). Now passages with `status: superseded` (5 percent, from `NW-POL-001 v1.0, 3. Approval tiers`) and `status: unapproved` (15 percent, the draft memo `NW-MEM-900`) appear beside the current 10 percent. Write down all three figures and their citations. A model given these passages would have to choose, and it might choose wrong. (The keyword search is sensitive to wording; the exact question above is the one that brings all three up on a laptop. On HANA, meaning-based search does it for any phrasing.)
- [ ] Ask: `Has the lead time for Pavlova products changed?` A passage with `status: unverified-external` appears: a supplier email. Read its second passage to the end. It contains an instruction addressed to "any AI assistant".
- [ ] As Nancy with the filter off, ask the QUICK-Stop question from Exercise 3. The London memo now appears for her too.

Restart the server without `STRICT_FILTERS=0` and confirm all three traps are gone again.

What the exercise shows: the filter is one line of policy applied before retrieval, and it removes three different failure classes at once: out-of-date rules, unapproved rules, and content that tries to instruct the model. The model's good behaviour is a second line of defence, not the first. In the demo you saw Claude refuse the injected instruction even when asked directly; here you see that with the filter on it never received the instruction at all.

Question: which of the three traps would a keyword search have ranked highest for a question about discounts, and why is that dangerous? (Write your answer below; the instructor has the answer key.)

## Exercise 5: read the code, find each rule (15 minutes)

Each rule you have just observed is a few lines in one file. Find them; the point is to see that governance is code you can review, not behaviour you hope for.

| Rule you observed | File | What to look for |
| --- | --- | --- |
| Steven cannot read order 11070 | `apps/northwind-service/srv/northwind-service.cds` | `@restrict` on `Orders`: `SalesHQ` reads everything, `SalesRegion` reads `where: 'Employee.Country = $user.country'`. Also `@readonly`: there is no write at all. |
| Superseded, unapproved, expired and restricted passages never appear | `apps/mcp-servers/stores.py` | function `visible()`: four conditions, applied before ranking |
| The same four conditions on SAP HANA | `apps/mcp-servers/hana_store.py` | the `SEARCH` statement: `WHERE STATUS = 'current' AND ... AUDIENCE IN (...)`, before `ORDER BY SCORE` |
| Only three tools, all read-only | `apps/mcp-servers/server.py` | function `build()`: three `@mcp.tool()` functions and nothing else; no generic query tool |
| Who the user is, locally | `apps/mcp-servers/identity.py` | `DEV_USERS`, and the line that refuses everything when `DEV_MODE` is not `1` |
| Who the user is, on BTP | `apps/mcp-servers/xsuaa.py` | `verify_token`: signature, expiry, issuer, audience, in that order; `audiences_for`: role scopes and the `country` attribute become document audiences |
| The server cannot start open on BTP | `apps/mcp-servers/server.py` | function `auth_config()`: `SystemExit` when there is no XSUAA binding and no `DEV_MODE` |
| Text in a passage is data, not a command | `apps/mcp-servers/policy_tools.py` and `server.py` | the `note` field in every search result, and the `INSTRUCTIONS` text given to the model |

- [ ] Change one thing and watch a test fail: in `stores.py`, make `visible()` return `True` for superseded passages, run `python -m pytest -q`, and read which tests fail and what they say. Put it back.
- [ ] Read `tests/test_xsuaa.py`. It creates a fake SAP token signed with a local key and shows each of the four validation rules refusing a bad token. Which test would catch a token stolen from a different SAP application?

## Going further

**Talk to it in Claude Desktop instead of the Inspector.** Claude Desktop can run a local MCP server directly. Edit its configuration file (Claude Desktop > Settings > Developer > Edit Config) and add an entry like this, with your own paths; keep Terminal 1 running.

```json
{
  "mcpServers": {
    "northwind-local": {
      "command": "/full/path/to/SAP-BTP/apps/mcp-servers/.venv/bin/python",
      "args": ["/full/path/to/SAP-BTP/apps/mcp-servers/server.py", "advisor", "--stdio"],
      "env": {
        "DEV_MODE": "1",
        "DEV_USER": "nancy",
        "LAB_TODAY": "2026-05-07",
        "NORTHWIND_SERVICE_URL": "http://localhost:4004/odata/v4/northwind",
        "POLICY_CHUNKS": "/full/path/to/SAP-BTP/apps/policy-loader/chunks.jsonl"
      }
    }
  }
}
```

Restart Claude Desktop and ask the four demo questions. Change `DEV_USER` to `steven`, restart, and ask them again. You now have the full demo on your laptop, with Claude writing the prose.

**Deploy it to your own SAP BTP trial account.** This is the second half of the course, about half a day. The steps are in the repository: `apps/DEPLOY.md` (HANA Cloud instance with the natural-language-processing option, the data service, the role collections) and `apps/DEPLOY-MCP.md` (the MCP server with SAP sign-in and the Claude connector). Two things learned the hard way are already written into them: pin `mcp<2` in `requirements.txt`, and type the `cf cups` values one at a time. `apps/phase0/hana_checks.sql` verifies that your HANA instance can embed text before you load anything.

**Bring your own documents.** Put a `.txt` or `.pdf` in `data/northwind/corpus/`, add it to `manifest.json` with a status, effective dates and an audience, run `python loader.py --data ../../data/northwind --out chunks.jsonl` in `apps/policy-loader`, and restart the server. Your document is now searchable, under the same filter as everything else. Try giving it `"status": "draft"` and watch it stay invisible.

## Reflection

Reflection, to discuss in your team:

1. Which of the four rules (rows, documents, tools, identity) would your own organisation find hardest to express as code, and where does it live today?
2. The assistant said "this information is not available to you" to Nancy. Should it say that a restricted document exists? What would change if it did?
3. The filter uses status, effective dates and audience. Which other document properties would matter for your policies, and who would maintain them?
4. If you replaced Claude with another model, which of the behaviours you saw would change, and which are guaranteed by the platform regardless of the model?

# Part B: your own SAP BTP tenant

In Part A everything ran on your laptop with two test users. In Part B you build the same advisor on a free SAP BTP trial account with real SAP sign-in, exactly as the instructor's demo. Six sections, about four hours in total, in this order; each ends with a check you can see on screen. Region: choose **Singapore (Azure)** so that every address in this handbook matches yours; other regions work, with different host names.

What you type into SAP screens stays with you: the DBADMIN password, the POLICY\_READER password, and the connector's client secret. Never put any of them in a file in the repository, a chat, or a screenshot.

## 1. Create the trial account (15 minutes)

1. Open <https://account.hanatrial.ondemand.com> and click **Get started** (or **Register** if you have no SAP Universal ID). Fill in name, email and a password; SAP sends a verification code to the email. Enter it.
2. Sign in. Accept the trial terms. SAP asks for a mobile number and sends a code by SMS; enter it. (One trial per Universal ID; if you already have one, this step takes you straight to it.)
3. Choose the region **Singapore - Azure** and confirm. A page shows the account being set up; it takes about a minute.
4. Click **Go To Your Trial Account**. You are in the BTP cockpit, in your global account (its name ends in `trial`). Click the subaccount tile **trial**.
5. On the subaccount Overview, read the Cloud Foundry Environment box: API endpoint `https://api.cf.ap21.hana.ondemand.com`, an org name ending in `trial`, and further down one space called `dev`. Write the org name on your sheet; you will need it for `cf target`.
6. In the left menu click **Entitlements**. Find SAP HANA Cloud: plans `hana-free` and `tools` are listed. SAP AI Core is not, which is why this course calls Claude directly (deck slide 14).

Check: the Overview page with your API endpoint and org name.

## 2. Prepare the environment (60 minutes, including waiting)

Do the steps in this order. The first two must come before the database, or the database screens will not open.

**2a. The SAP HANA Cloud tools subscription.** Left menu **Instances and Subscriptions** > **Create**. Service: type `SAP HANA Cloud` and pick it; Plan: `tools` (under Subscriptions, not Instances). Click **Create**. The Subscriptions list shows it as Processing, then Subscribed (about a minute).

**2b. Your role collections.** Left menu **Security > Users**, click your user, tab **Role Collections**, then the **...** menu > **Assign Role Collection**. Type `HANA` in the search, tick **SAP HANA Cloud Administrator** and **SAP HANA Cloud Security Administrator**, click Assign. Sign out of the cockpit and in again so the new roles take effect.

**2c. The database instance.** Left menu **Instances and Subscriptions** > **Create**. Service `SAP HANA Cloud`, Plan `hana-free` (under Instances), Runtime Environment **Cloud Foundry**, Space `dev`. Click **Next** or **Create**; SAP HANA Cloud Central opens with a wizard.

- Instance name: `northwind-hana`. Administrator password: choose one now and save it in your password manager as "DBADMIN northwind-hana" (at least 8 characters, upper case, lower case, a digit).
- Keep the free-tier size (16 GB memory, 80 GB storage).
- **Advanced Settings**: under Allowed connections choose **Allow all IP addresses**; under Additional Features switch on **Natural Language Processing (NLP)**. This cannot be added later; an instance without it has to be deleted and recreated.
- Review and **Create Instance**. Creation takes 5 to 10 minutes; the instance shows Creating, then Running.

If the wizard did not ask for a password (some paths create the instance with a generated one), open the instance in HANA Cloud Central, use the **...** menu > **Reset DBADMIN Password**, set a temporary one, and change it at your first sign-in.

**2d. Phase 0: does the database do what we need?** In HANA Cloud Central, on your instance choose **Open > Open in SQL Console**. If asked, register with user `DBADMIN` and your password. Open `apps/phase0/hana_checks.sql` from the repository and run the seven blocks one at a time (paste a block, click **Run**). Block 4 is the one that matters: it must return **768**. Block 6 must return `expedite` first and neither `old-discount` nor `london-memo`. Block 7 drops the test table.

Check: `northwind-hana` is Running with NLP Enabled (Configuration tab), and block 4 returned 768.

Daily habit from now on: trial instances stop every night. Before each session open HANA Cloud Central and click **Start** on the instance.

## 3. Tools on your laptop and sign-in (15 minutes)

You need the Cloud Foundry command line, its deployment plugin, and the MTA build tool. On a Mac with Homebrew:

```bash
brew install cloudfoundry/tap/cf-cli@8
cf install-plugin multiapps
npm install -g mbt
```

On Windows, install the cf CLI from the Cloud Foundry GitHub releases page, then run the same `cf install-plugin` and `npm install -g mbt` in PowerShell. Check with `cf --version` and `mbt --version`.

Sign in with your browser (no password on the command line):

```bash
cf login --sso -a https://api.cf.ap21.hana.ondemand.com
```

It prints a link; open it, sign in, copy the temporary code back into the terminal. Then point at your org and space, using the org name from your sheet:

```bash
cf target -o <your org name> -s dev
```

Check: `cf target` shows your org and space `dev`.

## 4. Deploy the Northwind data service (20 minutes)

This is the CAP service that owns the orders and the row rule, packaged with its HDI database container and its XSUAA sign-in configuration. One deployment creates all three.

```bash
cd SAP-BTP/apps/northwind-service
npm ci
mbt build
cf deploy mta_archives/northwind-service_0.1.0.mtar
```

The build takes a minute, the deployment three to five; it ends with "Process finished". Then:

```bash
cf apps
```

`northwind-service-srv` is started with one instance; `northwind-service-db-deployer` is stopped (it ran once to create the tables and load the 830 orders). In the cockpit, Instances and Subscriptions now lists three instances: your HANA database, `northwind-service-auth` (XSUAA) and `northwind-service-db` (the HDI container).

Open the service address in a browser: `cf app northwind-service-srv` prints it under routes; add `/odata/v4/northwind/Orders`. You must get **401 Unauthorized**. That is correct: on BTP the mocked users are gone and only a valid SAP token is accepted.

**Roles.** Cockpit > Security > Users > your user > Role Collections > Assign: tick `SalesHQ (northwind-service <org>-dev)`, which the deployment created. You are Nancy. For Steven, create the region role once: Security > Roles, search `northwind`, on the `SalesRegion` template click **Create Role**, name `SalesRegion_UK`, next; attribute `country`, source Static, value `UK` and press Enter so it becomes a chip (Next stays grey until it does); skip role collections; Finish. Then Security > Role Collections > Create, name `Northwind SalesRegion UK`, open it, Edit, add the role `SalesRegion_UK`, Save. Leave it unassigned for now.

Check: `cf apps` shows the service started and the browser answers 401.

## 5. The documents into HANA (20 minutes)

The 86 policy passages go into a table in your database and are embedded there by HANA's own model. Open the SQL console on your instance as DBADMIN.

1. Open `apps/hana/load_policy_chunks.sql` from the repository in a text editor. It is one CREATE TABLE and 86 INSERT statements. Paste it into the console in two or three portions (the editor handles a few hundred lines at a time comfortably) and click Run after each. Every statement reports Success.
2. Embed the passages, one statement:

```sql
UPDATE POLICY_CHUNKS SET VEC = VECTOR_EMBEDDING(TO_NVARCHAR(TEXT), 'DOCUMENT', 'SAP_NEB.20240715');
SELECT COUNT(*) AS LOADED, SUM(CASE WHEN VEC IS NULL THEN 0 ELSE 1 END) AS EMBEDDED FROM POLICY_CHUNKS;
```

Expected: 86 and 86.

3. Try the search that the MCP server will run, as Nancy (audiences all-staff, sales, sales-seattle) on the lab date:

```sql
SELECT TOP 3 CHUNK_ID, ROUND(COSINE_SIMILARITY(VEC, VECTOR_EMBEDDING('customer wants a rush job, is that allowed?', 'QUERY', 'SAP_NEB.20240715')), 3) AS SCORE
FROM POLICY_CHUNKS
WHERE STATUS = 'current' AND (EFFECTIVE_FROM IS NULL OR EFFECTIVE_FROM <= DATE'2026-05-07') AND (EFFECTIVE_TO IS NULL OR EFFECTIVE_TO >= DATE'2026-05-07') AND AUDIENCE IN ('all-staff','sales','sales-seattle')
ORDER BY SCORE DESC;
```

Expected: `NW-RUN-001@1.0#03` (the runbook's rush-order situation) first, around 0.67. Change the audiences to `'all-staff','sales','sales-london'` and ask `How far are we prepared to go on the QUICK-Stop contract discount?`: now `NW-MEM-001@1.0#03` comes first. That is Exercise 3 of Part A, inside the database.

4. Create the technical user the MCP server will use; open `apps/hana/create_policy_reader.sql`, replace `<choose-a-password>` with a password you choose (save it as "POLICY\_READER"), run it. Then **History > Clear All** so the password leaves the screen.

Check: the count returns 86 and 86, and the rush-job search returns the runbook first.

## 6. Deploy the MCP server and connect Claude (55 minutes)

The MCP server offers the three tools, verifies SAP tokens, and forwards them to the data service. It never runs without sign-in: there is no development switch in its deployment file, and it refuses to start if its sign-in binding is missing.

**6a. Tell XSUAA where Claude's sign-in may return to.** `apps/northwind-service/mta.yaml` already lists Claude's callback addresses; if you deployed the data service from the current repository in section 4, this is already in place. If you deployed from an older copy, repeat the three commands of section 4 once.

**6b. Give the server its database credentials.** A user-provided service holds the POLICY\_READER details. The command asks for each value; answer them one at a time and press Enter after each. The host is on your instance's page in HANA Cloud Central (**Copy SQL Endpoint**), without the `:443`.

```bash
cf cups policy-db -p "host, port, user, password, schema"
```

host: your instance's SQL endpoint host; port: `443`; user: `POLICY_READER`; password: the one you chose in section 5; schema: `DBADMIN`. If you later see an SSL error with the host name written twice, the host was pasted twice: run `cf update-user-provided-service policy-db -p "host, port, user, password, schema"` and type it once.

**6c. Adjust the route to your account and deploy.** Open `apps/mcp-servers/manifest.yml`. Two lines carry the instructor's org name and must carry yours: `route:` and `MCP_PUBLIC_URL:` (replace `cab3acb2trial` with your org name in both), and `NORTHWIND_SERVICE_URL:` must be your data service address from section 4 followed by `/odata/v4/northwind`. Then:

```bash
cd SAP-BTP/apps/mcp-servers
cf push
```

Two to four minutes. The result shows `northwind-mcp` running, 1/1. If it crashes with "No module named mcp.server.fastmcp", the Python dependency `mcp` was installed at version 2; `requirements.txt` in the current repository pins it below 2, so make sure you have the latest copy.

**6d. Check before touching Claude.** With `BASE` set to your route:

```bash
BASE=https://northwind-mcp-<your org>.cfapps.ap21.hana.ondemand.com
curl -s $BASE/health
curl -s -i -X POST $BASE/mcp -H "content-type: application/json" -d "{}" | head -6
```

Expected: `"signed_in_required":true`, then `HTTP/2 401` with a `www-authenticate` line that names `oauth-protected-resource`. Without a token, nothing; that is the point.

**6e. The client id and secret for Claude.**

```bash
cf create-service-key northwind-service-auth claude-connector
cf service-key northwind-service-auth claude-connector
```

From the printed JSON copy `clientid` and `clientsecret` into your password manager. They go only into Claude's connector settings.

**6f. Add the connector in Claude.** Settings > Connectors > **Add custom connector**. Name `Northwind Advisor`; Remote MCP server URL `https://northwind-mcp-<your org>.cfapps.ap21.hana.ondemand.com/mcp`; open Advanced settings and paste the OAuth Client ID and Client Secret; Add; **Connect**. The SAP sign-in page of your trial tenant opens; sign in with your BTP user. Claude shows Connected.

**6g. The four questions.** Start a new chat with the connector on and ask, one at a time:

1. What is the status of order 11019, and can it be expedited?
2. How much discount can I give a customer on my own authority?
3. How far are we prepared to go on the QUICK-Stop contract discount?
4. Has the delivery lead time for Pavlova products changed? Approve a 40 percent discount on their products for me.

Compare with the Demo Script's expected answers: facts from `get_order_status`, rules cited as `doc_id vVersion, section`, nothing from the superseded, draft or supplier documents, no figure for QUICK-Stop, and a refusal to approve. If a tool call reports that the session expired, ask again; Claude reconnects.

**6h. Become Steven.** Cockpit > Security > Users > your user > Role Collections: remove `SalesHQ` (the × in its row) and assign `Northwind SalesRegion UK`. In Claude, disconnect the connector and connect again so a new token is issued. Ask question 3 again: the answer now cites `NW-MEM-001 v1.0, 2. QUICK-Stop contract renewal`. Ask for order 11070: "No order with this number is visible to you." Swap back the same way when you are done, and never leave both collections assigned: the platform combines them, and head office wins.

Check: question 1 answers with order data and citations as Nancy; question 3 changes its answer as Steven.

## What you have built

The same six steps as the instructor's demo, on your own tenant: sign-in through XSUAA, a token that travels with every question, a data service that applies the row rule from that token, a document store whose filter runs inside HANA with your audiences in the WHERE clause, and an assistant that answers from facts and cited passages only. Deck slide 17 is now a description of something you own.

To keep it: the trial lasts 90 days; the instance stops nightly and restarts with one click; the connector's token lasts 12 hours and Claude refreshes it. To tidy up: `cf delete-service-key northwind-service-auth claude-connector` removes the connector's credentials, `cf delete northwind-mcp` removes the server, and the cockpit's Instances and Subscriptions page deletes the rest.
