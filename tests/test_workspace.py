import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workspace", ROOT / "scripts/workspace.py")
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="novel-aed-workspace-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "story"
        w.create(self.root, "Test", "A traveler reached the locked gate. She carried a key.")

    def command(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/workspace.py"),
                                 args[0], str(self.root), *args[1:]], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def state(self):
        return w.read(self.root / "state.json")

    def submit(self, payload, ok=True):
        path = self.root / "drafts/input.json"
        w.write(path, payload)
        return self.command("submit", "--input", str(path), "--revision", str(self.state()["revision"]), ok=ok)

    def approve(self):
        s = self.state()
        self.command("approve", "--revision", str(s["revision"]), "--digest", s["pending"]["digest"], "--message", "I approve this result")

    def analysis(self):
        return {"parts": [{"summary": "A traveler arrived.", "claims": [{"category": "thread", "subject": "Gate",
                "statement": "The gate is locked", "epistemic": "explicit", "confidence": 1,
                "evidence": [{"chunk_id": "src-0001", "quote": "locked gate"}]}], "unknowns": [], "structure_notes": []}]}

    def outline(self):
        pacing = {k: "Measured" for k in ("pace", "event_density", "story_time", "scene_balance", "tension", "transition")}
        assessment = {k: "Gate opens" for k in ("progress", "pacing_baseline", "recent_pacing", "continuation_strategy", "ending_allocation")}
        assessment.update(open_arcs=["Gate"], evidence=[{"chunk_id": "src-0001", "quote": "locked gate"}], uncertainties=[])
        return {"premise": "Travel", "ending": "Arrival", "chapters": [{"number": 1, "title": "Gate", "goal": "Enter",
                "beats": ["Use key", "Enter"], "canon_ids": ["canon-00001"], "thread_ids": ["canon-00001"],
                "ending": "Home", "pacing": pacing}], "unresolved": [], "narrative_assessment": assessment,
                "length_spec": {"chapters_count": 1, "target_chars": 100, "rationale": "A short ending"}}

    def test_full_workflow_and_approval_gate(self):
        self.submit(self.analysis())
        self.assertIsNone(self.state()["bible"])
        self.submit(self.analysis(), ok=False)
        self.command("approve", "--revision", "1", "--digest", "wrong", "--message", "yes", ok=False)
        self.approve()
        self.assertEqual(w.stage(self.state()), "outline")
        self.submit(self.outline())
        self.approve()
        draft = {"title": "Home", "text": "x" * 100, "state_changes": ["Gate opened"], "resolved_thread_ids": ["canon-00001"]}
        self.submit({"draft": draft, "review": {"verdict": "pass", "issues": [], "rationale": "Checked"}})
        self.approve()
        self.assertEqual(w.stage(self.state()), "complete")
        self.assertTrue((self.root / "chapters/0001.md").exists())
        self.assertEqual(len(self.state()["approvals"]), 3)
        self.command("validate")
        (self.root / "chapters/0001.md").write_text("Changed", encoding="utf-8")
        self.command("validate", ok=False)

    def test_bad_quote_and_missing_chunks(self):
        data = self.analysis()
        data["parts"][0]["claims"][0]["evidence"][0]["quote"] = "invented"
        self.submit(data, ok=False)
        self.submit({"parts": []}, ok=False)
        self.assertEqual(self.state()["revision"], 0)

    def test_stale_revision_tamper_and_changed_inputs(self):
        self.submit(self.analysis())
        self.command("reject", "--revision", "0", "--reason", "Change", ok=False)
        pending = self.state()["pending"]
        artifact = w.read(self.root / pending["file"])
        artifact["parts"][0]["summary"] = "Changed"
        w.write(self.root / pending["file"], artifact)
        self.command("validate", ok=False)
        self.command("approve", "--revision", "1", "--digest", pending["digest"], "--message", "yes", ok=False)
        self.command("reject", "--revision", "1", "--reason", "Change")
        self.submit(self.analysis())
        (self.root / "references/new.md").write_text("New world rule", encoding="utf-8")
        self.command("validate", ok=False)

    def test_bad_length_review_and_canon(self):
        self.submit(self.analysis())
        self.approve()
        data = self.outline()
        data["chapters"][0]["canon_ids"] = ["nonexistent"]
        self.submit(data, ok=False)
        self.submit(self.outline())
        self.approve()
        draft = {"title": "Home", "text": "x" * 101, "state_changes": [], "resolved_thread_ids": []}
        review = {"verdict": "pass", "issues": [], "rationale": "Checked"}
        self.submit({"draft": draft, "review": review}, ok=False)
        draft["text"] = "x" * 100
        review["issues"] = [{"severity": "medium", "category": "pacing", "description": "Rushed", "draft_quote": "xxx", "canon_ids": []}]
        self.submit({"draft": draft, "review": review}, ok=False)

    def test_analysis_submission_envelope_is_strict(self):
        original = (self.root / "state.json").read_bytes()
        invalid_payloads = (
            {**self.analysis(), "unexpected": True},
            {"parts": {}},
            {"parts": [None]},
            [],
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                self.submit(payload, ok=False)
                self.assertEqual((self.root / "state.json").read_bytes(), original)
                self.assertEqual(list((self.root / "history").iterdir()), [])

    def test_chapter_submission_envelope_is_strict(self):
        self.submit(self.analysis())
        self.approve()
        self.submit(self.outline())
        self.approve()
        payload = {
            "draft": {"title": "Home", "text": "x" * 100,
                      "state_changes": [], "resolved_thread_ids": []},
            "review": {"verdict": "pass", "issues": [], "rationale": "Checked"},
            "unexpected": True,
        }
        original = (self.root / "state.json").read_bytes()
        history = sorted(path.name for path in (self.root / "history").iterdir())
        self.submit(payload, ok=False)
        self.assertEqual((self.root / "state.json").read_bytes(), original)
        self.assertEqual(sorted(path.name for path in (self.root / "history").iterdir()), history)

    def test_inputs_stay_frozen_after_first_submission_is_rejected(self):
        self.submit(self.analysis())
        self.command("reject", "--revision", "1", "--reason", "Revise this synthetic analysis")
        self.assertEqual(w.stage(self.state()), "analysis")
        original = (self.root / "state.json").read_bytes()
        with (self.root / "source.md").open("a", encoding="utf-8") as stream:
            stream.write(" An external edit changes this synthetic source.")
        for command in ("status", "validate"):
            with self.subTest(command=command):
                result = self.command(command, ok=False)
                self.assertIn("Inputs changed after analysis/submission", result.stderr)
        self.submit(self.analysis(), ok=False)
        self.assertEqual((self.root / "state.json").read_bytes(), original)

    def test_validate_replays_approved_artifacts_without_mutating_state(self):
        self.submit(self.analysis())
        self.approve()
        self.submit(self.outline())
        self.approve()
        draft = {"title": "Home", "text": "x" * 100,
                 "state_changes": ["Gate opened"], "resolved_thread_ids": ["canon-00001"]}
        self.submit({"draft": draft, "review": {"verdict": "pass", "issues": [], "rationale": "Checked"}})
        self.approve()
        self.command("validate")
        original = self.state()
        mutations = (
            (("bible", "claims", 0, "statement"), "An unapproved claim"),
            (("bible", "claims", 0, "evidence", 0, "start"), 1),
            (("plan", "ending"), "An unapproved ending"),
            (("chapters", 0, "state_changes"), ["An unapproved state change"]),
        )
        for keys, replacement in mutations:
            with self.subTest(keys=keys):
                changed = copy.deepcopy(original)
                target = changed
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = replacement
                w.write(self.root / "state.json", changed)
                before = (self.root / "state.json").read_bytes()
                result = self.command("validate", ok=False)
                self.assertIn("Approved state differs from recorded artifact history", result.stderr)
                self.assertEqual((self.root / "state.json").read_bytes(), before)
        w.write(self.root / "state.json", original)
        self.command("validate")

    def test_validate_detects_changed_approved_history(self):
        self.submit(self.analysis())
        self.approve()
        record = self.state()["approvals"][0]
        path = self.root / record["file"]
        payload = w.read(path)
        payload["parts"][0]["summary"] = "An unreviewed replacement"
        w.write(path, payload)
        original = (self.root / "state.json").read_bytes()
        result = self.command("validate", ok=False)
        self.assertIn("Reviewed artifact changed", result.stderr)
        self.assertEqual((self.root / "state.json").read_bytes(), original)

    def test_approval_requires_immutable_history_path(self):
        self.submit(self.analysis())
        changed = self.state()
        changed["pending"]["file"] = "drafts/input.json"
        w.write(self.root / "state.json", changed)
        original = (self.root / "state.json").read_bytes()
        result = self.command(
            "approve", "--revision", str(changed["revision"]),
            "--digest", changed["pending"]["digest"],
            "--message", "I approve this synthetic result", ok=False,
        )
        self.assertIn("generated history files", result.stderr)
        self.assertEqual((self.root / "state.json").read_bytes(), original)
        self.assertIsNone(self.state()["bible"])

    def test_rejecting_changed_pending_artifact_preserves_recovery(self):
        self.submit(self.analysis())
        pending = self.state()["pending"]
        path = self.root / pending["file"]
        payload = w.read(path)
        payload["parts"][0]["summary"] = "Changed after submission"
        w.write(path, payload)
        self.command("reject", "--revision", "1", "--reason", "Reject the changed synthetic result")
        self.submit(self.analysis())
        self.approve()
        self.command("validate")
        state = self.state()
        self.assertEqual(len(state["approvals"]), 2)
        self.assertIn("rejected", state["approvals"][0])
        self.assertEqual(state["bible"]["summaries"][0]["summary"], "A traveler arrived.")

    def test_lock_and_legacy_export(self):
        with w.locked(self.root):
            self.submit(self.analysis(), ok=False)
        self.submit(self.analysis())
        import sqlite3
        db_path = Path(self.temp.name) / "old.sqlite3"
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE projects (data TEXT)")
            db.execute("CREATE TABLE jobs (data TEXT)")
            old = {"id": "old", "title": "Old", "source": "A long source story that must be fully preserved.", "references": []}
            db.execute("INSERT INTO projects VALUES (?)", (json.dumps(old),))
        db.close()
        before = db_path.read_bytes()
        destination = Path(self.temp.name) / "export"
        w.export_legacy(db_path, destination)
        self.assertEqual(db_path.read_bytes(), before)
        self.assertEqual(w.read(destination / "story-001/legacy-project.json"), old)


if __name__ == "__main__":
    unittest.main()
