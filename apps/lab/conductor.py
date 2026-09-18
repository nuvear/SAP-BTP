#!/usr/bin/env python3
"""Lab conductor: walks the whole Northwind Advisor scenario, step by step, and keeps the evidence.

    python lab/conductor.py                    interactive, Part A then Part B
    python lab/conductor.py --part A --yes     Part A without questions (laptop lab, fully automatic)
    python lab/conductor.py --part B           Part B: your own BTP tenant (you click, the conductor checks)
    python lab/conductor.py --start A8         resume from a step
    python lab/conductor.py --rehearse         replay the recorded evidence, run nothing (for a dry run of the session)
    python lab/conductor.py --part A --pace    live session: real run, but it waits for Enter after every step

Three kinds of step:
    auto    the conductor runs it (npm, pytest, start servers, call the tools) and checks the result
    manual  you do it (cockpit, passwords, Claude sign-in); the conductor tells you exactly what and waits
    probe   the conductor checks something you did (public endpoints, cf state); no credentials involved

Everything it finds goes to lab/lab_journal.md and lab/lab_journal.json. Passwords are never asked, read or written.
Standard library only.
"""
from __future__ import annotations
import argparse, base64, json, os, shutil, signal, subprocess, sys, time, urllib.request, urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

HERE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.dirname(HERE)
LOGS = os.path.join(HERE, "logs")
JOURNAL_JSON = os.path.join(HERE, "lab_journal.json")
JOURNAL_MD = os.path.join(HERE, "lab_journal.md")
REHEARSAL = os.path.join(HERE, "rehearsal.json")

CAP_URL = "http://localhost:4004/odata/v4/northwind"
MCP_URL = "http://localhost:8000/mcp"
LAB_TODAY = "2026-05-07"
BTP = {
    "mcp": os.environ.get("NW_MCP_URL", "https://northwind-mcp-cab3acb2trial.cfapps.ap21.hana.ondemand.com"),
    "cap": os.environ.get("NW_CAP_URL", "https://cab3acb2trial-dev-northwind-service-srv.cfapps.ap21.hana.ondemand.com/odata/v4/northwind"),
    "org": os.environ.get("NW_CF_ORG", "cab3acb2trial"), "space": os.environ.get("NW_CF_SPACE", "dev"),
}

# ----------------------------------------------------------------------------------------------- small helpers
BOLD, DIM, GREEN, RED, YELLOW, CYAN, END = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[0m"
if not sys.stdout.isatty() or os.name == "nt":
    BOLD = DIM = GREEN = RED = YELLOW = CYAN = END = ""


def say(text: str = "", style: str = "") -> None:
    print(f"{style}{text}{END}" if style else text, flush=True)


class Evidence(list):
    """Lines of (ok, text). A step passes when every line is ok."""
    def check(self, ok: bool, text: str) -> bool:
        self.append((bool(ok), text))
        say(f"   {GREEN + 'PASS' if ok else RED + 'FAIL'}{END}  {text}")
        return bool(ok)

    def note(self, text: str) -> None:
        self.append((True, text))
        say(f"   {DIM}note{END}  {text}")

    @property
    def ok(self) -> bool:
        return all(ok for ok, _ in self)


def run(cmd: list[str], cwd: str, env: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=timeout)


def http_get(url: str, auth: tuple[str, str] | None = None, timeout: int = 10, method: str = "GET", body: bytes | None = None,
             headers: dict | None = None) -> tuple[int, dict, str]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode(errors="replace")
    except Exception as e:                                  # connection refused, DNS, timeout
        return 0, {}, str(e)


def wait_for(url: str, seconds: int, auth=None, accept=(200,)) -> bool:
    for _ in range(seconds * 2):
        status, _, _ = http_get(url, auth=auth, timeout=3)
        if status in accept:
            return True
        time.sleep(0.5)
    return False


def venv_python() -> str:
    d = os.path.join(APPS, "mcp-servers", ".venv")
    return os.path.join(d, "Scripts", "python.exe") if os.name == "nt" else os.path.join(d, "bin", "python")


# ----------------------------------------------------------------------------------------------- the conductor
@dataclass
class Step:
    id: str
    title: str
    kind: str                                   # auto | manual | probe
    fn: Callable[["Conductor", Evidence], None] | None = None
    instructions: str = ""
    minutes: int = 0


@dataclass
class Conductor:
    yes: bool = False
    rehearse: bool = False
    procs: dict = field(default_factory=dict)
    records: list = field(default_factory=list)
    replay: dict = field(default_factory=dict)
    mcp_env: dict = field(default_factory=dict)
    pace: bool = False

    # ---- background servers ------------------------------------------------------------------------------
    def start(self, name: str, cmd: list[str], cwd: str, env: dict, ready_url: str, auth=None, accept=(200,), seconds=60) -> bool:
        self.stop(name)
        os.makedirs(LOGS, exist_ok=True)
        log = open(os.path.join(LOGS, f"{name}.log"), "a")
        log.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)}  env={ {k: v for k, v in env.items()} }\n")
        log.flush()
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        self.procs[name] = subprocess.Popen(cmd, cwd=cwd, env={**os.environ, **env}, stdout=log, stderr=subprocess.STDOUT, **kw)
        return wait_for(ready_url, seconds, auth=auth, accept=accept)

    def stop(self, name: str) -> None:
        p = self.procs.pop(name, None)
        if p and p.poll() is None:
            try:
                os.killpg(p.pid, signal.SIGTERM) if os.name != "nt" else p.terminate()
                p.wait(10)
            except Exception:
                p.kill()

    def stop_all(self) -> None:
        for name in list(self.procs):
            self.stop(name)

    def start_cap(self, ev: Evidence) -> bool:
        ok = self.start("cap", ["npm", "start"], os.path.join(APPS, "northwind-service"), {},
                        CAP_URL + "/Orders?$top=1", auth=("nancy", "nancy"), seconds=90)
        return ev.check(ok, "Terminal 1: data service answers on http://localhost:4004 (user nancy)")

    def start_mcp(self, ev: Evidence, user="nancy", **extra) -> bool:
        env = {"DEV_MODE": "1", "DEV_USER": user, "LAB_TODAY": LAB_TODAY, "NORTHWIND_SERVICE_URL": CAP_URL,
               "POLICY_CHUNKS": os.path.join(APPS, "policy-loader", "chunks.jsonl"), **extra}
        self.mcp_env = env
        ok = self.start("mcp", [venv_python(), "server.py", "advisor"], os.path.join(APPS, "mcp-servers"), env,
                        "http://localhost:8000/health", seconds=40)
        flags = " ".join(f"{k}={v}" for k, v in extra.items())
        return ev.check(ok, f"Terminal 2: MCP server up as DEV_USER={user} {flags}".rstrip())

    # ---- tool calls through the real MCP client ------------------------------------------------------------
    def tool(self, name: str, args: dict, user: str = "nancy") -> dict:
        r = run([venv_python(), os.path.join(HERE, "mcp_call.py"), "call", name, json.dumps(args), "--user", user], HERE, timeout=120)
        if r.returncode != 0:
            return {"error": r.stderr.strip()[-600:]}
        try:
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            return {"error": r.stdout[-600:]}

    def cites(self, question: str, user="nancy", k=4) -> tuple[list[str], list[dict], dict]:
        out = self.tool("search_policies", {"question": question, "k": k}, user)
        passages = out.get("passages", [])
        return [p["citation"] for p in passages], passages, out

    # ---- journal --------------------------------------------------------------------------------------------
    def record(self, step: Step, status: str, ev: Evidence, seconds: float) -> None:
        self.records = [r for r in self.records if r["id"] != step.id]
        self.records.append({"id": step.id, "title": step.title, "kind": step.kind, "status": status,
                             "evidence": [[ok, t] for ok, t in ev], "at": datetime.now().isoformat(timespec="seconds"),
                             "seconds": round(seconds, 1)})
        self.records.sort(key=lambda r: (r["id"][0], int(r["id"][1:])))
        self.write_journal()

    def write_journal(self) -> None:
        with open(JOURNAL_JSON, "w") as f:
            json.dump(self.records, f, indent=1, ensure_ascii=False)
        with open(JOURNAL_MD, "w") as f:
            f.write(f"# Lab journal\n\nUpdated {datetime.now().isoformat(timespec='seconds')}. "
                    f"Steps: {len(self.records)}; passed {sum(r['status'] == 'pass' for r in self.records)}, "
                    f"failed {sum(r['status'] == 'fail' for r in self.records)}.\n\n| Step | Result | Kind | Time |\n|---|---|---|---|\n")
            for r in self.records:
                f.write(f"| {r['id']} {r['title']} | {r['status']} | {r['kind']} | {r['at'][11:]} |\n")
            f.write("\n")
            for r in self.records:
                f.write(f"## {r['id']} {r['title']} ({r['status']})\n\n")
                for ok, t in r["evidence"]:
                    f.write(f"- {'PASS' if ok else 'FAIL'}: {t}\n")
                f.write("\n")

    def load_journal(self) -> None:
        if os.path.exists(JOURNAL_JSON):
            with open(JOURNAL_JSON) as f:
                self.records = json.load(f)

    # ---- running a step -------------------------------------------------------------------------------------
    def pause(self, prompt: str) -> str:
        if self.yes:
            return ""
        try:
            return input(f"{CYAN}{prompt}{END} ").strip().lower()
        except EOFError:
            return "q"

    def perform(self, step: Step) -> str:
        ev, t0 = Evidence(), time.time()
        say()
        say(f"{BOLD}{step.id}  {step.title}{END}  {DIM}[{step.kind}{', ~' + str(step.minutes) + ' min' if step.minutes else ''}]{END}")
        if self.rehearse:
            rec = self.replay.get(step.id)
            if step.instructions:
                say(step.instructions.rstrip())
            if not rec:
                ev.note("no recorded evidence for this step")
            for ok, text in rec["evidence"] if rec else []:
                time.sleep(0.15)
                ev.check(ok, text)
            self.pause("Enter for the next step:")
            return "rehearsed"                              # a rehearsal leaves the journal untouched
        if step.kind == "manual":
            say(step.instructions.rstrip())
            answer = self.pause("When done press Enter (s = skip, q = quit):")
            if answer == "q":
                raise KeyboardInterrupt
            status = "skipped" if answer == "s" else ("assumed" if self.yes else "done")
            ev.note(f"marked {status} by the person at the keyboard")
        else:
            if step.instructions:
                say(step.instructions.rstrip(), DIM)
            try:
                step.fn(self, ev)
                status = "pass" if ev.ok else "fail"
            except KeyboardInterrupt:
                raise
            except Exception as e:
                ev.check(False, f"exception: {type(e).__name__}: {e}")
                status = "fail"
            if status == "fail":
                answer = self.pause("Step failed. Enter = continue anyway, r = retry, q = quit:")
                if answer == "r":
                    return self.perform(step)
                if answer == "q":
                    raise KeyboardInterrupt
        self.record(step, status, ev, time.time() - t0)
        if self.pace and step.kind != "manual":
            if self.pause("Enter for the next step (q = quit):") == "q":
                raise KeyboardInterrupt
        return status


# ----------------------------------------------------------------------------------------------- Part A steps
def a_prereq(c: Conductor, ev: Evidence) -> None:
    for tool, hint in [("git", "https://git-scm.com"), ("node", "Node 20 or later"), ("npm", "comes with Node"),
                       ("npx", "comes with Node")]:
        path = shutil.which(tool)
        ev.check(path, f"{tool} found ({hint})" if path else f"{tool} missing: {hint}")
    ver = sys.version_info
    ev.check(ver >= (3, 11), f"python {ver.major}.{ver.minor} (3.11 or later needed)")
    ev.check(os.path.exists(os.path.join(APPS, "policy-loader", "chunks.jsonl")), "policy-loader/chunks.jsonl present (86 passages)")
    n = sum(1 for _ in open(os.path.join(APPS, "policy-loader", "chunks.jsonl"), encoding="utf-8"))
    ev.check(n == 86, f"chunks.jsonl has {n} passages")


def a_npm(c: Conductor, ev: Evidence) -> None:
    cwd = os.path.join(APPS, "northwind-service")
    if os.path.isdir(os.path.join(cwd, "node_modules")):
        ev.note("node_modules already present, skipping npm ci")
    else:
        r = run(["npm", "ci"], cwd)
        ev.check(r.returncode == 0, "npm ci finished" if r.returncode == 0 else "npm ci failed: " + r.stderr[-300:])
    r = run(["npm", "test"], cwd)
    ev.check("# pass 9" in r.stdout and "# fail 0" in r.stdout, "npm test: same request, different users, different rows -> '# pass 9'")


def a_cap(c: Conductor, ev: Evidence) -> None:
    c.start_cap(ev)
    status, _, body = http_get(CAP_URL + "/Orders?$top=3", auth=("nancy", "nancy"))
    ev.check(status == 200 and body.count('"OrderID"') == 3, "GET /Orders?$top=3 as nancy returns three orders")
    status, _, _ = http_get(CAP_URL + "/Orders?$top=3")
    ev.check(status == 401, "the same URL without a user is refused (401)")


def a_venv(c: Conductor, ev: Evidence) -> None:
    cwd = os.path.join(APPS, "mcp-servers")
    if os.path.exists(venv_python()):
        ev.note(".venv already present, skipping venv + pip install")
    else:
        r = run([sys.executable, "-m", "venv", ".venv"], cwd)
        ev.check(r.returncode == 0, "python -m venv .venv")
        r = run([venv_python(), "-m", "pip", "install", "-q", "-r", "requirements.txt"], cwd, timeout=1200)
        ev.check(r.returncode == 0, "pip install -r requirements.txt" if r.returncode == 0 else "pip failed: " + r.stderr[-300:])
    r = run([venv_python(), "-c", "import mcp, jwt, httpx, pytest; print(mcp.__file__)"], cwd)
    ev.check(r.returncode == 0, "mcp SDK (1.x), PyJWT, httpx and pytest import inside .venv")
    r = run([venv_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd, timeout=600)
    line = next((l for l in r.stdout.splitlines() if "passed" in l or "failed" in l), r.stdout[-200:])
    ev.check(r.returncode == 0 and "45 passed" in line, f"pytest: {line.strip()}")


def a_mcp(c: Conductor, ev: Evidence) -> None:
    c.start_mcp(ev)
    status, _, body = http_get("http://localhost:8000/health")
    health = json.loads(body) if status == 200 else {}
    ev.check(health.get("signed_in_required") is False, f"GET /health -> {body.strip()[:80]} (DEV_MODE: no sign-in, laptop only)")
    r = run([venv_python(), os.path.join(HERE, "mcp_call.py"), "list"], HERE, timeout=60)
    tools = json.loads(r.stdout.strip().splitlines()[-1]).get("tools", []) if r.returncode == 0 else []
    ev.check(sorted(tools) == ["get_order_status", "get_product_availability", "search_policies"],
             f"tools/list over Streamable HTTP: {', '.join(tools) or r.stderr[-200:]}")


def a_ex1(c: Conductor, ev: Evidence) -> None:
    o = c.tool("get_order_status", {"order_id": 11019})
    ev.check(o.get("found") and o["customer"]["name"] == "Rancho grande" and o["customer"]["country"] == "Argentina",
             f"11019 as Nancy: customer {o.get('customer', {}).get('name')} ({o.get('customer', {}).get('country')})")
    ev.check(o.get("salesperson", {}).get("name") == "Michael Suyama" and o["salesperson"]["office_country"] == "UK",
             f"11019 salesperson {o.get('salesperson', {}).get('name')}, office {o.get('salesperson', {}).get('office_country')}")
    ev.check(o.get("required_date") == "2026-05-11" and o.get("days_until_required") == 4,
             f"11019 required {o.get('required_date')}, days_until_required {o.get('days_until_required')} (lab date {o.get('lab_today')})")
    ev.check(o.get("carrier", {}).get("name") == "Federal Shipping", f"11019 carrier {o.get('carrier', {}).get('name')} (id {o.get('carrier', {}).get('id')})")
    lines = {l["product_name"]: l for l in o.get("lines", [])}
    ev.check(set(lines) == {"Spegesild", "Maxilaku"} and lines["Spegesild"]["category"] == "Seafood" and lines["Spegesild"]["units_in_stock"] == 95
             and lines["Maxilaku"]["units_in_stock"] == 10 and lines["Maxilaku"]["units_on_order"] == 60,
             "11019 lines: Spegesild (Seafood, 95 in stock), Maxilaku (Confections, 10 in stock, 60 on order)")
    ev.check("data_read_at" in o, f"every fact carries data_read_at ({o.get('data_read_at')})")
    o = c.tool("get_order_status", {"order_id": 11070})
    ev.check(o.get("found") and o["salesperson"]["name"] == "Andrew Fuller" and o["salesperson"]["office_country"] == "USA"
             and o["days_until_required"] == 26, f"11070 as Nancy: {o.get('salesperson', {}).get('name')}, USA, {o.get('days_until_required')} days")
    o = c.tool("get_order_status", {"order_id": 11019}, user="steven")
    ev.check(o.get("found") is True, "11019 as Steven: visible (UK salesperson)")
    o = c.tool("get_order_status", {"order_id": 11070}, user="steven")
    ev.check(o.get("found") is False and "visible to you" in o.get("message", ""), f"11070 as Steven: found false, '{o.get('message')}'")
    log = open(os.path.join(LOGS, "cap.log"), encoding="utf-8", errors="replace").read()
    ev.check("404" in log and "Orders(11070)" in log, "Terminal 1 log shows the row rule answering with 404 for Orders(11070)")
    p = c.tool("get_product_availability", {"product": "Rössle Sauerkraut"})
    m = p.get("matches", [{}])[0]
    ev.check(m.get("discontinued") is True and m.get("units_in_stock") == 26 and m.get("reorder_level") == 0,
             f"Rössle Sauerkraut: discontinued {m.get('discontinued')}, {m.get('units_in_stock')} in stock, reorder level {m.get('reorder_level')}")
    p = c.tool("get_product_availability", {"product": "Chai"})
    m = p.get("matches", [{}])[0]
    ev.check(m.get("discontinued") is False, f"Chai: discontinued {m.get('discontinued')}, {m.get('units_in_stock')} in stock (a normal product)")


def a_ex2(c: Conductor, ev: Evidence) -> None:
    cites, passages, _ = c.cites("How much discount can I give a customer on my own authority?")
    ev.check(any(x.startswith("NW-POL-001 v2.0") for x in cites), "discount question cites NW-POL-001 v2.0: " + " | ".join(cites))
    ev.check(any("10 percent" in p["text"] for p in passages), "the number is 10 percent (locally restated by NW-POL-001 v2.0 section 5 and the runbook's Situation 6)")
    ev.check(not any(x.startswith("NW-POL-001 v1.0") for x in cites), "the superseded 1.0 policy (5 percent) is not returned")
    ev.check(not any(x.startswith("NW-MEM-900") for x in cites), "the unapproved spring-campaign draft (15 percent) is not returned")
    ev.check(all(p["status"] == "current" for p in passages), "every returned passage has status current")
    cites, _, _ = c.cites("customer wants a rush job, is that allowed?")
    ev.check(any(x.startswith("NW-GLO-001") for x in cites), "rush job: the glossary (NW-GLO-001) bridges 'rush job' to 'expedite': " + " | ".join(cites))
    cites, passages, _ = c.cites("Which carrier may carry seafood?")
    ev.check(any(x.startswith("NW-POL-004") for x in cites), "seafood carrier: NW-POL-004 cited: " + " | ".join(cites))
    ev.check(any("Speedy Express" in p["text"] for p in passages), "the passage names Speedy Express as the seafood carrier")


def a_ex3(c: Conductor, ev: Evidence) -> None:
    q = "How far are we prepared to go on the QUICK-Stop contract discount?"
    cites, passages, out = c.cites(q)
    ev.check(not any(x.startswith("NW-MEM-001") for x in cites), "Nancy: no London memo: " + (" | ".join(cites) or out.get("message", "")))
    ev.check(not any("20 percent" in p["text"] for p in passages), "Nancy: no negotiating figure anywhere in her passages")
    cites, passages, _ = c.cites(q, user="steven")
    ev.check("NW-MEM-001 v1.0, 2. QUICK-Stop contract renewal" in cites, "Steven: NW-MEM-001 v1.0, 2. QUICK-Stop contract renewal appears")
    memo = next((p for p in passages if p["doc_id"] == "NW-MEM-001"), {})
    ev.check("20 percent" in memo.get("text", ""), f"the memo holds the figure (prepared to go to 20 percent); effective {memo.get('effective_from')} to {memo.get('effective_to')}")
    c.start_mcp(ev, user="steven", LAB_TODAY="2026-08-01")
    cites, _, _ = c.cites(q, user="steven")
    ev.check(not any(x.startswith("NW-MEM-001") for x in cites), "optional: on 2026-08-01 the memo has expired, even for Steven")
    c.start_mcp(ev)


def a_ex4(c: Conductor, ev: Evidence) -> None:
    c.start_mcp(ev, STRICT_FILTERS="0")
    cites, passages, _ = c.cites("What discount may I approve for a customer?", k=6)
    status = {p["doc_id"] + " v" + p["version"]: p["status"] for p in passages}
    ev.check(status.get("NW-POL-001 v2.0") == "current", "filter off: current 10 percent (NW-POL-001 v2.0) still there")
    ev.check(status.get("NW-POL-001 v1.0") == "superseded", "filter off: superseded 5 percent (NW-POL-001 v1.0, 3. Approval tiers) now appears")
    ev.check(any(p["doc_id"] == "NW-MEM-900" and p["status"] == "unapproved" for p in passages),
             "filter off: unapproved draft 15 percent (NW-MEM-900) now appears")
    ev.note("citations: " + " | ".join(cites))
    cites, passages, _ = c.cites("Has the lead time for Pavlova products changed?")
    ext = [p for p in passages if p["status"] == "unverified-external"]
    ev.check(bool(ext), "filter off: the supplier email (unverified-external) appears: " + " | ".join(p["citation"] for p in ext))
    ev.check(any("ai assistant" in p["text"].lower() for p in ext), "the email carries an instruction addressed to 'any AI assistant' (data, not a command)")
    cites, _, _ = c.cites("How far are we prepared to go on the QUICK-Stop contract discount?")
    ev.check(any(x.startswith("NW-MEM-001") for x in cites), "filter off: Nancy now sees the London memo")
    c.start_mcp(ev)
    cites, passages, _ = c.cites("What discount may I approve for a customer?", k=6)
    ev.check(passages and all(p["status"] == "current" for p in passages), "filter on again: superseded and unapproved passages gone")
    cites, passages, _ = c.cites("Has the lead time for Pavlova products changed?")
    ev.check(not any(p["status"] == "unverified-external" for p in passages), "filter on again: the supplier email is gone")
    cites, _, _ = c.cites("How far are we prepared to go on the QUICK-Stop contract discount?")
    ev.check(not any(x.startswith("NW-MEM-001") for x in cites), "filter on again: Nancy no longer sees the memo")


def a_ex5(c: Conductor, ev: Evidence) -> None:
    cwd = os.path.join(APPS, "mcp-servers")
    for path, needle, what in [
        (os.path.join(APPS, "northwind-service", "srv", "northwind-service.cds"), "Employee.Country = $user.country", "the row rule in northwind-service.cds"),
        (os.path.join(cwd, "stores.py"), 'chunk["status"] != "current"', "visible() in stores.py refuses non-current passages"),
        (os.path.join(cwd, "hana_store.py"), "STATUS = 'current'", "the same condition inside the HANA SEARCH statement"),
        (os.path.join(cwd, "identity.py"), "DEV_USERS", "DEV_USERS in identity.py"),
        (os.path.join(cwd, "xsuaa.py"), "def audiences_for", "audiences_for in xsuaa.py"),
        (os.path.join(cwd, "server.py"), "SystemExit", "auth_config() exits when there is no XSUAA binding and no DEV_MODE"),
    ]:
        text = open(path, encoding="utf-8").read()
        ev.check(needle in text, what)
    src = open(os.path.join(cwd, "server.py"), encoding="utf-8").read()
    ev.check(src.count("@mcp.tool()") == 3, f"server.py defines exactly {src.count('@mcp.tool()')} tools, all read-only")
    # break the filter, watch tests fail, put it back
    store = os.path.join(cwd, "stores.py")
    original = open(store, encoding="utf-8").read()
    broken = original.replace('if chunk["status"] != "current":', 'if chunk["status"] not in ("current", "superseded"):')
    ev.check(broken != original, "mutation: visible() now lets superseded passages through")
    try:
        open(store, "w", encoding="utf-8").write(broken)
        r = run([venv_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd, timeout=600)
        failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED")]
        ev.check(r.returncode != 0 and failed, f"pytest now fails: {len(failed)} test(s), e.g. {failed[0][7:90] if failed else '-'}")
    finally:
        open(store, "w", encoding="utf-8").write(original)
    r = run([venv_python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-k", "another_application"], cwd, timeout=300)
    ev.check(r.returncode == 0 and "1 passed" in r.stdout, "restored; test_token_issued_to_another_application_is_refused passes (the audience check)")


def a_stdio(c: Conductor, ev: Evidence) -> None:
    r = run([venv_python(), os.path.join(HERE, "mcp_call.py"), "stdio", json.dumps({"order_id": 11019})], HERE, timeout=120)
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
    ev.check(len(out.get("tools", [])) == 3 and out.get("result", {}).get("found"), "stdio transport (desktop clients): three tools, order 11019 found")


def a_stop(c: Conductor, ev: Evidence) -> None:
    c.stop_all()
    ev.check(not wait_for("http://localhost:8000/health", 2), "MCP server stopped")
    ev.check(not wait_for(CAP_URL, 2, auth=("nancy", "nancy")), "data service stopped")


# ----------------------------------------------------------------------------------------------- Part B steps
def cf(*args: str) -> subprocess.CompletedProcess | None:
    if not shutil.which("cf"):
        return None
    try:
        return run(["cf", *args], APPS, timeout=120)
    except Exception:
        return None


def cf_check(ev: Evidence, args: tuple, cond: Callable[[str], bool], text: str) -> None:
    """A cf-based check; on a machine without the cf CLI it is noted as skipped, not failed."""
    r = cf(*args)
    if r is None:
        ev.note(f"skipped (no cf CLI on this machine): {text}")
        return
    ev.check(r.returncode == 0 and cond(r.stdout), text if r.returncode == 0 else f"{text}: {(r.stderr or r.stdout).strip()[:120]}")


def b_cli(c: Conductor, ev: Evidence) -> None:
    ev.check(shutil.which("cf"), "cf CLI installed (brew install cloudfoundry/tap/cf-cli@8)")
    ev.check(shutil.which("mbt"), "mbt installed (npm i -g mbt)")
    r = cf("target")
    ok = r is not None and r.returncode == 0 and BTP["org"] in r.stdout and BTP["space"] in r.stdout
    ev.check(ok, f"cf target: org {BTP['org']}, space {BTP['space']}" if ok else "cf target: not signed in or wrong org/space (cf login --sso)")


def b_hana(c: Conductor, ev: Evidence) -> None:
    cf_check(ev, ("service", "northwind-hana"), lambda out: "succeeded" in out, "cf service northwind-hana: exists, last operation succeeded")
    ev.note("the trial instance stops every night; if it is stopped, start it in HANA Cloud Central before B7")


def b_cap(c: Conductor, ev: Evidence) -> None:
    cf_check(ev, ("app", "northwind-service-srv"), lambda out: "running" in out, "cf app northwind-service-srv: running")
    status, _, _ = http_get(BTP["cap"] + "/Orders?$top=1")
    ev.check(status == 401, f"data service on BTP refuses an anonymous request ({status}); XSUAA guards it")
    cf_check(ev, ("service", "northwind-service-auth"), lambda out: "succeeded" in out, "XSUAA instance northwind-service-auth: last operation succeeded (redirect URIs for Claude applied)")


def b_policy_db(c: Conductor, ev: Evidence) -> None:
    cf_check(ev, ("service", "policy-db"), lambda out: "user-provided" in out, "user-provided service policy-db exists (POLICY_READER credentials, typed, never in a file)")


def b_mcp(c: Conductor, ev: Evidence) -> None:
    cf_check(ev, ("app", "northwind-mcp"), lambda out: "running" in out, "cf app northwind-mcp: running")
    base = BTP["mcp"]
    status, _, body = http_get(base + "/health")
    health = json.loads(body) if status == 200 else {}
    ev.check(health.get("signed_in_required") is True, f"GET /health -> {status} {body.strip()[:80]} (sign-in required)")
    status, _, body = http_get(base + "/.well-known/oauth-protected-resource/mcp")
    ev.check(status == 200 and base + "/" in body, "protected-resource metadata names this server as its own authorization server")
    status, _, body = http_get(base + "/.well-known/oauth-authorization-server")
    ev.check(status == 200 and "/oauth/authorize" in body and "/oauth/token" in body and "registration_endpoint" not in body,
             "authorization-server metadata points at XSUAA authorize/token, no dynamic registration")
    status, headers, _ = http_get(base + "/mcp", method="POST", body=b"{}", headers={"content-type": "application/json"})
    www = {k.lower(): v for k, v in headers.items()}.get("www-authenticate", "")
    ev.check(status == 401 and "resource_metadata" in www, f"POST /mcp without a token -> {status}, WWW-Authenticate carries resource_metadata")
    status, _, _ = http_get(base + "/mcp", method="POST", body=b"{}", headers={"content-type": "application/json", "Authorization": "Bearer forged"})
    ev.check(status == 401, "a forged bearer token is refused just the same (401)")


def b_key(c: Conductor, ev: Evidence) -> None:
    cf_check(ev, ("service-keys", "northwind-service-auth"), lambda out: "claude-connector" in out,
             "service key claude-connector exists (its values live only in your password manager and Claude's connector settings)")


PART_A = [
    Step("A1", "Prerequisites on this laptop", "auto", a_prereq, minutes=1),
    Step("A2", "Terminal 1: npm ci and npm test (9 tests)", "auto", a_npm, minutes=3),
    Step("A3", "Terminal 1: start the data service", "auto", a_cap, minutes=1),
    Step("A4", "Terminal 2: venv, pip install, pytest (45 tests)", "auto", a_venv, minutes=5),
    Step("A5", "Terminal 2: start the MCP server as Nancy, list the tools", "auto", a_mcp, minutes=1),
    Step("A6", "Exercise 1: live facts and the row rule", "auto", a_ex1, minutes=2),
    Step("A7", "Exercise 2: rules with citations", "auto", a_ex2, minutes=1),
    Step("A8", "Exercise 3: identity decides (Nancy, Steven, and August)", "auto", a_ex3, minutes=2),
    Step("A9", "Exercise 4: the traps, filter off and on again", "auto", a_ex4, minutes=2),
    Step("A10", "Exercise 5: find each rule, break one, watch a test fail", "auto", a_ex5, minutes=3),
    Step("A11", "Bonus: the same server over stdio", "auto", a_stdio, minutes=1),
    Step("A12", "Stop both servers", "auto", a_stop),
]

PART_B = [
    Step("B1", "Create the SAP BTP trial account", "manual", minutes=15, instructions="""
   1. https://account.hanatrial.ondemand.com  ->  Register, confirm the email, sign in.
   2. Choose region Singapore (ap21) when asked. Wait for 'trial subaccount created'.
   3. In the trial subaccount: Cloud Foundry Environment shows org <account>trial and space dev.
   Nothing to type here except your own account details. The conductor never sees them."""),
    Step("B2", "Prepare the environment", "manual", minutes=60, instructions="""
   1. Subaccount > Entitlements: SAP HANA Cloud (hana-free, tools), Application Runtime (memory), Destination.
   2. Subaccount > Subscriptions > SAP HANA Cloud, plan 'tools' -> Subscribe.
   3. Security > Users > you > assign role collections 'SAP HANA Cloud Administrator' and 'SAP HANA Cloud Security Administrator'.
   4. Open HANA Cloud Central, Create Instance: name northwind-hana, allow all IP addresses, enable NLP. Wait ~15 min.
   5. Choose the DBADMIN password yourself and keep it in your password manager. If you lose it: Security Administrator > Reset DBADMIN Password.
   Nightly: the trial instance stops every night; start it before a session."""),
    Step("B3", "Tools on your laptop and sign-in (cf, mbt, cf login --sso)", "probe", b_cli, minutes=15),
    Step("B4", "HANA instance exists and is healthy", "probe", b_hana, minutes=1),
    Step("B5", "Deploy the Northwind data service (mbt build, cf deploy)", "manual", minutes=20, instructions="""
   cd apps/northwind-service
   npm ci && mbt build
   cf deploy mta_archives/northwind-service_0.1.0.mtar
   Then: Security > Role Collections. Assign 'SalesHQ (northwind-service ...)' to yourself. Leave 'Northwind SalesRegion UK' unassigned for now."""),
    Step("B6", "Data service deployed and guarded by XSUAA", "probe", b_cap, minutes=1),
    Step("B7", "The documents into HANA (SQL console)", "manual", minutes=20, instructions="""
   In HANA Cloud Central > SQL console (as DBADMIN):
   1. Run apps/hana/load_policy_chunks.sql   ->  86 rows, then the UPDATE that fills VEC. Check: count 86 and 86.
   2. Run apps/hana/create_policy_reader.sql with a password YOU choose (replace <choose-a-password>). Clear the console history afterwards.
   3. Try the search from Part B step 5 of the handbook: NW-RUN-001 first for the rush question, NW-MEM-001 first for QUICK-Stop as sales-london."""),
    Step("B8", "Give the MCP server its database credentials (cf cups, typed)", "manual", minutes=3, instructions="""
   cf cups policy-db -p "host, port, user, password, schema"
   host = the SQL endpoint without :443, port = 443, user = POLICY_READER, password = the one you chose, schema = DBADMIN.
   Each value is asked for interactively; nothing lands in a file or in the shell history. (Already exists? cf update-user-provided-service policy-db -p "...".)"""),
    Step("B9", "policy-db service exists", "probe", b_policy_db),
    Step("B10", "Deploy the MCP server (cf push)", "manual", minutes=5, instructions="""
   cd apps/mcp-servers
   cf push
   Wait for 'running'. If it crashes: cf logs northwind-mcp --recent. The manifest has no DEV_MODE, on purpose."""),
    Step("B11", "MCP server up: health, OAuth metadata, and 401 without a token", "probe", b_mcp, minutes=1),
    Step("B12", "Service key for Claude's connector", "manual", minutes=3, instructions="""
   cf create-service-key northwind-service-auth claude-connector
   cf service-key northwind-service-auth claude-connector
   Copy clientid and clientsecret into your password manager. They go into Claude's connector settings and nowhere else."""),
    Step("B13", "Service key exists", "probe", b_key),
    Step("B14", "Connect Claude", "manual", minutes=5, instructions=f"""
   Claude > Settings > Connectors > Add custom connector:
     Name: Northwind Advisor
     URL:  {BTP['mcp']}/mcp
     Advanced: OAuth Client ID = clientid, OAuth Client Secret = clientsecret
   Add, Connect, sign in on the SAP page with your BTP user. Claude returns with the connector connected."""),
    Step("B15", "The demo questions in Claude (as Nancy)", "manual", minutes=10, instructions="""
   Ask, in a fresh chat with the connector enabled, and compare with the Demo Script:
   1. What is the status of order 11019, and can it be expedited?
      -> get_order_status then search_policies; Rancho grande, 4 days, Federal Shipping; expedite conditions cited as
         NW-POL-002 v1.0, 4.; the seafood line must move to Speedy Express (NW-POL-004 v1.0), corrected by Logistics at no charge.
   2. How much discount can I give on my own authority?      -> 10 percent, NW-POL-001 v2.0; never 5 or 15.
   3. How far are we prepared to go on the QUICK-Stop contract? -> no figure; 'not available to you'.
   4. Has the lead time for Pavlova products changed?         -> nothing from the supplier email; 'not available'.
   5. Is Rössle Sauerkraut still available?                  -> discontinued, 26 in stock.
   6. Please approve the expedite for 11019.                  -> refuses; points to the Sales Approvals queue.
   If a tool call says the session expired, ask again; Claude reconnects."""),
]


# ----------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", choices=["A", "B", "all"], default="all")
    ap.add_argument("--start", help="first step to run, e.g. A6 or B11")
    ap.add_argument("--only", help="run one step, e.g. A9")
    ap.add_argument("--yes", action="store_true", help="never wait at the keyboard (manual steps are marked 'assumed')")
    ap.add_argument("--pace", action="store_true", help="live session: pause for Enter after every step, so the screen moves at your speed")
    ap.add_argument("--rehearse", action="store_true", help="replay recorded evidence; run nothing")
    ap.add_argument("--fresh", action="store_true", help="start a new journal instead of adding to the existing one (with --rehearse: replay the shipped recording, not your journal)")
    args = ap.parse_args()

    steps = (PART_A if args.part in ("A", "all") else []) + (PART_B if args.part in ("B", "all") else [])
    if args.start:
        ids = [s.id for s in steps]
        if args.start.upper() not in ids:
            ap.error(f"--start must be one of {', '.join(ids)}")
        steps = steps[ids.index(args.start.upper()):]
    if args.only:
        steps = [s for s in steps if s.id == args.only.upper()] or ap.error("unknown step")

    c = Conductor(yes=args.yes, rehearse=args.rehearse)
    c.pace = args.pace and not args.yes
    if not args.fresh:
        c.load_journal()
    if args.rehearse:
        src = JOURNAL_JSON if os.path.exists(JOURNAL_JSON) and not args.fresh else REHEARSAL
        if not os.path.exists(src):
            say("nothing to rehearse yet: run the lab once, or put a rehearsal.json next to this script", YELLOW)
            return 2
        with open(src) as f:
            c.replay = {r["id"]: r for r in json.load(f)}
        say(f"Rehearsal from {os.path.basename(src)}: nothing is executed, the recorded evidence is replayed.", YELLOW)

    say(f"{BOLD}Northwind Advisor lab conductor{END}  {DIM}{len(steps)} steps, journal in lab/lab_journal.md{END}")
    results = {}
    try:
        for step in steps:
            results[step.id] = c.perform(step)
            if step.kind in ("auto", "probe") and not args.rehearse and step.id.startswith("A") and results[step.id] == "fail" \
                    and step.id in ("A2", "A3", "A4", "A5"):
                say("A setup step failed; the exercises need it. Fix it and rerun with --start " + step.id, YELLOW)
                break
    except KeyboardInterrupt:
        say("\nstopped at the keyboard", YELLOW)
    finally:
        c.stop_all()
    say()
    say(f"{BOLD}Summary{END}")
    for sid, status in results.items():
        colour = GREEN if status in ("pass", "done", "rehearsed") else (RED if status == "fail" else YELLOW)
        say(f"   {sid:<4} {colour}{status:<9}{END} {next(s.title for s in steps if s.id == sid)}")
    say(f"{DIM}journal: {JOURNAL_MD}{END}")
    return 0 if all(s in ("pass", "done", "rehearsed", "assumed", "skipped") for s in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
