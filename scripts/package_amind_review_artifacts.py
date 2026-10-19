#!/usr/bin/env python3
"""Create deterministic archives of frozen review files; never edit originals."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile

from restore_amind_review_artifacts import BUNDLES, safe_name


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "reviews/2026-10-19-shipping"
LINK_PARENTS = (
    "reviews/2026-10-19-workplace/product-diagnostics/evaluation/cross-engineering-review",
    "reviews/2026-10-19-workplace/product-diagnostics/evaluation/cross-engineering-review/v2",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def same_or_new(path, data):
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError("Refusing to replace different existing artifact: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def build(root=ROOT, destination=DESTINATION):
    bundles = []
    links = {}
    for name, prefixes in BUNDLES.items():
        files = []
        for prefix in prefixes:
            source = root / prefix
            if not source.is_dir() or source.is_symlink():
                raise ValueError("Missing regular source directory: " + prefix)
            for directory, subdirs, names in os.walk(source, followlinks=False):
                for filename in sorted(subdirs + names):
                    path = Path(directory) / filename
                    relative = path.relative_to(root).as_posix()
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        links[relative] = os.readlink(path)
                    elif stat.S_ISREG(info.st_mode):
                        files.append((safe_name(relative), path.read_bytes()))
                    elif not stat.S_ISDIR(info.st_mode):
                        raise ValueError("Unsupported source file type: " + relative)
        compressed = io.BytesIO()
        with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0,
                           compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for relative, payload in sorted(files):
                    member = tarfile.TarInfo(relative)
                    member.size = len(payload)
                    member.mtime = 0
                    member.mode = 0o644
                    member.uid = member.gid = 0
                    member.uname = member.gname = ""
                    archive.addfile(member, io.BytesIO(payload))
        data = compressed.getvalue()
        same_or_new(destination / name, data)
        bundles.append({"archive": name, "sha256": sha(data), "size_bytes": len(data),
                        "member_count": len(files),
                        "uncompressed_bytes": sum(len(payload) for _, payload in files),
                        "members": [{"path": relative, "sha256": sha(payload),
                                     "size_bytes": len(payload)}
                                    for relative, payload in sorted(files)]})
    for prefix in LINK_PARENTS:
        for path in (root / prefix).iterdir():
            if path.is_symlink():
                links[path.relative_to(root).as_posix()] = os.readlink(path)
    manifest = {"schema_name": "amind-review-artifact-archive", "schema_version": 1,
                "description": "Frozen review files, including ignored logs; originals remain local. Links are inert metadata only.",
                "determinism": "Sorted paths; tar regular members only; uid/gid/mtime zero; mode 0644; gzip mtime zero and empty filename.",
                "bundles": bundles,
                "inert_symlinks": [{"path": path, "target": target,
                                    "target_sha256": sha(target.encode()),
                                    "absolute_target": target.startswith("/"),
                                    "restored": False}
                                   for path, target in sorted(links.items())]}
    encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    same_or_new(destination / "artifact-manifest.json", encoded)
    return {"success": True, "bundles": len(bundles),
            "files": sum(b["member_count"] for b in bundles),
            "payload_bytes": sum(b["uncompressed_bytes"] for b in bundles),
            "archive_bytes": sum(b["size_bytes"] for b in bundles),
            "inert_symlinks": len(links), "manifest_sha256": sha(encoded)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=DESTINATION)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.out), indent=2))


if __name__ == "__main__":
    main()
