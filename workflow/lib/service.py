"""Transport-independent, confined operations for the Novel AED MCP server."""
import json
import re
from pathlib import Path

from scripts import workspace as w
from . import contracts as c
from .tools import chunk_text

ROOT = Path(__file__).resolve().parents[2]


def confined(base, relative):
    """Accept portable relative paths only; reject links and Windows aliases/ADS."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Use a nonempty relative path with forward slashes")
    parts = relative.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in parts:
        if (part in ("", ".", "..") or part[-1:] in (" ", ".") or
                any(ord(ch) < 32 or ch in '<>:"|?*' for ch in part) or
                part.split(".")[0].upper() in reserved):
            raise ValueError("Invalid relative path")
    base = Path(base).resolve()
    target = base.joinpath(*parts)
    current = base
    for part in parts:
        current = current / part
        if current.exists() or current.is_symlink():
            attributes = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attributes & 0x400:
                raise ValueError("Links and reparse points are not supported")
    if not target.resolve().is_relative_to(base):
        raise ValueError("Path escapes the stories root")
    return target


def check_tree(folder):
    """Do not let CLI internals follow links in story-owned state or exports."""
    if not folder.exists():
        return
    for child in folder.iterdir():
        safe = confined(folder, child.name)
        if safe.is_dir():
            check_tree(safe)


def page(items, offset, limit, maximum=50):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= maximum:
        raise ValueError(f"offset must be nonnegative; limit must be 1..{maximum}")
    end = min(offset + limit, len(items))
    return {"items": items[offset:end], "total": len(items),
            "next_offset": end if end < len(items) else None}


def guidance(topic):
    if topic in ("analysis", "outline", "chapter"):
        if topic == "analysis":
            schema = c.ANALYSIS_SUBMISSION
            heading = "Analysis"
        elif topic == "outline":
            schema, heading = c.plan_schema({"length_mode": "recommended"}), "Outline"
        else:
            schema, heading = c.CHAPTER_SUBMISSION, "Writing"
        stages = (ROOT / "workflow/STAGES.md").read_text(encoding="utf-8")
        common = stages.split("## Common rules\n", 1)[1].split("\n## ", 1)[0]
        instructions = stages.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
        if topic == "chapter":
            instructions += "\n" + stages.split("## Self-review\n", 1)[1].split("\n## ", 1)[0]
        return {"topic": topic, "instructions": common + "\n" + instructions, "schema": schema}
    paths = {"workflow": "workflow/WORKFLOW.md", "rules": "AGENTS.md", "skill": "skills/novel-aed/SKILL.md"}
    if topic not in paths:
        raise ValueError("topic must be workflow, rules, skill, analysis, outline or chapter")
    return {"topic": topic, "instructions": (ROOT / paths[topic]).read_text(encoding="utf-8")}


class StoryService:
    def __init__(self, stories_root):
        self.root = Path(stories_root).resolve()

    def story(self, story):
        folder = confined(self.root, story)
        if not (folder / "state.json").is_file():
            raise ValueError("Unknown story; call list_stories or initialize_story")
        check_tree(folder)
        state = w.read(folder / "state.json")
        if state.get("pending"):
            pending = state["pending"]["file"]
            if not pending.startswith("history/"):
                raise ValueError("Pending artifact must be in history/")
            confined(folder, pending)
        return folder

    def list_stories(self, offset=0, limit=20):
        entries = []
        folders = [self.root] if self.root.is_dir() else []
        while folders:
            parent = folders.pop()
            for child in sorted(parent.iterdir()):
                child = confined(parent, child.name)
                if not child.is_dir():
                    continue
                story = child.relative_to(self.root).as_posix()
                if (child / "state.json").is_file():
                    try:
                        entries.append({"story": story, **w.execute("status", self.story(story))})
                    except (ValueError, KeyError, OSError, TypeError) as exc:
                        entries.append({"story": story, "error": str(exc)})
                else:
                    folders.append(child)
        return page(sorted(entries, key=lambda item: item["story"]), offset, limit)

    def initialize(self, story, title, source_text):
        if not title.strip():
            raise ValueError("A title is required")
        folder = confined(self.root, story)
        # Existing ancestor stories must not acquire nested story workspaces.
        if any((parent / "state.json").exists() for parent in folder.parents if parent.is_relative_to(self.root)):
            raise ValueError("Cannot initialize inside another story")
        w.create(folder, title, source_text)
        return {"story": story, **w.execute("status", folder)}

    def status(self, story):
        return {"story": story, **w.execute("status", self.story(story))}

    def context(self, story, offset=0, limit=50):
        folder = self.story(story)
        state, prefs = w.load(folder)
        chunks = chunk_text((folder / "source.md").read_text(encoding="utf-8-sig"))
        files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")
                       if p.is_file() and self.readable(p.relative_to(folder).as_posix()))
        return {"story": story, **w.status(state), "preferences": prefs,
                "source_chunks": len(chunks), "source_characters": sum(len(x["text"]) for x in chunks),
                "files": page(files, offset, limit),
                "approved_analysis": bool(state["bible"]), "approved_outline": bool(state["plan"]),
                "notice": "File names are an inventory, not proof their contents have been read. Read legacy records before continuing imported stories."}

    def source_chunk(self, story, chunk_id):
        folder = self.story(story)
        w.load(folder)
        for chunk in chunk_text((folder / "source.md").read_text(encoding="utf-8-sig")):
            if chunk["id"] == chunk_id:
                return chunk
        raise ValueError("Unknown source chunk ID")

    @staticmethod
    def readable(path):
        return (path in ("source.md", "preferences.json", "legacy-project.json", "legacy-jobs.json") or
                (path.split("/")[0] in ("references", "drafts", "history", "chapters") and
                 Path(path).suffix.lower() in (".json", ".md", ".txt")))

    def read_file(self, story, path, offset=0, limit=12000):
        folder = self.story(story)
        w.load(folder)
        target = confined(folder, path)
        if not self.readable(path):
            raise ValueError("File is not a readable story document; use read_approved for approved state")
        text = target.read_text(encoding="utf-8-sig")
        result = page(text, offset, limit, maximum=20000)
        return {"path": path, "text": result.pop("items"), "offset": offset, **result}

    def approved(self, story, section, offset=0, limit=10):
        state, _ = w.load(self.story(story))
        if section in ("summaries", "claims", "unknowns", "structure_notes"):
            return {"section": section, **page((state["bible"] or {}).get(section, []), offset, limit)}
        if section == "outline":
            outline = state["plan"] or {}
            return {"section": section, "metadata": {k: v for k, v in outline.items() if k != "chapters"},
                    **page(outline.get("chapters", []), offset, limit)}
        if section in ("chapters", "approvals"):
            return {"section": section, **page(state[section], offset, limit, maximum=10)}
        raise ValueError("Unknown approved context section")

    @staticmethod
    def revision(state, revision):
        if type(revision) is not int or state["revision"] != revision:
            raise ValueError("Stale revision; read status again")

    def configure(self, story, revision, preferences=None, reference_name=None, text=None, scope=None):
        folder = self.story(story)
        with w.locked(folder):
            state, _ = w.load(folder)
            self.revision(state, revision)
            if state["bible"] or state["pending"] or state["approvals"] or state["plan"] or state["chapters"]:
                raise ValueError("Inputs are frozen after submission; initialize a new story version")
            if preferences is not None:
                w.validate_preferences(preferences)
                w.write(folder / "preferences.json", preferences)
            else:
                if not scope or not scope.strip() or not text or not text.strip():
                    raise ValueError("Reference text and applicability scope are required")
                target = confined(folder / "references", reference_name)
                if target.suffix != ".md" or "/" in reference_name:
                    raise ValueError("Use a single .md reference filename")
                with target.open("x", encoding="utf-8") as stream:
                    stream.write(f"Applicability / 적용 범위: {scope}\n\n{text}")
            state["input_digest"] = w.fingerprint(folder)
            state["revision"] += 1
            w.write(folder / "state.json", state)
            return w.status(state)

    def draft_path(self, folder, name):
        path = confined(folder / "drafts", name)
        if not re.fullmatch(r"[^/]+\.json", name):
            raise ValueError("Use a single .json draft filename")
        return path

    def save_draft(self, story, name, payload, revision):
        folder = self.story(story)
        with w.locked(folder):
            state, _ = w.load(folder)
            self.revision(state, revision)
            if w.stage(state) not in ("analysis", "outline", "chapter"):
                raise ValueError("Drafts are frozen while awaiting approval or after completion")
            # Draft writes consume a revision too, so two clients cannot silently overwrite one another.
            path = self.draft_path(folder, name)
            json.dumps(payload, allow_nan=False)
            w.write(path, payload)
            state["revision"] += 1
            state["input_digest"] = w.fingerprint(folder)
            w.write(folder / "state.json", state)
            return {"file": f"drafts/{name}", "digest": w.artifacts.digest(payload), **w.status(state)}

    def assemble(self, story, name, kind, part_names, header, revision):
        folder = self.story(story)
        # Saving is the sole mutation and rechecks revision under the shared lock.
        if kind == "analysis":
            if header:
                raise ValueError("Analysis assembly does not use a header")
            payload = {"parts": [w.read(self.draft_path(folder, part)) for part in part_names]}
        elif kind == "outline":
            if "chapters" in header:
                raise ValueError("Outline header must omit chapters")
            payload = {**header, "chapters": []}
            for part in part_names:
                payload["chapters"].extend(w.read(self.draft_path(folder, part))["chapters"])
        else:
            raise ValueError("Assembly kind must be analysis or outline")
        return self.save_draft(story, name, payload, revision)

    def submit(self, story, name, revision):
        folder = self.story(story)
        return w.execute("submit", folder, revision=revision, input_path=self.draft_path(folder, name))

    def approve(self, story, revision, digest, message):
        return w.execute("approve", self.story(story), revision=revision, digest=digest, message=message)

    def reject(self, story, revision, reason):
        return w.execute("reject", self.story(story), revision=revision, reason=reason)

    def validate(self, story):
        return w.execute("validate", self.story(story))
