"""Read-only handshake check using the official MCP client; never reads story contents."""
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import sys

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    sys.exit("Run this with the Python environment containing requirements-mcp.txt")

ROOT = Path(__file__).resolve().parents[1]


async def check():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "scripts/mcp_server.py")],
                                  env={"PYTHONIOENCODING": "utf-8"})
    async with stdio_client(params) as streams:
        async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=30)) as session:
            hello = await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            result = await session.call_tool("get_guidance", {"topic": "workflow"})
            if result.isError:
                raise RuntimeError(str(result.content))
            print(json.dumps({"server": hello.serverInfo.name, "protocol": hello.protocolVersion,
                              "tools": [tool.name for tool in tools.tools],
                              "resources": [str(resource.uri) for resource in resources.resources],
                              "guidance_call": "OK"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(check())
