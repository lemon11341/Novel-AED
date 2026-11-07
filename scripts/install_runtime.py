"""Install an immutable Python runtime outside npm caches; never publish or modify manuscripts."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from distribution import fingerprint, metadata, package_files

ROOT = Path(__file__).resolve().parents[1]


def default_home():
    if os.environ.get("NOVEL_AED_HOME"):
        return Path(os.environ["NOVEL_AED_HOME"]).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "NovelAED"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "novel-aed"


def runtime_plan(home, source=ROOT):
    files = package_files(source)
    version = metadata(files)["version"]
    digest = fingerprint(files)
    home = Path(home).expanduser().resolve()
    runtime = home / "runtimes" / f"{version}-{digest[:16]}"
    python = runtime / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    marker = runtime / ".ready.json"
    ready = False
    if marker.is_file() and python.is_file():
        try:
            ready = (json.loads(marker.read_text(encoding="utf-8")).get("sha256") == digest
                     and fingerprint(package_files(runtime)) == digest)
        except (ValueError, OSError, KeyError):
            ready = False
    return {"home": str(home), "runtime_root": str(runtime), "python": str(python),
            "stories_root": str(home / "stories"), "version": version, "sha256": digest, "ready": ready}


def run(command):
    subprocess.run(command, check=True, stdout=sys.stderr, stderr=sys.stderr)


def install(plan, source=ROOT):
    if plan["ready"]:
        return plan
    home, runtime = Path(plan["home"]), Path(plan["runtime_root"])
    home.mkdir(parents=True, exist_ok=True)
    lock = home / ".install.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(f"Installation is locked: {lock}. Check whether another setup is running; do not remove a live lock.") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "at": datetime.now(timezone.utc).isoformat()}, stream)
        files = package_files(source)
        if fingerprint(files) != plan["sha256"]:
            raise ValueError("Package changed during installation")
        runtime.mkdir(parents=True, exist_ok=True)
        # A failed install can resume, but never overwrite different code in an immutable runtime.
        for name, content in files.items():
            target = runtime / name
            if target.exists():
                if target.read_bytes() != content:
                    raise ValueError(f"Runtime content differs: {target}. Choose a fresh --home; existing data was preserved.")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(content)
        python = Path(plan["python"])
        if not python.is_file():
            run([sys.executable, "-m", "venv", str(runtime / ".venv")])
        run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(runtime / "requirements-mcp.txt")])
        run([str(python), "-c", "from mcp.server.fastmcp import FastMCP; from importlib.metadata import version; assert version('mcp') == '1.26.0'"])
        marker = runtime / ".ready.json"
        marker.write_text(json.dumps({"version": plan["version"], "sha256": plan["sha256"]}, indent=2), encoding="utf-8")
        return runtime_plan(home, source)
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=default_home())
    parser.add_argument("--install", action="store_true", help="create the persistent runtime and install its SDK")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required")
    plan = runtime_plan(args.home)
    if args.install:
        plan = install(plan)
    print(json.dumps(plan, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
