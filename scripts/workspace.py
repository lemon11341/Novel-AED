"""File-based novel workflow helpers. Standard library only; never calls a model."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from contextlib import contextmanager, closing
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.lib import artifacts, contracts
from workflow.lib.tools import chunk_text


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def fingerprint(root):
    paths = [root / "source.md", root / "preferences.json"]
    paths += sorted((root / "references").rglob("*"))
    h = hashlib.sha256()
    for path in paths:
        if path.is_file():
            h.update(str(path.relative_to(root)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def stage(state):
    if state["pending"]:
        return "awaiting_approval"
    if not state["bible"]:
        return "analysis"
    if not state["plan"]:
        return "outline"
    return "complete" if len(state["chapters"]) == len(state["plan"]["chapters"]) else "chapter"


@contextmanager
def locked(root):
    path = root / ".workflow.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(descriptor)
    try:
        yield
    finally:
        path.unlink()


def create(root, title, source):
    if root.exists():
        raise ValueError("Destination already exists; refusing to overwrite")
    if len(source.strip()) < 30:
        raise ValueError("Source must contain at least 30 characters")
    root.mkdir(parents=True)
    for folder in ("references", "drafts", "history", "chapters"):
        (root / folder).mkdir()
    (root / "source.md").write_text(source, encoding="utf-8")
    write(root / "preferences.json", {"output_language": "source", "count_mode": "recommended",
          "length_mode": "recommended", "preferences": ""})
    state = {"version": 1, "title": title, "revision": 0, "bible": None,
             "plan": None, "chapters": [], "pending": None, "approvals": []}
    state["input_digest"] = fingerprint(root)
    write(root / "state.json", state)
    return state


def project(root, state):
    source = (root / "source.md").read_text(encoding="utf-8-sig")
    return {**state, "source": source, "chunks": chunk_text(source)}


def check_payload(kind, payload, p, prefs):
    value = copy.deepcopy(payload)
    if kind == "analysis":
        contracts.validate(value, contracts.ANALYSIS_SUBMISSION)
        if len(value["parts"]) != len(p["chunks"]):
            raise ValueError("Submit one analysis part for every source chunk, in order")
        parts = [artifacts.analyze_chunk(part, chunk) for part, chunk in zip(value["parts"], p["chunks"])]
        return artifacts.bible(parts, p)
    if kind == "outline":
        return artifacts.plan(value, p, prefs.get("chapters_count"), prefs)
    if kind == "chapter":
        contracts.validate(value, contracts.CHAPTER_SUBMISSION)
        artifacts.draft(value["draft"], p)
        artifacts.review(value["review"], p, value["draft"])
        if value["review"]["verdict"] != "pass":
            raise ValueError("Revise the draft and self-review before submitting")
        return value
    raise ValueError("Unknown stage")


def read_artifact(root, record):
    """Read an immutable workflow artifact, checking its path and content digest."""
    if not isinstance(record, dict):
        raise ValueError("Invalid artifact history record")
    relative = record.get("file")
    match = re.fullmatch(
        r"history/[0-9]{6,}-(analysis|outline|chapter)-([0-9a-f]{64})\.json",
        relative,
    ) if isinstance(relative, str) else None
    if (match is None or match.group(1) != record.get("kind") or
            match.group(2) != record.get("digest")):
        raise ValueError("Artifact history paths must be generated history files matching kind and digest")
    path = root / relative
    for candidate in (root / "history", path):
        if candidate.is_symlink() or getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Artifact history may not contain links or reparse points")
    payload = read(path)
    if artifacts.digest(payload) != record["digest"]:
        raise ValueError("Reviewed artifact changed")
    return payload


def validate_approved_history(root, state, p, prefs):
    """Rebuild accepted state in memory; never rewrite history, approvals or exports."""
    if not isinstance(state["approvals"], list):
        raise ValueError("Approval history must be an array")
    replay = {**p, "bible": None, "plan": None, "chapters": [], "pending": None}
    for record in state["approvals"]:
        if not isinstance(record, dict):
            raise ValueError("Invalid approval history record")
        # Rejection must remain a recovery path for a changed pending artifact.
        if "rejected" in record:
            continue
        if record.get("kind") != stage(replay):
            raise ValueError("Approval history stage sequence is invalid")
        message = record.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Approved artifact is missing its user approval message")
        payload = read_artifact(root, record)
        kind = record["kind"]
        result = check_payload(kind, payload, replay, prefs)
        if kind == "analysis":
            replay["bible"] = result
        elif kind == "outline":
            replay["plan"] = result
        else:
            number = len(replay["chapters"]) + 1
            replay["chapters"].append({"number": number, **result["draft"], "review": result["review"]})
    for field in ("bible", "plan", "chapters"):
        if artifacts.digest(replay[field]) != artifacts.digest(state[field]):
            raise ValueError(f"Approved state differs from recorded artifact history: {field}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("folder", type=Path)
    init.add_argument("--source", required=True, type=Path)
    init.add_argument("--title", required=True)
    export = sub.add_parser("export-legacy")
    export.add_argument("database", type=Path)
    export.add_argument("destination", type=Path)
    for name in ("status", "context", "submit", "approve", "reject", "validate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("folder", type=Path)
        if name in ("submit", "approve", "reject"):
            cmd.add_argument("--revision", required=True, type=int)
        if name == "submit":
            cmd.add_argument("--input", required=True, type=Path)
        if name == "approve":
            cmd.add_argument("--digest", required=True)
            cmd.add_argument("--message", required=True, help="Exact user approval message")
        if name == "reject":
            cmd.add_argument("--reason", required=True)
    args = parser.parse_args()
    if args.command == "init":
        create(args.folder, args.title, args.source.read_text(encoding="utf-8-sig"))
        return
    if args.command == "export-legacy":
        export_legacy(args.database, args.destination)
        return
    result = execute(args.command, args.folder, revision=getattr(args, "revision", None),
                     input_path=getattr(args, "input", None), digest=getattr(args, "digest", None),
                     message=getattr(args, "message", None), reason=getattr(args, "reason", None))
    print("OK" if args.command == "validate" else json.dumps(result, ensure_ascii=False, indent=2))


def validate_preferences(prefs):
    """Validate preferences for both CLI and MCP callers."""
    allowed = {"output_language", "count_mode", "length_mode", "chapters_count", "target_chars", "preferences"}
    if not isinstance(prefs, dict) or set(prefs) - allowed:
        raise ValueError("Unknown preference fields")
    if not isinstance(prefs.get("preferences", ""), str):
        raise ValueError("preferences must be text")
    if prefs.get("output_language") not in ("source", "en", "ko"):
        raise ValueError("Invalid output_language")
    if prefs.get("count_mode") not in ("custom", "recommended") or prefs.get("length_mode") not in ("custom", "recommended"):
        raise ValueError("Invalid count_mode or length_mode")
    if prefs["count_mode"] == "custom" and (type(prefs.get("chapters_count")) is not int or prefs["chapters_count"] < 1):
        raise ValueError("chapters_count must be a positive integer")
    if prefs["length_mode"] == "custom" and (type(prefs.get("target_chars")) is not int or not 100 <= prefs["target_chars"] <= 12000):
        raise ValueError("target_chars must be 100..12000")


def load(root):
    state = read(root / "state.json")
    prefs = read(root / "preferences.json")
    validate_preferences(prefs)
    if fingerprint(root) != state["input_digest"]:
        if state["bible"] or state["pending"] or state["approvals"] or state["plan"] or state["chapters"]:
            raise ValueError("Inputs changed after analysis/submission. Restore inputs or initialize a new story version")
    return state, prefs


def status(state):
    return {"title": state["title"], "revision": state["revision"], "next": stage(state),
            "approved_chapters": len(state["chapters"]), "pending": state["pending"]}


def execute(command, folder, *, revision=None, input_path=None, digest=None, message=None, reason=None):
    """Shared workflow entrypoint. Mutations reload inputs after acquiring the lock."""
    root = Path(folder).resolve()
    if command in ("submit", "approve", "reject"):
        with locked(root):
            state, prefs = load(root)
            if type(revision) is not int or state["revision"] != revision:
                raise ValueError("Stale revision; read status again")
            p = project(root, state)
            if command == "submit":
                kind = stage(state)
                if kind not in ("analysis", "outline", "chapter"):
                    raise ValueError("No submission allowed while awaiting approval or after completion")
                payload = read(input_path)
                check_payload(kind, payload, p, prefs)
                result_digest = artifacts.digest(payload)
                relative = f"history/{state['revision']:06d}-{kind}-{result_digest}.json"
                write(root / relative, payload)
                state["pending"] = {"kind": kind, "file": relative, "digest": result_digest}
            else:
                pending = state["pending"]
                if not pending:
                    raise ValueError("No pending artifact")
                if command == "approve":
                    if digest != pending["digest"] or not isinstance(message, str) or not message.strip():
                        raise ValueError("Approval must identify the reviewed digest and user message")
                    payload = read_artifact(root, pending)
                    result = check_payload(pending["kind"], payload, p, prefs)
                    if pending["kind"] == "analysis":
                        state["bible"] = result
                    elif pending["kind"] == "outline":
                        state["plan"] = result
                    else:
                        number = len(state["chapters"]) + 1
                        state["chapters"].append({"number": number, **result["draft"], "review": result["review"]})
                        (root / "chapters" / f"{number:04d}.md").write_text(result["draft"]["title"] + "\n\n" + result["draft"]["text"], encoding="utf-8")
                    state["approvals"].append({**pending, "message": message, "at": datetime.now(timezone.utc).isoformat()})
                else:
                    if not isinstance(reason, str) or not reason.strip():
                        raise ValueError("A revision reason is required")
                    state["approvals"].append({**pending, "rejected": reason})
                state["pending"] = None
            state["input_digest"] = fingerprint(root)
            state["revision"] += 1
            write(root / "state.json", state)
            return status(state)
    if command not in ("status", "context", "validate"):
        raise ValueError("Unknown workflow command")
    state, prefs = load(root)
    if command == "status":
        return status(state)
    p = project(root, state)
    if command == "context":
        return {"next": stage(state), "project": p, "preferences": prefs,
                "reference_files": [str(f) for f in sorted((root / "references").rglob("*")) if f.is_file()]}
    if command == "validate":
        if state.get("version") != 1 or type(state.get("revision")) is not int or state["revision"] < 0:
            raise ValueError("Invalid state version or revision")
        validate_approved_history(root, state, p, prefs)
        if len(state["chapters"]) > len((state["plan"] or {}).get("chapters", [])):
            raise ValueError("More approved chapters than outlined chapters")
        for number, chapter in enumerate(state["chapters"], 1):
            if chapter["number"] != number:
                raise ValueError("Approved chapter sequence is invalid")
            expected = chapter["title"] + "\n\n" + chapter["text"]
            if (root / "chapters" / f"{number:04d}.md").read_text(encoding="utf-8") != expected:
                raise ValueError("Chapter export differs from approved state")
        if state["pending"]:
            pending = state["pending"]
            expected_kind = stage({**state, "pending": None})
            if not isinstance(pending, dict) or pending.get("kind") != expected_kind:
                raise ValueError("Pending artifact does not match the current workflow stage")
            payload = read_artifact(root, pending)
            check_payload(pending["kind"], payload, p, prefs)
        return {"valid": True, **status(state)}


def export_legacy(database, destination):
    if destination.exists():
        raise ValueError("Export destination already exists")
    # Read-only connection: never initialize or modify the legacy database.
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        projects = [json.loads(row[0]) for row in db.execute("SELECT data FROM projects")]
        jobs = [json.loads(row[0]) for row in db.execute("SELECT data FROM jobs")]
    destination.mkdir(parents=True)
    write(destination / "legacy-export.json", {"projects": projects, "jobs": jobs})
    for index, old in enumerate(projects, 1):
        root = destination / f"story-{index:03d}"
        state = create(root, old["title"], old["source"])
        # Preserve the complete original snapshot; legacy approvals require a user review
        # before being adopted into the new workflow.
        write(root / "legacy-project.json", old)
        write(root / "legacy-jobs.json", [j for j in jobs if j["project_id"] == old["id"]])
        for number, ref in enumerate(old.get("references", []), 1):
            (root / "references" / f"{number:03d}.md").write_text(
                ref["title"] + "\n\n" + ref.get("notes", "") + "\n\n" + ref["text"], encoding="utf-8")
        state["input_digest"] = fingerprint(root)
        write(root / "state.json", state)
    print(f"Exported {len(projects)} stories and {len(jobs)} jobs; original database unchanged")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as exc:
        sys.exit(str(exc))
