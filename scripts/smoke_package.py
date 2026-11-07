"""Install a packed npm payload in isolation, then use its installed MCP connection."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from verify_package import find_archive, verify_archive

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    archive = find_archive(args.path).resolve()
    verify_archive(archive)
    temp_parent = ROOT / "artifacts"
    temp_parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-smoke-", dir=temp_parent) as temporary:
        temporary = Path(temporary)
        with tarfile.open(archive, "r:gz") as tar:
            # verify_archive already restricted every entry to a regular allowlisted file.
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                target = temporary / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
        source = temporary / "package"
        project = temporary / "consumer project 한글"
        project.mkdir()
        home = temporary / "persistent home 한글"
        env = {**os.environ, "NOVEL_AED_PYTHON": sys.executable, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        subprocess.run(["node", str(source / "bin/novel-aed.mjs"), "setup", "--client", "cursor",
                        "--project", str(project), "--home", str(home), "--write"],
                       env=env, check=True, cwd=temporary)
        config = json.loads((project / ".cursor/mcp.json").read_text(encoding="utf-8"))["mcpServers"]["novel_aed"]
        runtime = Path(config["args"][0]).parents[1]
        expected_stories = home / "stories"
        if Path(config["args"][-1]) != expected_stories or not runtime.is_relative_to(home):
            raise ValueError("Setup did not use persistent data/runtime paths")
        if not (project / ".cursor/skills/novel-aed/SKILL.md").is_file():
            raise ValueError("Packaged skill was not installed")
        # Prove the installed connection is independent of the extracted npm cache.
        hidden_source = temporary / "npm-cache-unavailable"
        source.rename(hidden_source)
        subprocess.run([config["command"], str(runtime / "scripts/check_mcp.py")],
                       cwd=project, env=env, check=True)
        # Create/read a disposable story through the actual installed MCP config.
        code = r'''
import asyncio, json, sys
from datetime import timedelta
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def check():
    config = json.loads(sys.argv[1])
    parameters = StdioServerParameters(command=config["command"], args=config["args"])
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams, read_timeout_seconds=timedelta(seconds=30)) as session:
            await session.initialize()
            created = await session.call_tool("initialize_story", {"story":"packaged-fixture", "title":"Package smoke fixture", "source_text":"A traveler reached the locked gate. She carried a key."})
            assert not created.isError, created.content
            status = await session.call_tool("get_status", {"story":"packaged-fixture"})
            assert not status.isError, status.content
            assert status.structuredContent["next"] == "analysis"
asyncio.run(check())
'''
        subprocess.run([config["command"], "-c", code, json.dumps(config, ensure_ascii=False)],
                       cwd=project, env=env, check=True)
        if not (expected_stories / "packaged-fixture/source.md").is_file():
            raise ValueError("Story was not written to persistent storage")
        print(json.dumps({"package_smoke": "OK", "cache_independence": True, "installed_skill": True,
                          "installed_mcp": True, "persistent_story_storage": True}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
