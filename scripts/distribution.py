"""Shared release allowlist and metadata. Never enumerate user manuscript directories."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT_FILES = {
    "package.json", "LICENSE", "README.md", "README.ko.md", "README.en.md",
    "AGENTS.md", "requirements-mcp.txt",
}
PATTERNS = (
    "bin/*.mjs", "scripts/*.py", "workflow/*.md", "workflow/lib/*.py",
    "workflow/schemas/*.json", "skills/novel-aed/SKILL.md", "docs/*.md",
    "config/research.json", "config/research.en.json",
)
REQUIRED = {
    "package.json", "LICENSE", "README.md", "requirements-mcp.txt", "AGENTS.md",
    "bin/novel-aed.mjs", "scripts/install_runtime.py", "scripts/setup_mcp.py",
    "scripts/mcp_server.py", "scripts/check_mcp.py", "scripts/workspace.py", "scripts/distribution.py",
    "workflow/WORKFLOW.md", "workflow/STAGES.md", "workflow/lib/service.py",
    "workflow/lib/contracts.py", "workflow/lib/artifacts.py", "workflow/lib/tools.py",
    "workflow/lib/__init__.py", "skills/novel-aed/SKILL.md",
    *(f"workflow/schemas/{name}.json" for name in ("analysis", "outline", "draft", "review")),
}


def allowed(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        return False
    if any(part.startswith(".") or part in ("stories", "data", "tests", "__pycache__", "node_modules") for part in path.parts):
        return False
    return name in ROOT_FILES or any(len(path.parts) == len(PurePosixPath(pattern).parts) and path.match(pattern)
                                     for pattern in PATTERNS)


def package_files(root):
    root = Path(root)
    names = set(ROOT_FILES)
    for pattern in PATTERNS:
        names.update(path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file())
    files = {}
    for name in sorted(names):
        path = root / name
        if not path.is_file():
            continue
        if path.is_symlink() or not allowed(name):
            raise ValueError(f"Unsupported package file: {name}")
        files[name] = path.read_bytes()
    missing = REQUIRED - files.keys()
    if missing:
        raise ValueError(f"Missing package files: {', '.join(sorted(missing))}")
    return files


def metadata(files):
    package = json.loads(files["package.json"])
    if package.get("name") != "novel-aed" or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", package.get("version", "")):
        raise ValueError("Expected novel-aed with a semantic version")
    if package.get("bin", {}).get("novel-aed") != "bin/novel-aed.mjs":
        raise ValueError("Missing novel-aed CLI entrypoint")
    if not package.get("license") or any(name in package.get("scripts", {}) for name in ("postinstall", "preinstall", "install")):
        raise ValueError("Package requires a license and must not auto-install Python on npm install")
    return package


def fingerprint(files):
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode("utf-8") + b"\0" + content + b"\0")
    return digest.hexdigest()
