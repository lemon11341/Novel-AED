"""Verify npm source metadata or a packed tarball, including exclusion of private/local data."""
import argparse
import json
from pathlib import Path
import sys
import tarfile

from distribution import REQUIRED, allowed, metadata, package_files

ROOT = Path(__file__).resolve().parents[1]


def find_archive(path):
    path = Path(path)
    if path.is_dir():
        matches = list(path.glob("novel-aed-*.tgz"))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one novel-aed tarball in {path}; found {len(matches)}")
        return matches[0]
    return path


def verify_archive(path):
    archive = find_archive(path)
    files = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isdir() and member.name in ("package", "package/"):
                continue
            if not member.isfile() or not member.name.startswith("package/"):
                raise ValueError(f"Unexpected archive entry: {member.name}")
            name = member.name.removeprefix("package/")
            if not allowed(name) or name in files or member.size > 2_000_000:
                raise ValueError(f"Forbidden, duplicate or oversized release file: {name}")
            files[name] = tar.extractfile(member).read()
    missing = REQUIRED - files.keys()
    if missing:
        raise ValueError(f"Missing release files: {', '.join(sorted(missing))}")
    package = metadata(files)
    return {"archive": str(archive), "version": package["version"], "files": len(files),
            "private_data": "excluded"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if args.source_only or args.path is None:
        files = package_files(ROOT)
        package = metadata(files)
        print(json.dumps({"source": "OK", "version": package["version"], "files": len(files)}))
    else:
        print(json.dumps(verify_archive(args.path)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, tarfile.TarError) as exc:
        sys.exit(str(exc))
