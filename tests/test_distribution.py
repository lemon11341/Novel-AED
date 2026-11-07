"""Focused tests for source packaging and the persistent runtime installer."""
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
STORIES = ROOT / "stories"
SCRIPTS = ROOT / "scripts"

# The installer and verifier import the shared module as ``distribution``.
scripts_path = str(SCRIPTS)
added_scripts_path = scripts_path not in sys.path
if added_scripts_path:
    sys.path.insert(0, scripts_path)
try:
    distribution = importlib.import_module("distribution")
    install_runtime = importlib.import_module("install_runtime")
    verify_package = importlib.import_module("verify_package")
finally:
    if added_scripts_path:
        sys.path.remove(scripts_path)


def add_file(archive, name, content):
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(content))


def write_tarball(path, files, extra_files=(), extra_members=()):
    with tarfile.open(path, "w:gz") as archive:
        root = tarfile.TarInfo("package/")
        root.type = tarfile.DIRTYPE
        root.mode = 0o755
        archive.addfile(root)
        for name, content in files.items():
            add_file(archive, f"package/{name}", content)
        for name, content in extra_files:
            add_file(archive, name, content)
        for member in extra_members:
            archive.addfile(member)


class DistributionTests(unittest.TestCase):
    def source_files(self):
        return distribution.package_files(ROOT)

    def test_source_allowlist_includes_runtime_schema_and_skill_only(self):
        files = self.source_files()

        self.assertIn("scripts/install_runtime.py", files)
        self.assertIn("workflow/schemas/analysis.json", files)
        self.assertIn("skills/novel-aed/SKILL.md", files)
        for forbidden in (
            "stories/user/state.json",
            "data/private.json",
            ".venv/pyvenv.cfg",
            ".git/config",
            "tests/test_distribution.py",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(distribution.allowed(forbidden))
                self.assertNotIn(forbidden, files)

    def test_archive_rejects_story_data(self):
        files = self.source_files()
        with tempfile.TemporaryDirectory(prefix="distribution-test-", dir=STORIES) as temp:
            archive = Path(temp) / "malicious.tgz"
            write_tarball(
                archive,
                files,
                extra_files=(("package/stories/secret.md", b"private manuscript"),),
            )

            with self.assertRaisesRegex(ValueError, "Forbidden, duplicate or oversized"):
                verify_package.verify_archive(archive)

    def test_archive_rejects_traversal_symlink_and_duplicate_entries(self):
        files = self.source_files()
        with tempfile.TemporaryDirectory(prefix="distribution-test-", dir=STORIES) as temp:
            temp_path = Path(temp)
            cases = (
                (
                    "traversal",
                    (("package/../escape.txt", b"escape"),),
                    (),
                ),
                (
                    "symlink",
                    (),
                    (self._symlink_member(),),
                ),
                (
                    "duplicate",
                    (("package/README.md", files["README.md"]),),
                    (),
                ),
            )
            for label, extra_files, extra_members in cases:
                with self.subTest(entry=label):
                    archive = temp_path / f"{label}.tgz"
                    write_tarball(archive, files, extra_files, extra_members)
                    with self.assertRaises(ValueError):
                        verify_package.verify_archive(archive)

    @staticmethod
    def _symlink_member():
        info = tarfile.TarInfo("package/readme-link")
        info.type = tarfile.SYMTYPE
        info.linkname = "README.md"
        return info

    def test_archive_rejects_missing_required_file(self):
        files = self.source_files()
        missing = sorted(distribution.REQUIRED)[0]
        del files[missing]

        with tempfile.TemporaryDirectory(prefix="distribution-test-", dir=STORIES) as temp:
            archive = Path(temp) / "missing.tgz"
            write_tarball(archive, files)

            with self.assertRaisesRegex(ValueError, "Missing release files"):
                verify_package.verify_archive(archive)

    def test_actual_source_payload_verifies_as_a_tarball(self):
        files = self.source_files()
        with tempfile.TemporaryDirectory(prefix="distribution-test-", dir=STORIES) as temp:
            archive = Path(temp) / "novel-aed-source.tgz"
            write_tarball(archive, files)

            result = verify_package.verify_archive(archive)

        self.assertEqual(result["version"], distribution.metadata(files)["version"])
        self.assertEqual(result["files"], len(files))
        self.assertEqual(result["private_data"], "excluded")

    def test_runtime_plan_is_side_effect_free_and_readiness_checks_payload(self):
        files = self.source_files()
        with tempfile.TemporaryDirectory(prefix="distribution-test-", dir=STORIES) as temp:
            home = Path(temp) / "runtime-home"
            initial = install_runtime.runtime_plan(home)

            self.assertFalse(initial["ready"])
            self.assertFalse(home.exists())

            runtime = Path(initial["runtime_root"])
            for name, content in files.items():
                target = runtime / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)

            self.assertFalse(install_runtime.runtime_plan(home)["ready"])

            python = Path(initial["python"])
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b"test-only fake python executable")
            marker = runtime / ".ready.json"
            marker.write_text(json.dumps({"version": initial["version"], "sha256": "wrong"}), encoding="utf-8")
            self.assertFalse(install_runtime.runtime_plan(home)["ready"])

            marker.write_text(
                json.dumps({"version": initial["version"], "sha256": initial["sha256"]}),
                encoding="utf-8",
            )
            self.assertTrue(install_runtime.runtime_plan(home)["ready"])

            (runtime / "README.md").write_bytes(files["README.md"] + b"\ntampered")
            self.assertFalse(install_runtime.runtime_plan(home)["ready"])

    def test_existing_install_lock_refuses_without_subprocess_or_story_changes(self):
        with tempfile.TemporaryDirectory(prefix="distribution-test-", dir=STORIES) as temp:
            home = Path(temp) / "runtime-home"
            plan = install_runtime.runtime_plan(home)
            home.mkdir()
            lock = home / ".install.lock"
            lock.write_text("active setup", encoding="utf-8")
            lock_before = lock.read_bytes()
            story = home / "stories" / "saved-state.json"
            story.parent.mkdir()
            story.write_bytes(b"preserve this user data")

            with patch.object(install_runtime.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "Installation is locked"):
                    install_runtime.install(plan)

            run.assert_not_called()
            self.assertEqual(lock.read_bytes(), lock_before)
            self.assertEqual(story.read_bytes(), b"preserve this user data")
            self.assertFalse(Path(plan["runtime_root"]).exists())


if __name__ == "__main__":
    unittest.main()
