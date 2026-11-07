"""Build a private-data-free ZIP that can be shared before npm publication."""
import json
from pathlib import Path
import zipfile

from distribution import metadata, package_files


def main():
    root = Path(__file__).resolve().parents[1]
    files = package_files(root)
    version = metadata(files)["version"]
    target = root / "artifacts" / f"novel-aed-{version}-download.zip"
    target.parent.mkdir(exist_ok=True)
    prefix = f"Novel-AED-{version}/"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(prefix + name, content)
        archive.writestr(prefix + "stories/.gitkeep", b"")
        archive.writestr(prefix + ".gitignore", (root / ".gitignore").read_bytes())
    with zipfile.ZipFile(target) as archive:
        for name, content in files.items():
            if archive.read(prefix + name) != content:
                raise ValueError(f"ZIP content mismatch: {name}")
    print(json.dumps({"zip": str(target), "files": len(files) + 2,
                      "private_data": "excluded"}))


if __name__ == "__main__":
    main()

