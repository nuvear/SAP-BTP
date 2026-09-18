"""Call one tool on the local MCP server and print the JSON result. Runs inside apps/mcp-servers/.venv.

    python mcp_call.py list                              [--user nancy] [--url http://localhost:8000/mcp]
    python mcp_call.py call get_order_status '{"order_id": 11019}' --user steven
    python mcp_call.py stdio '{"order_id": 11019}'      (starts server.py advisor --stdio itself)
"""
import asyncio, json, os, sys

URL = "http://localhost:8000/mcp"


def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def http(mode: str, name: str | None, args: dict, user: str, url: str):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with streamablehttp_client(url, headers={"X-Dev-User": user}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            if mode == "list":
                tools = await s.list_tools()
                return {"tools": [t.name for t in tools.tools]}
            res = await s.call_tool(name, args)
            return json.loads(_text(res)) if not res.isError else {"error": _text(res)}


async def stdio(args: dict, user: str):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    here = os.path.dirname(os.path.abspath(__file__))
    env = dict(os.environ, DEV_MODE="1", DEV_USER=user, LAB_TODAY="2026-05-07",
               NORTHWIND_SERVICE_URL="http://localhost:4004/odata/v4/northwind",
               POLICY_CHUNKS=os.path.join(here, "..", "policy-loader", "chunks.jsonl"))
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(here, "..", "mcp-servers", "server.py"), "advisor", "--stdio"],
                                   env=env, cwd=os.path.join(here, "..", "mcp-servers"))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            res = await s.call_tool("get_order_status", args)
            return {"tools": [t.name for t in tools.tools], "result": json.loads(_text(res))}


if __name__ == "__main__":
    mode = sys.argv[1]
    user = sys.argv[sys.argv.index("--user") + 1] if "--user" in sys.argv else "nancy"
    url = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else URL
    if mode == "list":
        out = asyncio.run(http("list", None, {}, user, url))
    elif mode == "call":
        out = asyncio.run(http("call", sys.argv[2], json.loads(sys.argv[3]), user, url))
    else:
        out = asyncio.run(stdio(json.loads(sys.argv[2]), user))
    print(json.dumps(out, ensure_ascii=False))
