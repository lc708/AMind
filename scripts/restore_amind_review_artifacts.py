#!/usr/bin/env python3
"""Check or restore archived review files without extracting links or running code."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile
import unicodedata
import uuid


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "reviews/2026-10-19-shipping/artifact-manifest.json"
BUNDLES = {
    "artifacts/october-18-agent-runs.tar.gz": (
        "reviews/2026-10-18-comparison/agent-runs/",
    ),
    "artifacts/october-19-workplace-runs.tar.gz": (
        "reviews/2026-10-19-workplace/runs/",
    ),
    "artifacts/october-19-reconciliation-fixtures.tar.gz": (
        "reviews/2026-10-19-workplace/product-diagnostics/evaluation/cross-engineering-review/physical/",
        "reviews/2026-10-19-workplace/product-diagnostics/evaluation/cross-engineering-review/v2/physical/",
    ),
}
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 20000
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ArtifactError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ArtifactError(message)


def safe_name(value):
    require(isinstance(value, str) and bool(value), "Empty or non-string member path")
    require("\\" not in value and ":" not in value and "\0" not in value,
            "Unsupported member path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in ("", ".", "..", ".git")
                                          for p in value.split("/")), "Unsafe member path")
    require(path.as_posix() == value, "Non-canonical member path")
    return value


def integer(value, maximum, label):
    require(type(value) is int and 0 <= value <= maximum, "Invalid " + label)
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_namespace(names):
    """Reject file/directory and conservative cross-filesystem path aliases."""
    nodes = {}
    for name in sorted(names):
        parts = PurePosixPath(name).parts
        for length in range(1, len(parts) + 1):
            original = parts[:length]
            key = tuple(unicodedata.normalize("NFD", part.casefold()) for part in original)
            kind = "file" if length == len(parts) else "directory"
            previous = nodes.get(key)
            if previous is not None:
                require(previous == (original, kind),
                        "Conflicting case/Unicode alias or file/directory prefix: " + name)
            else:
                nodes[key] = (original, kind)


def read_regular(path, maximum):
    """Never follow a final symlink, including one swapped after lstat."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode), "Expected regular file: " + str(path))
        require(info.st_size <= maximum, "Oversized file: " + str(path))
        data = handle.read(maximum + 1)
    require(len(data) <= maximum, "Oversized file: " + str(path))
    return data


def validated_members(manifest_path):
    """Validate every bundle and payload before any destination writes."""
    manifest = json.loads(read_regular(manifest_path, 16 * 1024 * 1024))
    require(manifest.get("schema_name") == "amind-review-artifact-archive" and
            type(manifest.get("schema_version")) is int and
            manifest["schema_version"] == 1, "Unsupported archive manifest")
    bundles = manifest.get("bundles")
    require(isinstance(bundles, list) and len(bundles) == len(BUNDLES),
            "Incomplete archive bundle set")
    require({b.get("archive") for b in bundles if isinstance(b, dict)} == set(BUNDLES),
            "Unexpected or duplicate archive bundle")
    archive_directory = manifest_path.parent / "artifacts"
    require(stat.S_ISDIR(archive_directory.lstat().st_mode), "Archive directory must not be a link")
    restored = {}
    total = 0
    for bundle in bundles:
        archive_name = bundle["archive"]
        require(SHA256.fullmatch(str(bundle.get("sha256", ""))) is not None,
                "Invalid archive checksum")
        expected_size = integer(bundle.get("size_bytes"), MAX_ARCHIVE_BYTES, "archive size")
        data = read_regular(manifest_path.parent / archive_name, MAX_ARCHIVE_BYTES)
        require(len(data) == expected_size and digest(data) == bundle["sha256"],
                "Archive checksum/size mismatch: " + archive_name)
        rows = bundle.get("members")
        require(isinstance(rows, list) and len(rows) <= MAX_MEMBERS, "Invalid member inventory")
        expected = {}
        for row in rows:
            require(isinstance(row, dict), "Invalid member record")
            name = safe_name(row.get("path"))
            require(any(name.startswith(prefix) for prefix in BUNDLES[archive_name]),
                    "Member outside the fixed review roots: " + name)
            require(name not in expected and name not in restored, "Duplicate manifest member: " + name)
            integer(row.get("size_bytes"), MAX_MEMBER_BYTES, "member size")
            require(SHA256.fullmatch(str(row.get("sha256", ""))) is not None,
                    "Invalid member checksum: " + name)
            expected[name] = row
        require(bundle.get("member_count") == len(expected), "Member count mismatch")
        require(bundle.get("uncompressed_bytes") == sum(r["size_bytes"] for r in rows),
                "Uncompressed size mismatch")
        expected_payload_bytes = sum(r["size_bytes"] for r in rows)
        require(total + expected_payload_bytes <= MAX_TOTAL_BYTES,
                "Archive exceeds restoration limits")
        # Bound gzip expansion before tarfile sees any PAX/long-name header.
        # Payload plus bounded per-member metadata covers our deterministic tar
        # writer while refusing oversized metadata and decompression bombs.
        tar_limit = expected_payload_bytes + len(rows) * 4096 + 10240
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as compressed:
            tar_data = compressed.read(tar_limit + 1)
        require(len(tar_data) <= tar_limit, "Archive gzip expansion exceeds inventory bound")
        seen = set()
        with tarfile.open(fileobj=io.BytesIO(tar_data), mode="r:") as archive:
            for member in archive:
                name = safe_name(member.name)
                require(member.isfile() and not member.issym() and not member.islnk(),
                        "Archive contains a non-regular member: " + name)
                require(name in expected and name not in seen, "Unexpected/duplicate tar member: " + name)
                row = expected[name]
                require(member.size == row["size_bytes"], "Tar member size mismatch: " + name)
                total += member.size
                require(total <= MAX_TOTAL_BYTES and len(restored) < MAX_MEMBERS,
                        "Archive exceeds restoration limits")
                source = archive.extractfile(member)
                require(source is not None, "Missing tar payload: " + name)
                payload = source.read(MAX_MEMBER_BYTES + 1)
                require(len(payload) == row["size_bytes"] and digest(payload) == row["sha256"],
                        "Tar member checksum mismatch: " + name)
                restored[name] = payload
                seen.add(name)
        require(seen == set(expected), "Missing tar members: " + archive_name)
    links = manifest.get("inert_symlinks", [])
    require(isinstance(links, list), "Invalid inert link metadata")
    # These records are deliberately inert: their paths/targets are never used
    # as filesystem instructions, and no link is created or dereferenced.
    validate_namespace(restored)
    return restored, len(links)


def check_destinations(root, members):
    missing = []
    existing = []
    for name, payload in sorted(members.items()):
        current = root
        absent_parent = False
        parts = PurePosixPath(name).parts
        for part in parts[:-1]:
            current = current / part
            if absent_parent:
                continue
            try:
                info = current.lstat()
            except FileNotFoundError:
                absent_parent = True
                continue
            require(stat.S_ISDIR(info.st_mode), "Destination parent is not a regular directory: " + str(current))
        target = root / name
        if absent_parent:
            missing.append(name)
            continue
        try:
            info = target.lstat()
        except FileNotFoundError:
            missing.append(name)
            continue
        require(stat.S_ISREG(info.st_mode), "Destination is not a regular file: " + name)
        require(read_regular(target, MAX_MEMBER_BYTES) == payload,
                "Existing destination has different content: " + name)
        existing.append(name)
    return missing, existing


def parent_fd(root_fd, parts):
    """Open/create directory components relative to a trusted root descriptor."""
    descriptor = os.dup(root_fd)
    try:
        for part in parts:
            try:
                os.mkdir(part, mode=0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def apply_missing(root, members, missing):
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in missing:
            parts = PurePosixPath(name).parts
            directory_fd = parent_fd(root_fd, parts[:-1])
            temporary = ".amind-restore-" + uuid.uuid4().hex
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o644, dir_fd=directory_fd)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(members[name])
                    handle.flush()
                    os.fsync(handle.fileno())
                # Hard-link installation is an atomic no-replace operation.
                # The source is our new regular tempfile, never an archive link.
                os.link(temporary, parts[-1], src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd, follow_symlinks=False)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                os.close(directory_fd)
    finally:
        os.close(root_fd)


def restore(manifest_path, root, apply=False):
    require(all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")) and
            all(operation in os.supports_dir_fd for operation in (os.open, os.mkdir, os.link, os.unlink)),
            "Restoration requires POSIX no-follow and directory-descriptor filesystem support")
    root = Path(root).absolute()
    require(stat.S_ISDIR(root.lstat().st_mode), "Destination root must be a directory, not a symlink")
    members, inert_links = validated_members(Path(manifest_path).absolute())
    missing, existing = check_destinations(root, members)
    if apply:
        apply_missing(root, members, missing)
    return {"success": True, "mode": "apply" if apply else "check", "files": len(members),
            "bytes": sum(map(len, members.values())), "already_matching": len(existing),
            "missing_before": len(missing), "restored": len(missing) if apply else 0,
            "inert_symlinks_not_restored": inert_links,
            "root": str(root), "manifest": str(Path(manifest_path).absolute())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Existing repository destination directory")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--apply", action="store_true", help="Restore missing regular files; default only checks")
    args = parser.parse_args()
    try:
        result = restore(args.manifest, args.root, args.apply)
    except (ArtifactError, OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        print(json.dumps({"success": False, "error": str(error)}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
