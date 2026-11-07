"""Print or install the Novel AED MCP client configuration."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
import uuid
import tomllib


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATHS = {
    "codex": Path(".codex/config.toml"),
    "claude": Path(".mcp.json"),
    "cursor": Path(".cursor/mcp.json"),
}
SKILL_PATHS = {
    "codex": Path(".agents/skills/novel-aed"),
    "claude": Path(".claude/skills/novel-aed"),
    "cursor": Path(".cursor/skills/novel-aed"),
}


def server_entry(root=ROOT, *, stories_root=None, python=None, runtime_root=None):
    """Return the MCP server configuration using absolute paths."""
    root = Path(root).resolve()
    server_root = Path(runtime_root).resolve() if runtime_root is not None else root
    stories = Path(stories_root).resolve() if stories_root is not None else (root / "stories").resolve()
    if os.name == "nt":
        local_python = server_root / ".venv" / "Scripts" / "python.exe"
    else:
        local_python = server_root / ".venv" / "bin" / "python"
    if python is not None:
        python = Path(python).resolve()
    else:
        python = local_python if local_python.is_file() else Path(sys.executable).resolve()
    return {
        "command": str(python),
        "args": [
            str((server_root / "scripts" / "mcp_server.py").resolve()),
            "--stories-root",
            str(stories),
        ],
        "startup_timeout_sec": 30,
        "tool_timeout_sec": 120,
    }


def _toml_string(value):
    # JSON basic strings use the same escaping needed by these TOML values.
    return json.dumps(value, ensure_ascii=False)


def render_codex(entry):
    lines = [
        "[mcp_servers.novel_aed]",
        f"command = {_toml_string(entry['command'])}",
        "args = [",
        *(f"  {_toml_string(arg)}," for arg in entry["args"]),
        "]",
        f"startup_timeout_sec = {entry['startup_timeout_sec']}",
        f"tool_timeout_sec = {entry['tool_timeout_sec']}",
    ]
    return "\n".join(lines)


def portable_entry(entry):
    """Return fields supported by portable JSON MCP client configurations."""
    return {key: entry[key] for key in ("command", "args")}


def render_json(entry):
    return json.dumps({"mcpServers": {"novel_aed": portable_entry(entry)}}, ensure_ascii=False, indent=2)


_CODEX_TARGET_HEADER = re.compile(
    r"^\s*\[\s*mcp_servers\s*\.\s*novel_aed(?P<suffix>(?:\s*\.\s*[A-Za-z0-9_-]+\s*)*)\s*\]\s*(?:#.*)?$"
)


def _toml_config(text):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Existing Codex TOML is invalid: {exc}") from exc


def _json_config(text):
    if not text.strip():
        return {}
    try:
        current = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Existing MCP JSON is invalid: {exc}") from exc
    if not isinstance(current, dict):
        raise ValueError("Existing MCP JSON root must be an object")
    return current


def _existing_server_entry(client, text):
    if client == "codex":
        current = _toml_config(text)
        servers = current.get("mcp_servers", {})
    else:
        current = _json_config(text)
        servers = current.get("mcpServers", {})
    if not isinstance(servers, dict):
        name = "mcp_servers" if client == "codex" else "mcpServers"
        raise ValueError(f"Existing {name} setting is not a table/object")
    if "novel_aed" in servers:
        return True, servers["novel_aed"]
    return False, None


def _is_toml_header(line):
    if not line.lstrip().startswith("["):
        return False
    try:
        tomllib.loads(line)
    except tomllib.TOMLDecodeError:
        return False
    return True


def _replace_codex_table(text, entry):
    # Line-based replacement is safe for ordinary table blocks. Refuse multiline
    # strings, where a line that looks like a table header could be string content.
    if '"""' in text or "'''" in text:
        raise ValueError("Cannot safely replace novel_aed in TOML containing multiline strings")

    output = []
    remove_section = False
    found = False
    for line in text.splitlines(keepends=True):
        if _is_toml_header(line):
            line_body = line.lstrip().split("#", 1)[0].strip()
            match = _CODEX_TARGET_HEADER.fullmatch(line.rstrip("\r\n"))
            if match:
                remove_section = True
                found = True
                continue
            has_server = re.search(r"(?<![A-Za-z0-9_-])mcp_servers(?![A-Za-z0-9_-])", line_body)
            has_novel = re.search(r"(?<![A-Za-z0-9_-])novel_aed(?![A-Za-z0-9_-])", line_body)
            if has_server and has_novel:
                raise ValueError("Cannot safely replace quoted/complex novel_aed TOML table syntax")
            remove_section = False
            output.append(line)
            continue
        if not remove_section:
            output.append(line)

    if not found:
        raise ValueError("Cannot locate a replaceable [mcp_servers.novel_aed] table in existing TOML")
    preserved = "".join(output)
    separator = "" if not preserved else ("\n" if preserved.endswith(("\n", "\r")) else "\n\n")
    return preserved + separator + render_codex(entry) + "\n"


def merge_codex(text, entry, *, replace=False):
    """Append or safely replace the Codex server table."""
    current = _toml_config(text)
    servers = current.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("Existing mcp_servers setting is not a TOML table")
    if "novel_aed" in servers:
        if servers["novel_aed"] != entry:
            if not replace:
                raise ValueError("Existing novel_aed MCP configuration differs; refusing to override")
            return _replace_codex_table(text, entry), True
        return text, False
    separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    return text + separator + render_codex(entry) + "\n", True


def merge_json(text, entry, *, replace=False):
    """Merge the JSON MCP server entry while preserving all other keys."""
    entry = portable_entry(entry)
    current = _json_config(text)
    servers = current.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("Existing mcpServers setting must be an object")
    if "novel_aed" in servers:
        if servers["novel_aed"] != entry:
            if not replace:
                raise ValueError("Existing novel_aed MCP configuration differs; refusing to override")
            current["mcpServers"] = {**servers, "novel_aed": entry}
            return json.dumps(current, ensure_ascii=False, indent=2) + "\n", True
        return text, False
    current["mcpServers"] = {**servers, "novel_aed": entry}
    return json.dumps(current, ensure_ascii=False, indent=2) + "\n", True


def _ensure_inside(path, project):
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(Path(project).resolve())
    except ValueError as exc:
        raise ValueError(f"Target escapes the project directory: {path}") from exc
    return resolved


def _is_link_or_junction(path):
    path = Path(path)
    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or (junction_check is not None and junction_check())


def _check_parent_paths(path, project):
    """Reject a file blocking a future parent directory before making changes."""
    project = Path(project).resolve()
    parent = Path(path).parent
    cursor = parent
    while cursor != project and project in cursor.parents:
        if cursor.exists() and not cursor.is_dir():
            raise ValueError(f"A non-directory blocks the target path: {cursor}")
        cursor = cursor.parent


def _backup_path(path):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    unique = uuid.uuid4().hex[:12]
    backup = Path(path).with_name(f"{Path(path).name}.novel-aed-backup-{stamp}-{unique}")
    if backup.exists():
        raise ValueError(f"Backup path already exists: {backup}")
    return backup


def _read_config(path):
    if not path.exists():
        return ""
    if path.is_symlink():
        raise ValueError(f"Refusing to use a symlink as a project configuration: {path}")
    if not path.is_file():
        raise ValueError(f"Configuration path is not a file: {path}")
    return path.read_text(encoding="utf-8-sig")


def _tree_files(root, *, allow_symlinks=False):
    """Map a directory's relative file paths to bytes, rejecting symlinks by default."""
    root = Path(root)
    files = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            if allow_symlinks:
                return None
            raise ValueError(f"Skill folders may not contain symlinks: {path}")
        if path.is_file():
            files[path.relative_to(root)] = path.read_bytes()
        elif not path.is_dir():
            raise ValueError(f"Unsupported item in skill folder: {path}")
    return files


def _skill_is_identical(source, destination, *, allow_unsafe_destination=False):
    if destination.is_symlink():
        raise ValueError(f"Refusing to use a symlink as the skill destination: {destination}")
    if destination.is_file():
        raise ValueError(f"Skill destination is not a directory: {destination}")
    source_files = _tree_files(source)
    try:
        destination_files = _tree_files(destination, allow_symlinks=allow_unsafe_destination)
    except ValueError:
        if allow_unsafe_destination:
            return False
        raise
    if destination_files is None:
        return False
    return source_files == destination_files


def make_plan(client, project, root=ROOT, *, write=False, stories_root=None, python=None,
              runtime_root=None, replace=False):
    """Validate all destinations and conflicts before any write takes place."""
    if client not in CLIENT_PATHS and client != "json":
        raise ValueError(f"Unsupported client: {client}")
    root = Path(root).resolve()
    project = Path(project).resolve()
    entry = server_entry(root, stories_root=stories_root, python=python, runtime_root=runtime_root)
    if client != "codex":
        entry = portable_entry(entry)
    if client == "json":
        return {
            "client": client,
            "project": project,
            "entry": entry,
            "snippet": render_json(entry) + "\n",
            "config_path": None,
            "config_text": None,
            "config_changed": False,
            "skill_source": None,
            "skill_path": None,
            "skill_changed": False,
            "backup_paths": [],
        }

    config_path = _ensure_inside(project / CLIENT_PATHS[client], project)
    _check_parent_paths(config_path, project)
    existing = _read_config(config_path)
    original_bytes = config_path.read_bytes() if config_path.exists() else None
    has_existing_entry, previous_entry = _existing_server_entry(client, existing)
    config_replace = has_existing_entry and previous_entry != entry
    if client == "codex":
        config_text, config_changed = merge_codex(existing, entry, replace=replace)
        snippet = render_codex(entry) + "\n"
    else:
        config_text, config_changed = merge_json(existing, entry, replace=replace)
        snippet = render_json(entry) + "\n"

    skill_source = root / "skills" / "novel-aed"
    raw_skill_path = project / SKILL_PATHS[client]
    skill_path = _ensure_inside(raw_skill_path, project)
    _check_parent_paths(skill_path, project)
    skill_changed = False
    skill_replace = False
    if write:
        if not skill_source.is_dir():
            raise ValueError(f"Canonical skill folder is required for --write: {skill_source}")
        if _is_link_or_junction(skill_source):
            raise ValueError(f"Canonical skill folder may not be a symlink or junction: {skill_source}")
        if _is_link_or_junction(raw_skill_path):
            raise ValueError(f"Skill destination may not be a symlink or junction: {raw_skill_path}")
        _tree_files(skill_source)  # Validate source before creating any destination.
        if skill_path.exists():
            identical = _skill_is_identical(skill_source, skill_path, allow_unsafe_destination=replace)
            if not identical:
                if not replace:
                    raise ValueError(f"Existing skill differs; refusing to overwrite: {skill_path}")
                skill_replace = True
                skill_changed = True
        else:
            skill_changed = True

    config_backup_path = _backup_path(config_path) if write and config_replace and replace else None
    skill_backup_path = _backup_path(skill_path) if write and skill_replace else None
    backup_paths = [path for path in (config_backup_path, skill_backup_path) if path is not None]

    return {
        "client": client,
        "project": project,
        "entry": entry,
        "snippet": snippet,
        "config_path": config_path,
        "config_text": config_text,
        "config_changed": config_changed,
        "config_original": existing,
        "config_original_bytes": original_bytes,
        "config_backup_path": config_backup_path,
        "skill_source": skill_source,
        "skill_path": skill_path,
        "skill_changed": skill_changed,
        "skill_replace": skill_replace,
        "skill_backup_path": skill_backup_path,
        "backup_paths": backup_paths,
    }


def _backup_config(path, backup_path, original_bytes):
    if original_bytes is None:
        raise ValueError(f"Cannot back up a missing configuration: {path}")
    if not path.exists() or path.read_bytes() != original_bytes:
        raise ValueError(f"Configuration changed during setup; refusing to back up: {path}")
    with Path(backup_path).open("xb") as backup:
        backup.write(original_bytes)


def _write_config(path, content, original_bytes):
    current = path.read_bytes() if path.exists() else None
    if current != original_bytes:
        raise ValueError(f"Configuration changed during setup; refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent,
                                         prefix=".novel-aed-", suffix=".tmp", delete=False) as temp:
            temp.write(content)
            temp_name = temp.name
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def apply_plan(plan):
    """Apply a validated plan and return the paths of backups created."""
    if plan["client"] == "json":
        raise ValueError("The json client only prints a snippet; --write is not supported")

    created_backups = []
    try:
        if plan["config_changed"]:
            if plan.get("config_backup_path") is not None:
                _backup_config(plan["config_path"], plan["config_backup_path"], plan["config_original_bytes"])
                created_backups.append(plan["config_backup_path"])
            _write_config(plan["config_path"], plan["config_text"], plan["config_original_bytes"])

        if plan["skill_changed"]:
            destination = plan["skill_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Stage the complete new copy before moving any installed skill.
            stage_parent = Path(tempfile.mkdtemp(prefix=".novel-aed-skill-", dir=destination.parent))
            staged = stage_parent / destination.name
            try:
                shutil.copytree(plan["skill_source"], staged)
                if plan["skill_replace"]:
                    backup_path = plan["skill_backup_path"]
                    if not destination.is_dir() or backup_path.exists():
                        raise ValueError(f"Skill destination changed during setup; refusing to replace: {destination}")
                    os.rename(destination, backup_path)
                    created_backups.append(backup_path)
                elif destination.exists():
                    raise ValueError(f"Skill destination appeared during setup; refusing to overwrite: {destination}")
                os.rename(staged, destination)
            finally:
                shutil.rmtree(stage_parent, ignore_errors=True)
    except (OSError, ValueError) as exc:
        if created_backups:
            paths = ", ".join(str(path) for path in created_backups)
            raise OSError(f"{exc}; existing content is preserved at: {paths}") from exc
        raise
    return created_backups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("codex", "claude", "cursor", "json"), required=True)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true", help="write project-local config and copy the canonical skill")
    parser.add_argument("--stories-root", type=Path, default=None, help=f"stories directory (default: {ROOT / 'stories'})")
    parser.add_argument("--runtime-root", type=Path, default=None, help="runtime directory containing scripts/mcp_server.py")
    parser.add_argument("--python", type=Path, default=None, help="Python interpreter to use in the server command")
    parser.add_argument("--replace", action="store_true", help="back up and replace conflicting novel_aed config and installed skill")
    args = parser.parse_args(argv)

    if args.client == "json" and args.write:
        raise ValueError("The json client only prints a snippet; --write is not supported")
    project = args.project.resolve()
    if args.write and not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    plan = make_plan(args.client, project, ROOT, write=args.write, stories_root=args.stories_root,
                     python=args.python, runtime_root=args.runtime_root, replace=args.replace)
    if args.write:
        backups = apply_plan(plan)
        print(f"Configured {args.client} MCP server for {project}", file=sys.stderr)
        if backups:
            print("Backups:", file=sys.stderr)
            for path in backups:
                print(f"  {path}", file=sys.stderr)
    else:
        if args.client != "json":
            print(f"--write will also copy skills/novel-aed to {project / SKILL_PATHS[args.client]}", file=sys.stderr)
        print(plan["snippet"], end="")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, TypeError) as exc:
        sys.exit(str(exc))
