#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Allowlisted binary ZIP and complete corresponding source; no prefix traversal."""
import hashlib
import json
from pathlib import Path
import sys
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fenix_patch.core import digest, verify_bundle
from fenix_patch import __version__


def main():
    lock = json.loads((ROOT / "bundle.json").read_text())
    if lock["version"] != __version__:
        raise ValueError("Installer and bundle versions differ")
    verify_bundle(ROOT)
    for group in ("sources", "patches"):
        for name, expected in lock[group].items():
            if digest(ROOT / group / name) != expected:
                raise ValueError("Source checksum mismatch: " + name)
    allowed = [ROOT / name for name in ("README.md", "LICENSE", "THIRD_PARTY.md", "BUILDING.md", "bundle.json", "install.sh", ".gitignore")]
    for folder in ("fenix_patch", "patches", "licenses", "scripts", "tests", "docs", "native", ".github"):
        for file in sorted((ROOT / folder).rglob("*")):
            if "__pycache__" in file.parts or file.suffix == ".pyc": continue
            if file.is_symlink(): raise ValueError("Symlink in source export")
            if file.is_file(): allowed.append(file)
    allowed += [ROOT / "integration" / name for name in lock["integration"] if not name.endswith(".exe")]
    for file in allowed:
        if not file.is_file() or file.is_symlink(): raise ValueError("Missing source: " + str(file))
        data = file.read_bytes()
        if re.search(rb"/home/[A-Za-z0-9_-]+/(?:Work|\.local/share/flightdeck/runtimes)", data) or (b"-----BEGIN " + b"PRIVATE KEY-----") in data or re.search(rb"XBL3[.]0 x=\d+;[A-Za-z0-9_-]{30,}", data):
            raise ValueError("Private content in export: " + str(file.relative_to(ROOT)))
    archives = [ROOT / "sources" / name for name in lock["sources"]]
    output = ROOT / "dist"; output.mkdir(exist_ok=True)
    stem = "fenix-a320-linux-patch-" + lock["version"]
    source_path = output / (stem + "-source.tar.gz")
    with tarfile.open(source_path, "w:gz") as archive:
        for file in sorted(allowed + archives):
            info = archive.gettarinfo(str(file), str(Path(stem) / file.relative_to(ROOT)))
            info.uid = info.gid = 0; info.uname = info.gname = ""; info.mtime = 0
            with file.open("rb") as stream: archive.addfile(info, stream)
    binary_path = output / (stem + "-linux-x86_64.zip")
    binaries = [ROOT / "payload" / name for name in lock["files"]]
    binaries += [ROOT / "integration" / name for name in lock["integration"] if name.endswith(".exe")]
    with zipfile.ZipFile(binary_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(allowed + archives + binaries):
            info = zipfile.ZipInfo(str(Path(stem) / file.relative_to(ROOT)), (2026, 9, 23, 0, 0, 0))
            info.external_attr = (file.stat().st_mode & 0o777 | 0o100000) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, file.read_bytes())
    outputs = (binary_path, source_path)
    (output / "SHA256SUMS").write_text("".join(digest(p) + "  " + p.name + "\n" for p in outputs))
    release = {"version": lock["version"], "url": lock["repository"] + "/releases/download/v" + lock["version"] + "/" + binary_path.name,
               "sha256": digest(binary_path), "archive_root": stem}
    (output / "flightdeck-release.json").write_text(json.dumps(release, indent=2) + "\n")
    for path in outputs: print(path.name, path.stat().st_size, "bytes")


if __name__ == "__main__": main()
