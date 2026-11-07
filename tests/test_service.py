from pathlib import Path
import tempfile
import unittest

from scripts import workspace as w
from workflow.lib.service import StoryService


SOURCE = "A traveler reached the locked gate. She carried a key."


class StoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="novel-aed-service-")
        self.addCleanup(self.temp.cleanup)
        self.stories_root = Path(self.temp.name)
        self.service = StoryService(self.stories_root)
        self.story = "story"
        self.initial = self.service.initialize(self.story, "Synthetic test", SOURCE)
        self.folder = self.stories_root / self.story

    def state(self):
        return w.read(self.folder / "state.json")

    @staticmethod
    def claim(category, subject, statement, quote):
        return {
            "category": category,
            "subject": subject,
            "statement": statement,
            "epistemic": "explicit",
            "confidence": 1,
            "evidence": [{"chunk_id": "src-0001", "quote": quote}],
        }

    @classmethod
    def analysis_part(cls, *, first_quote="locked gate"):
        return {
            "summary": "A traveler arrives at a locked gate carrying a key.",
            "claims": [
                cls.claim("thread", "Gate", "The gate is locked.", first_quote),
                cls.claim("event", "Traveler", "The traveler carries a key.", "key"),
            ],
            "unknowns": [],
            "structure_notes": [],
        }

    @classmethod
    def analysis_payload(cls):
        return {"parts": [cls.analysis_part()]}

    @staticmethod
    def outline_payload():
        pacing = {key: "Measured" for key in (
            "pace", "event_density", "story_time", "scene_balance", "tension", "transition"
        )}
        chapters = [
            {
                "number": 1,
                "title": "The locked gate",
                "goal": "Reach the gate",
                "beats": ["Approach the gate", "Inspect the lock"],
                "canon_ids": ["canon-00001"],
                "thread_ids": ["canon-00001"],
                "ending": "The traveler studies the lock.",
                "pacing": dict(pacing),
            },
            {
                "number": 2,
                "title": "The key",
                "goal": "Use the key",
                "beats": ["Take out the key", "Open the gate"],
                "canon_ids": ["canon-00002"],
                "thread_ids": [],
                "ending": "The gate opens.",
                "pacing": dict(pacing),
            },
        ]
        assessment = {
            "progress": "The traveler has reached the gate.",
            "open_arcs": ["The locked gate"],
            "pacing_baseline": "Measured.",
            "recent_pacing": "Measured.",
            "continuation_strategy": "Use the key to resolve the obstacle.",
            "ending_allocation": "Resolve the gate within two chapters.",
            "evidence": [{"chunk_id": "src-0001", "quote": "locked gate"}],
            "uncertainties": [],
        }
        return {
            "premise": "A traveler reaches a locked gate with a key.",
            "ending": "The traveler passes through the gate.",
            "chapters": chapters,
            "unresolved": [],
            "narrative_assessment": assessment,
            "length_spec": {
                "chapters_count": len(chapters),
                "target_chars": 200,
                "rationale": "Two short chapters resolve the immediate obstacle.",
            },
        }

    @staticmethod
    def preferences():
        return {
            "output_language": "source",
            "count_mode": "recommended",
            "length_mode": "recommended",
            "preferences": "Keep the supplied source wording intact.",
        }

    def submit_analysis(self, name="analysis.json"):
        saved = self.service.save_draft(
            self.story, name, self.analysis_payload(), self.state()["revision"]
        )
        return self.service.submit(self.story, name, saved["revision"])

    def approve_pending(self, message="I approve this synthetic result."):
        state = self.state()
        return self.service.approve(
            self.story, state["revision"], state["pending"]["digest"], message
        )

    def test_initialize_list_and_status(self):
        self.assertEqual(self.initial["story"], self.story)
        self.assertEqual(self.initial["revision"], 0)
        self.assertEqual(self.initial["next"], "analysis")

        status = self.service.status(self.story)
        self.assertEqual(status["story"], self.story)
        self.assertEqual(status["title"], "Synthetic test")
        self.assertEqual(status["revision"], 0)
        self.assertEqual(status["next"], "analysis")
        self.assertIsNone(status["pending"])

        self.service.initialize("z-story", "Another synthetic test", SOURCE)
        first = self.service.list_stories(limit=1)
        self.assertEqual(first["total"], 2)
        self.assertEqual([item["story"] for item in first["items"]], ["story"])
        self.assertEqual(first["next_offset"], 1)
        second = self.service.list_stories(offset=first["next_offset"], limit=1)
        self.assertEqual([item["story"] for item in second["items"]], ["z-story"])
        self.assertIsNone(second["next_offset"])

    def test_configure_preferences_and_reference_updates_revision_before_submission(self):
        preferences = self.preferences()
        configured = self.service.configure(self.story, 0, preferences=preferences)
        self.assertEqual(configured["revision"], 1)
        self.assertEqual(w.read(self.folder / "preferences.json"), preferences)

        configured = self.service.configure(
            self.story,
            1,
            reference_name="world.md",
            scope="Applies to the entire synthetic test story",
            text="The gate opens when the traveler uses the key.",
        )
        self.assertEqual(configured["revision"], 2)
        reference = (self.folder / "references/world.md").read_text(encoding="utf-8")
        self.assertIn("Applicability / 적용 범위: Applies to the entire synthetic test story", reference)
        self.assertIn("The gate opens when the traveler uses the key.", reference)
        self.assertEqual(self.state()["input_digest"], w.fingerprint(self.folder))

    def test_draft_revision_assembly_submission_digest_and_approval(self):
        part = self.analysis_part()
        first = self.service.save_draft(self.story, "part-1.json", part, 0)
        self.assertEqual(first["revision"], 1)
        with self.assertRaisesRegex(ValueError, "Stale revision"):
            self.service.save_draft(self.story, "part-1.json", part, 0)

        assembled = self.service.assemble(
            self.story, "analysis.json", "analysis", ["part-1.json"], {}, first["revision"]
        )
        self.assertEqual(assembled["revision"], 2)
        self.assertEqual(w.read(self.folder / "drafts/analysis.json"), {"parts": [part]})

        pending_status = self.service.submit(self.story, "analysis.json", assembled["revision"])
        self.assertEqual(pending_status["revision"], 3)
        self.assertEqual(pending_status["next"], "awaiting_approval")
        pending = self.state()["pending"]
        self.assertEqual(pending["kind"], "analysis")
        self.assertTrue(pending["file"].startswith("history/"))

        with self.assertRaisesRegex(ValueError, "reviewed digest"):
            self.service.approve(self.story, 3, "0" * 64, "I approve this result.")
        self.assertEqual(self.state()["revision"], 3)
        self.assertIsNotNone(self.state()["pending"])

        approved = self.approve_pending("I approve the reviewed synthetic analysis.")
        self.assertEqual(approved["revision"], 4)
        self.assertEqual(approved["next"], "outline")
        claims = self.service.approved(self.story, "claims", limit=1)
        self.assertEqual(claims["total"], 2)
        self.assertEqual(len(claims["items"]), 1)
        self.assertEqual(claims["next_offset"], 1)
        next_claim = self.service.approved(self.story, "claims", offset=1, limit=1)
        self.assertEqual(next_claim["items"][0]["id"], "canon-00002")
        self.assertIsNone(next_claim["next_offset"])

        outline = self.outline_payload()
        outline_draft = self.service.save_draft(self.story, "outline.json", outline, 4)
        submitted = self.service.submit(self.story, "outline.json", outline_draft["revision"])
        self.assertEqual(submitted["next"], "awaiting_approval")
        approved_outline = self.approve_pending("I approve the reviewed synthetic outline.")
        self.assertEqual(approved_outline["next"], "chapter")
        first_outline_page = self.service.approved(self.story, "outline", limit=1)
        self.assertEqual(first_outline_page["total"], 2)
        self.assertEqual(first_outline_page["items"][0]["number"], 1)
        self.assertEqual(first_outline_page["next_offset"], 1)
        second_outline_page = self.service.approved(self.story, "outline", offset=1, limit=1)
        self.assertEqual(second_outline_page["items"][0]["number"], 2)
        self.assertEqual(second_outline_page["next_offset"], None)

    def test_pending_submission_blocks_drafts_submit_and_configure(self):
        submitted = self.submit_analysis()
        self.assertEqual(submitted["next"], "awaiting_approval")
        revision = self.state()["revision"]

        with self.assertRaisesRegex(ValueError, "Drafts are frozen"):
            self.service.save_draft(self.story, "another.json", self.analysis_payload(), revision)
        with self.assertRaisesRegex(ValueError, "No submission allowed"):
            self.service.submit(self.story, "analysis.json", revision)
        with self.assertRaisesRegex(ValueError, "Inputs are frozen"):
            self.service.configure(self.story, revision, preferences=self.preferences())
        self.assertEqual(self.state()["revision"], revision)
        self.assertIsNotNone(self.state()["pending"])

    def test_source_chunks_reassemble_exactly_and_file_reads_are_paged(self):
        source = "".join(
            f"Entry {index:04d}: a traveler follows the river toward a distant locked gate.\n"
            for index in range(450)
        )
        self.service.initialize("long-source", "Long synthetic source", source)
        context = self.service.context("long-source", offset=0, limit=1)
        self.assertEqual(context["source_characters"], len(source))
        self.assertGreater(context["source_chunks"], 1)
        self.assertEqual(context["files"]["total"], 2)
        self.assertEqual(len(context["files"]["items"]), 1)
        self.assertEqual(context["files"]["next_offset"], 1)

        ids = [f"src-{number:04d}" for number in range(1, context["source_chunks"] + 1)]
        chunks = [self.service.source_chunk("long-source", chunk_id) for chunk_id in ids]
        self.assertEqual("".join(chunk["text"] for chunk in chunks), source)
        self.assertEqual(chunks[0]["start"], 0)
        self.assertEqual(chunks[-1]["end"], len(source))
        for left, right in zip(chunks, chunks[1:]):
            self.assertEqual(left["end"], right["start"])

        offset, limit = 37, 29
        page = self.service.read_file("long-source", "source.md", offset=offset, limit=limit)
        self.assertEqual("".join(page["text"]), source[offset:offset + limit])
        self.assertEqual(page["offset"], offset)
        self.assertEqual(page["next_offset"], offset + limit)
        final = self.service.read_file(
            "long-source", "source.md", offset=page["next_offset"], limit=limit
        )
        self.assertEqual("".join(final["text"]), source[offset + limit:offset + 2 * limit])

    def test_path_alias_traversal_and_protected_state_are_rejected(self):
        absolute = Path("C:/outside/story").as_posix()
        invalid_story_ids = (
            "../outside",
            "nested/../../outside",
            absolute,
            "CON",
            "notes/NUL.txt",
            "COM1.json",
            "file.md:secret",
            "trailing.",
            "trailing ",
        )
        for story_id in invalid_story_ids:
            with self.subTest(story_id=story_id), self.assertRaises(ValueError):
                self.service.initialize(story_id, "Unsafe", SOURCE)

        invalid_files = (
            "../../state.json",
            absolute,
            "drafts/part.json:stream",
            "CON.txt",
            "nested/NUL.md",
        )
        for path in invalid_files:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.service.read_file(self.story, path)

        original_state = (self.folder / "state.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "readable story document"):
            self.service.read_file(self.story, "state.json")
        with self.assertRaisesRegex(ValueError, "Invalid relative path"):
            self.service.save_draft(self.story, "../state.json", self.analysis_payload(), 0)
        self.assertEqual((self.folder / "state.json").read_bytes(), original_state)

    def test_bad_original_quote_and_changed_input_fingerprint_are_rejected(self):
        invalid = {"parts": [self.analysis_part(first_quote="a quote absent from source")]}
        saved = self.service.save_draft(self.story, "bad-analysis.json", invalid, 0)
        with self.assertRaisesRegex(ValueError, "원문에 없는 근거 인용"):
            self.service.submit(self.story, "bad-analysis.json", saved["revision"])
        self.assertIsNone(self.state()["pending"])

        self.submit_analysis()
        self.approve_pending()
        with (self.folder / "source.md").open("a", encoding="utf-8") as source_file:
            source_file.write(" An external edit changes the source fingerprint.")
        with self.assertRaisesRegex(ValueError, "Inputs changed after analysis/submission"):
            self.service.validate(self.story)

    def test_submission_envelope_error_preserves_saved_revision(self):
        payload = {**self.analysis_payload(), "unexpected": True}
        saved = self.service.save_draft(self.story, "invalid-envelope.json", payload, 0)
        original = (self.folder / "state.json").read_bytes()
        with self.assertRaises(ValueError):
            self.service.submit(self.story, "invalid-envelope.json", saved["revision"])
        self.assertEqual((self.folder / "state.json").read_bytes(), original)
        self.assertIsNone(self.state()["pending"])
        self.assertEqual(list((self.folder / "history").iterdir()), [])

    def test_rejected_first_submission_keeps_inputs_frozen(self):
        submitted = self.submit_analysis()
        rejected = self.service.reject(
            self.story, submitted["revision"], "Revise this synthetic analysis."
        )
        self.assertEqual(rejected["next"], "analysis")
        self.assertIsNone(self.state()["bible"])
        original = (self.folder / "state.json").read_bytes()

        with self.assertRaisesRegex(ValueError, "Inputs are frozen"):
            self.service.configure(
                self.story, rejected["revision"], preferences=self.preferences()
            )
        (self.folder / "references/new.md").write_text(
            "An external change to a synthetic reference.", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "Inputs changed after analysis/submission"):
            self.service.status(self.story)
        self.assertEqual((self.folder / "state.json").read_bytes(), original)

    def test_symlink_in_story_tree_is_rejected_when_creation_is_available(self):
        target = self.stories_root / "outside.md"
        target.write_text("This file is outside the story folder.", encoding="utf-8")
        link = self.folder / "references" / "outside.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlink creation is unavailable: {exc}")

        with self.assertRaisesRegex(ValueError, "Links and reparse points"):
            self.service.status(self.story)


if __name__ == "__main__":
    unittest.main()
