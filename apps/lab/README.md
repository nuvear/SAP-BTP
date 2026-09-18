# lab: the conductor

One script walks the whole Northwind Advisor scenario and keeps the evidence. It is the student handbook,
executed: every exercise in Part A is a step the conductor runs and checks, every cockpit or password step
in Part B is a step it explains, waits for, and then verifies from the outside.

```bash
cd apps
python3 lab/conductor.py --part A --yes       # laptop lab, fully automatic, about 10 minutes the first time
python3 lab/conductor.py --part B             # your own BTP tenant: you click, it checks
python3 lab/conductor.py --start B11          # resume at a step
python3 lab/conductor.py --rehearse           # replay the recorded evidence, run nothing
python3 lab/conductor.py --only A9            # one step, e.g. the robustness lab
python3 lab/conductor.py --part A --pace      # live session: real run, waits for Enter after every step
```

Three kinds of step. `auto`: the conductor runs it (npm, pytest, starts both servers, calls the three tools
through a real MCP client, restarts the server as Steven, with the filter off, on another lab date) and checks
the result against the expected facts and citations. `manual`: you do it (trial account, HANA Cloud Central,
`cf cups`, `cf push`, Claude's connector); it prints exactly what to do and waits for Enter. `probe`: it checks
what you did from the outside: `cf app`, `cf service`, the public `/health` and OAuth metadata, the 401 without
a token, the 401 with a forged token. No credentials are asked, read or written; the cf CLI's own sign-in is used
where it exists, and cf-based checks are skipped on a machine without it.

Output: `lab_journal.md` (a table of every step with its evidence) and `lab_journal.json`. A rehearsal replays
your own journal, or `rehearsal.json` (the recording shipped with the course) when you have none: useful for a
dry run of the session with no network. `logs/` holds the output of both servers.

`mcp_call.py` is the helper the conductor uses to talk to the local MCP server; it runs inside
`mcp-servers/.venv` and can be used on its own:

```bash
../mcp-servers/.venv/bin/python mcp_call.py list
../mcp-servers/.venv/bin/python mcp_call.py call get_order_status '{"order_id": 11070}' --user steven
```

Part A needs Node 20+, Python 3.11+ and git. Part B additionally needs the cf CLI and mbt, signed in to your
trial org and space (`NW_CF_ORG`, `NW_CF_SPACE`, `NW_MCP_URL`, `NW_CAP_URL` override the course defaults).
