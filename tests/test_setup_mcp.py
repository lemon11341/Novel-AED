import copy
import importlib.util
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_mcp", ROOT / "scripts/setup_mcp.py")
setup_mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_mcp)


class SetupMcpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "stories")
        self.addCleanup(self.temp.cleanup)
        self.temp_root = Path(self.temp.name)
        self.install_root = self.temp_root / "설치 경로 with spaces" / "Novel AED"
        self.install_root.mkdir(parents=True)
        self.project = self.temp_root / "프로젝트 경로 with spaces"
        self.project.mkdir()

    def entry(self):
        return setup_mcp.server_entry(self.install_root)

    def test_codex_merge_keeps_other_tables_and_is_idempotent(self):
        entry = self.entry()
        original = ('[tool]\nname = "keep me"\n\n'
                    '[mcp_servers.other]\ncommand = "other-server"\n')

        merged, changed = setup_mcp.merge_codex(original, entry)
        parsed = tomllib.loads(merged)
        self.assertTrue(changed)
        self.assertEqual(parsed["tool"]["name"], "keep me")
        self.assertEqual(parsed["mcp_servers"]["other"]["command"], "other-server")
        self.assertEqual(parsed["mcp_servers"]["novel_aed"], entry)

        repeated, changed = setup_mcp.merge_codex(merged, entry)
        self.assertFalse(changed)
        self.assertEqual(repeated, merged)

    def test_codex_conflict_is_rejected(self):
        entry = self.entry()
        wrong = copy.deepcopy(entry)
        wrong["tool_timeout_sec"] = 121
        existing = setup_mcp.render_codex(wrong) + "\n"
        with self.assertRaisesRegex(ValueError, "differs"):
            setup_mcp.merge_codex(existing, entry)

    def test_codex_replace_removes_server_and_subtables_keeps_other_tables(self):
        entry = self.entry()
        old = copy.deepcopy(entry)
        old["command"] = "old-server"
        original = (
            '[tool]\nkeep = "yes"\n\n'
            + setup_mcp.render_codex(old)
            + '\n\n[mcp_servers.novel_aed.env]\nTOKEN = "old"\n'
            + '\n[mcp_servers.other]\ncommand = "other-server"\n'
            + '\n[other]\nkeep = 9\n'
        )
        with self.assertRaisesRegex(ValueError, "differs"):
            setup_mcp.merge_codex(original, entry)

        replaced, changed = setup_mcp.merge_codex(original, entry, replace=True)
        parsed = tomllib.loads(replaced)
        self.assertTrue(changed)
        self.assertEqual(parsed["tool"]["keep"], "yes")
        self.assertEqual(parsed["mcp_servers"]["novel_aed"], entry)
        self.assertEqual(parsed["mcp_servers"]["other"]["command"], "other-server")
        self.assertEqual(parsed["other"]["keep"], 9)
        self.assertNotIn("env", parsed["mcp_servers"]["novel_aed"])

    def test_codex_replace_refuses_complex_quoted_table_syntax(self):
        entry = self.entry()
        original = '[mcp_servers."novel_aed"]\ncommand = "old"\n'
        with self.assertRaisesRegex(ValueError, "quoted/complex"):
            setup_mcp.merge_codex(original, entry, replace=True)

    def test_json_merge_keeps_other_keys_and_is_idempotent(self):
        entry = self.entry()
        portable = setup_mcp.portable_entry(entry)
        original = json.dumps({"keep": {"value": 7}, "mcpServers": {
            "other": {"command": "other-server"}}}, ensure_ascii=False, indent=2)

        merged, changed = setup_mcp.merge_json(original, entry)
        parsed = json.loads(merged)
        self.assertTrue(changed)
        self.assertEqual(parsed["keep"], {"value": 7})
        self.assertEqual(parsed["mcpServers"]["other"]["command"], "other-server")
        self.assertEqual(parsed["mcpServers"]["novel_aed"], portable)

        repeated, changed = setup_mcp.merge_json(merged, entry)
        self.assertFalse(changed)
        self.assertEqual(repeated, merged)

    def test_json_conflict_is_rejected(self):
        entry = setup_mcp.portable_entry(self.entry())
        wrong = copy.deepcopy(entry)
        wrong["args"][-1] = str(self.install_root / "different")
        existing = json.dumps({"mcpServers": {"novel_aed": wrong}}, ensure_ascii=False)
        with self.assertRaisesRegex(ValueError, "differs"):
            setup_mcp.merge_json(existing, entry)

    def test_json_replace_changes_only_novel_aed(self):
        entry = setup_mcp.portable_entry(self.entry())
        original = json.dumps({"keep": {"value": 4}, "mcpServers": {
            "novel_aed": {"command": "old", "args": []},
            "other": {"command": "other-server"}}}, ensure_ascii=False)
        replaced, changed = setup_mcp.merge_json(original, entry, replace=True)
        parsed = json.loads(replaced)
        self.assertTrue(changed)
        self.assertEqual(parsed["keep"], {"value": 4})
        self.assertEqual(parsed["mcpServers"]["novel_aed"], entry)
        self.assertEqual(parsed["mcpServers"]["other"], {"command": "other-server"})

    def test_unicode_and_spaces_round_trip_through_toml_and_json(self):
        entry = self.entry()
        self.assertIn("설치 경로 with spaces", entry["args"][0])

        toml_text = setup_mcp.render_codex(entry)
        self.assertIn("설치 경로 with spaces", toml_text)
        self.assertEqual(tomllib.loads(toml_text)["mcp_servers"]["novel_aed"], entry)

        json_text = setup_mcp.render_json(entry)
        self.assertIn("설치 경로 with spaces", json_text)
        self.assertNotIn("\\uC124", json_text)
        self.assertEqual(json.loads(json_text)["mcpServers"]["novel_aed"], setup_mcp.portable_entry(entry))
        self.assertNotIn("startup_timeout_sec", json_text)
        self.assertNotIn("tool_timeout_sec", json_text)

    def test_write_copies_skill_and_repeated_write_is_a_noop(self):
        canonical = self.install_root / "skills" / "novel-aed"
        canonical.mkdir(parents=True)
        (canonical / "SKILL.md").write_text("canonical skill\n", encoding="utf-8")
        (canonical / "guidance.md").write_text("Korean: 한글\n", encoding="utf-8")

        plan = setup_mcp.make_plan("cursor", self.project, self.install_root, write=True)
        self.assertTrue(plan["config_changed"])
        self.assertTrue(plan["skill_changed"])
        setup_mcp.apply_plan(plan)

        destination = self.project / ".cursor" / "skills" / "novel-aed"
        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "canonical skill\n")
        self.assertEqual((destination / "guidance.md").read_text(encoding="utf-8"), "Korean: 한글\n")
        config = json.loads((self.project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(config["mcpServers"]["novel_aed"],
                         setup_mcp.portable_entry(setup_mcp.server_entry(self.install_root)))

        repeated = setup_mcp.make_plan("cursor", self.project, self.install_root, write=True, replace=True)
        self.assertFalse(repeated["config_changed"])
        self.assertFalse(repeated["skill_changed"])
        self.assertEqual(repeated["backup_paths"], [])
        setup_mcp.apply_plan(repeated)

    def test_configuration_conflict_preflight_prevents_skill_copy(self):
        canonical = self.install_root / "skills" / "novel-aed"
        canonical.mkdir(parents=True)
        (canonical / "SKILL.md").write_text("canonical skill\n", encoding="utf-8")
        config_path = self.project / ".codex" / "config.toml"
        config_path.parent.mkdir()
        wrong = copy.deepcopy(self.entry())
        wrong["command"] += "-different"
        config_path.write_text(setup_mcp.render_codex(wrong) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "differs"):
            setup_mcp.make_plan("codex", self.project, self.install_root, write=True)
        self.assertFalse((self.project / ".agents" / "skills" / "novel-aed").exists())

    def test_json_client_is_snippet_only(self):
        plan = setup_mcp.make_plan("json", self.project, self.install_root)
        self.assertEqual(json.loads(plan["snippet"])["mcpServers"]["novel_aed"],
                         setup_mcp.portable_entry(self.entry()))
        with self.assertRaisesRegex(ValueError, "only prints"):
            setup_mcp.apply_plan(plan)

    def test_explicit_runtime_python_and_stories_paths(self):
        runtime = self.temp_root / "영구 runtime with spaces"
        interpreter = runtime / ".venv" / "Scripts" / "python.exe"
        stories = self.temp_root / "사용자 stories with spaces"
        entry = setup_mcp.server_entry(self.install_root, runtime_root=runtime,
                                       python=interpreter, stories_root=stories)
        self.assertEqual(entry["command"], str(interpreter.resolve()))
        self.assertEqual(entry["args"][0], str((runtime / "scripts" / "mcp_server.py").resolve()))
        self.assertEqual(entry["args"][2], str(stories.resolve()))

        plan = setup_mcp.make_plan("claude", self.project, self.install_root,
                                   runtime_root=runtime, python=interpreter, stories_root=stories)
        config = json.loads(plan["snippet"])
        self.assertEqual(config["mcpServers"]["novel_aed"]["command"], str(interpreter.resolve()))
        self.assertEqual(config["mcpServers"]["novel_aed"]["args"][0],
                         str((runtime / "scripts" / "mcp_server.py").resolve()))

    def test_cli_accepts_runtime_python_and_stories_options(self):
        runtime = self.temp_root / "runtime CLI path"
        interpreter = runtime / ".venv" / "Scripts" / "python.exe"
        stories = self.temp_root / "stories CLI path"
        result = subprocess.run([
            sys.executable, str(ROOT / "scripts/setup_mcp.py"),
            "--client", "json", "--runtime-root", str(runtime),
            "--python", str(interpreter), "--stories-root", str(stories),
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = json.loads(result.stdout)["mcpServers"]["novel_aed"]
        self.assertEqual(entry["command"], str(interpreter.resolve()))
        self.assertEqual(entry["args"][0], str((runtime / "scripts" / "mcp_server.py").resolve()))
        self.assertEqual(entry["args"][2], str(stories.resolve()))

    def test_external_project_symlink_is_rejected(self):
        outside = self.temp_root / "outside project config"
        outside.mkdir()
        junction = self.project / ".codex"
        try:
            junction.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Directory symlink unavailable in this environment: {exc}")
        with self.assertRaisesRegex(ValueError, "escapes"):
            setup_mcp._ensure_inside(junction / "config.toml", self.project)

    def test_external_project_junction_is_rejected(self):
        if os.name != "nt":
            self.skipTest("Windows junction check")
        outside = self.temp_root / "outside junction target"
        outside.mkdir()
        junction = self.project / ".codex"
        result = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(junction), str(outside)],
                                capture_output=True, text=True, encoding="utf-8")
        if result.returncode:
            self.skipTest(f"Junction creation unavailable: {result.stderr or result.stdout}")
        try:
            self.assertTrue(junction.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
            with self.assertRaisesRegex(ValueError, "escapes"):
                setup_mcp._ensure_inside(junction / "config.toml", self.project)
        finally:
            junction.rmdir()

    def test_replace_backs_up_config_bytes_and_installed_skill(self):
        canonical = self.install_root / "skills" / "novel-aed"
        canonical.mkdir(parents=True)
        (canonical / "SKILL.md").write_text("new canonical skill\n", encoding="utf-8")

        config_path = self.project / ".codex" / "config.toml"
        config_path.parent.mkdir()
        wrong = copy.deepcopy(self.entry())
        wrong["command"] = "old-server"
        original_config = (
            '[tool]\nkeep = "preserved"\n\n'
            + setup_mcp.render_codex(wrong)
            + '\n\n[mcp_servers.other]\ncommand = "other-server"\n'
        ).encode("utf-8")
        config_path.write_bytes(original_config)

        skill_path = self.project / ".agents" / "skills" / "novel-aed"
        skill_path.mkdir(parents=True)
        (skill_path / "SKILL.md").write_text("old installed skill\n", encoding="utf-8")
        (skill_path / "user-note.txt").write_text("preserve me\n", encoding="utf-8")

        plan = setup_mcp.make_plan("codex", self.project, self.install_root, write=True, replace=True)
        self.assertEqual(len(plan["backup_paths"]), 2)
        backups = setup_mcp.apply_plan(plan)

        config_backup = Path(plan["config_backup_path"])
        skill_backup = Path(plan["skill_backup_path"])
        self.assertIn(config_backup, backups)
        self.assertIn(skill_backup, backups)
        self.assertEqual(config_backup.read_bytes(), original_config)
        self.assertEqual((skill_backup / "SKILL.md").read_text(encoding="utf-8"), "old installed skill\n")
        self.assertEqual((skill_backup / "user-note.txt").read_text(encoding="utf-8"), "preserve me\n")

        parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["tool"]["keep"], "preserved")
        self.assertEqual(parsed["mcp_servers"]["other"]["command"], "other-server")
        self.assertEqual(parsed["mcp_servers"]["novel_aed"], self.entry())
        self.assertEqual((skill_path / "SKILL.md").read_text(encoding="utf-8"), "new canonical skill\n")

    def test_json_replace_backs_up_exact_bytes_and_keeps_other_keys(self):
        canonical = self.install_root / "skills" / "novel-aed"
        canonical.mkdir(parents=True)
        (canonical / "SKILL.md").write_text("canonical\n", encoding="utf-8")
        config_path = self.project / ".mcp.json"
        config_path.write_bytes(
            b'{\n  "keep": {"value": 12},\n  "mcpServers": {\n'
            b'    "novel_aed": {"command": "old", "args": []},\n'
            b'    "other": {"command": "other-server"}\n  }\n}\n'
        )
        original = config_path.read_bytes()

        plan = setup_mcp.make_plan("claude", self.project, self.install_root,
                                   write=True, replace=True)
        backup = Path(plan["config_backup_path"])
        setup_mcp.apply_plan(plan)

        self.assertEqual(backup.read_bytes(), original)
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["keep"], {"value": 12})
        self.assertEqual(parsed["mcpServers"]["other"], {"command": "other-server"})
        self.assertEqual(parsed["mcpServers"]["novel_aed"], setup_mcp.portable_entry(self.entry()))


if __name__ == "__main__":
    unittest.main()
