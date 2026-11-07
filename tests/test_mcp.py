"""End-to-end wire tests against a real stdio MCP server and the official SDK client."""
import importlib.util
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SDK_AVAILABLE = importlib.util.find_spec("mcp") is not None
if SDK_AVAILABLE:
    from contextlib import AsyncExitStack
    from datetime import timedelta
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

# Synthetic contract fixtures; never run a model or touch a user's story.
spec = importlib.util.spec_from_file_location("workflow_fixtures", ROOT / "tests/test_workspace.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


@unittest.skipUnless(SDK_AVAILABLE, "Install requirements-mcp.txt to run real MCP wire tests")
class MCPWireTest(unittest.TestCase):
    async def run_case(self, scenario):
        # AnyIO task groups must enter and exit in the same asyncio task.
        with tempfile.TemporaryDirectory(dir=ROOT / "stories") as temporary:
            self.root = Path(temporary)
            with (self.root / "server.log").open("w", encoding="utf-8") as error_log:
                async with AsyncExitStack() as stack:
                    params = StdioServerParameters(
                        command=sys.executable,
                        args=[str(ROOT / "scripts/mcp_server.py"), "--stories-root", str(self.root / "works")],
                        cwd=str(self.root), env={"PYTHONIOENCODING": "utf-8"})
                    streams = await stack.enter_async_context(stdio_client(params, errlog=error_log))
                    self.session = await stack.enter_async_context(
                        ClientSession(*streams, read_timeout_seconds=timedelta(seconds=30)))
                    self.hello = await self.session.initialize()
                    await scenario()

    async def call(self, tool_name, ok=True, **arguments):
        result = await self.session.call_tool(tool_name, arguments)
        self.assertEqual(not result.isError, ok, str(result.content))
        if not ok:
            return result
        self.assertIsNotNone(result.structuredContent, f"{tool_name} must return structured JSON")
        self.assertEqual(json.loads(result.content[0].text), result.structuredContent)
        return result.structuredContent

    async def init(self):
        return await self.call("initialize_story", story="테스트-work", title="Synthetic MCP fixture",
                               source_text="A traveler reached the locked gate. She carried a key.")

    async def submit(self, payload):
        status = await self.call("get_status", story="테스트-work")
        saved = await self.call("save_draft", story="테스트-work", name="input.json", payload=payload,
                                revision=status["revision"])
        return await self.call("submit_draft", story="테스트-work", name="input.json", revision=saved["revision"])

    async def approve(self, pending):
        return await self.call("approve_result", story="테스트-work", revision=pending["revision"],
                               digest=pending["pending"]["digest"], message="Synthetic user approval for test fixture")

    def test_full_workflow_over_stdio(self):
        asyncio.run(self.run_case(self.full_workflow))

    async def full_workflow(self):
        self.assertEqual(self.hello.serverInfo.name, "Novel AED")
        tools = (await self.session.list_tools()).tools
        self.assertEqual(len(tools), 17)
        by_name = {tool.name: tool for tool in tools}
        for tool in tools:
            self.assertEqual(tool.outputSchema["type"], "object", tool.name)
        self.assertTrue(by_name["read_source_chunk"].annotations.readOnlyHint)
        self.assertFalse(by_name["approve_result"].annotations.readOnlyHint)
        self.assertIn("revision", by_name["approve_result"].inputSchema["required"])
        self.assertIn("explicit", self.hello.instructions)
        resources = await self.session.list_resources()
        self.assertEqual(len(resources.resources), 2)
        resource = await self.session.read_resource("novel-aed://workflow")
        self.assertIn("승인", resource.contents[0].text)
        for topic in ("rules", "workflow", "skill", "analysis", "outline", "chapter"):
            guide = await self.call("get_guidance", topic=topic)
            self.assertTrue(guide["instructions"])
            if topic in ("analysis", "outline", "chapter"):
                self.assertEqual(guide["schema"]["type"], "object")
        initial = await self.init()
        self.assertEqual(initial["revision"], 0)
        listed = await self.call("list_stories")
        self.assertEqual(listed["items"][0]["story"], "테스트-work")
        configured = await self.call("set_preferences", story="테스트-work", revision=0,
                                     preferences={"output_language": "source", "count_mode": "custom",
                                                  "chapters_count": 1, "length_mode": "custom",
                                                  "target_chars": 100, "preferences": ""})
        reference = await self.call("add_reference", story="테스트-work", revision=configured["revision"],
                                   name="world.md", text="Synthetic background", scope="Test fixture only")
        context = await self.call("get_context", story="테스트-work")
        self.assertIn("references/world.md", context["files"]["items"])
        chunk = await self.call("read_source_chunk", story="테스트-work", chunk_id="src-0001")
        self.assertEqual(chunk["text"], "A traveler reached the locked gate. She carried a key.")
        part = fixtures.WorkflowTest().analysis()["parts"][0]
        saved = await self.call("save_draft", story="테스트-work", name="part.json", payload=part,
                                revision=reference["revision"])
        assembled = await self.call("assemble_draft", story="테스트-work", name="analysis.json", kind="analysis",
                                    part_names=["part.json"], header={}, revision=saved["revision"])
        pending = await self.call("submit_draft", story="테스트-work", name="analysis.json", revision=assembled["revision"])
        self.assertEqual(pending["next"], "awaiting_approval")
        await self.call("save_draft", ok=False, story="테스트-work", name="overwrite.json", payload={}, revision=pending["revision"])
        await self.call("submit_draft", ok=False, story="테스트-work", name="analysis.json", revision=pending["revision"])
        await self.call("approve_result", ok=False, story="테스트-work", revision=pending["revision"], digest="wrong", message="Synthetic approval")
        history = await self.call("read_story_file", story="테스트-work", path=pending["pending"]["file"])
        self.assertEqual(json.loads(history["text"]), {"parts": [part]})
        approved = await self.approve(pending)
        self.assertEqual(approved["next"], "outline")
        claims = await self.call("read_approved", story="테스트-work", section="claims")
        self.assertEqual(claims["items"][0]["id"], "canon-00001")
        pending = await self.submit(fixtures.WorkflowTest().outline())
        self.assertEqual((await self.approve(pending))["next"], "chapter")
        text = "x" * 100
        self.assertEqual((await self.call("measure_text", text=text + " \n\t"))["nonspace_characters"], 100)
        pending = await self.submit({"draft": {"title": "Synthetic", "text": text, "state_changes": ["Gate opened"],
                                              "resolved_thread_ids": ["canon-00001"]},
                                     "review": {"verdict": "pass", "issues": [], "rationale": "Synthetic contract check"}})
        self.assertEqual((await self.approve(pending))["next"], "complete")
        self.assertTrue((await self.call("validate_story", story="테스트-work"))["valid"])
        chapter = await self.call("read_story_file", story="테스트-work", path="chapters/0001.md")
        self.assertEqual(chapter["text"], "Synthetic\n\n" + text)

    def test_errors_and_rejection_preserve_session(self):
        asyncio.run(self.run_case(self.errors_and_rejection))

    async def errors_and_rejection(self):
        await self.init()
        await self.call("get_status", ok=False, story="../escape")
        await self.call("read_story_file", ok=False, story="테스트-work", path="state.json")
        # Wire argument validation must reject malformed types before calling the workflow.
        await self.call("get_context", ok=False, story="테스트-work", offset="invalid")
        await self.call("get_guidance", ok=False, topic="not-a-stage")
        pending = await self.submit(fixtures.WorkflowTest().analysis())
        rejected = await self.call("reject_result", story="테스트-work", revision=pending["revision"], reason="Synthetic revision request")
        self.assertEqual(rejected["next"], "analysis")
        history = await self.call("read_story_file", story="테스트-work", path=pending["pending"]["file"])
        self.assertIn("locked gate", history["text"])
        self.assertTrue((await self.call("validate_story", story="테스트-work"))["valid"])


if __name__ == "__main__":
    unittest.main()
