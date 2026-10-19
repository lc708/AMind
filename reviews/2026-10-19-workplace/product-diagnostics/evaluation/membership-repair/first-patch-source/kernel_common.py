"""Shared experiment identity and bounded filesystem operations (Python stdlib)."""

import hashlib
import json
import math
import os
import re
import stat
import tempfile
import unicodedata
from pathlib import Path


SCHEMA = 2
MAX_FILE = 64 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha(value):
    data = value if isinstance(value, bytes) else canonical(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def regular(path, missing=False):
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        if missing:
            return
        raise
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f"expected an unlinked regular file: {path}")


def read_bytes(path, limit=MAX_FILE):
    path = Path(path)
    regular(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError(f"unsafe or oversized file: {path}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"oversized file: {path}")
        return data
    finally:
        os.close(fd)


def read_json(path):
    return json.loads(read_bytes(path))


def read_jsonl(path):
    rows = []
    for n, line in enumerate(read_bytes(path).decode("utf-8").splitlines(), 1):
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{n}: expected object")
            rows.append(value)
    return rows


def safe_dir(path):
    """Permit system aliases above the caller's root; refuse a linked root itself."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"symlink directory refused: {path}")
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError(f"not a directory: {path}")
    return path.resolve()


def in_root(root, relative, create_parent=False):
    root = Path(root).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError('linked artifact root or ancestor; use its resolved directory explicitly')
    root = root.resolve()
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(x in ("..", ".") for x in rel.parts):
        raise ValueError("artifact path must be relative without dot traversal")
    parent = root
    for component in rel.parts[:-1]:
        parent = parent / component
        if parent.is_symlink():
            raise ValueError(f"linked artifact parent: {parent}")
        if create_parent:
            parent.mkdir(exist_ok=True)
        if not parent.is_dir() or root not in (parent.resolve(), *parent.resolve().parents):
            raise ValueError(f"artifact parent outside root: {parent}")
    leaf = parent / rel.name
    regular(leaf, missing=True)
    return leaf


def atomic(root, relative, data):
    dest = in_root(root, relative, create_parent=True)
    if not isinstance(data, bytes):
        data = data.encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=".amind-", dir=dest.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        regular(dest, missing=True)
        os.replace(temporary, dest)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(root, relative, value):
    atomic(root, relative, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def append_json(root, relative, value):
    path = in_root(root, relative, create_parent=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("unsafe append target")
        data = (canonical(value) + "\n").encode("utf-8")
        while data:
            written = os.write(fd, data)
            if written <= 0:
                raise OSError("append made no progress")
            data = data[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def unique_ids(rows):
    seen = {}
    for row in rows:
        key = row.get("id")
        if not isinstance(key, str) or not key or len(key) > 512 or any(ord(c) < 32 for c in key):
            raise ValueError("case IDs must be nonempty printable strings, at most 512 characters")
        folded = unicodedata.normalize("NFKC", key).casefold()
        if folded in seen:
            raise ValueError(f"duplicate/normalized case ID collision: {key!r} and {seen[folded]!r}")
        seen[folded] = key
    return {row["id"]: row for row in rows}


def file_hashes(base, paths):
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise ValueError("snapshot files must be an explicit list of paths")
    hashes = {}
    for value in paths:
        path = Path(value)
        if not path.is_absolute():
            path = base / path
        hashes[value] = sha(read_bytes(path))
    return hashes


def command_spec(spec, base):
    if not isinstance(spec, dict):
        raise ValueError("command specification must be an object")
    command = spec.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("command must be a nonempty argv array; shell strings are not accepted")
    if not spec.get("files"):
        raise ValueError("command adapters must list their implementation files for hashing")
    cwd = (base / spec.get("cwd", ".")).resolve()
    if not cwd.is_dir():
        raise ValueError("adapter cwd must exist")
    return {"command": command, "cwd": str(cwd), "files": file_hashes(base, spec["files"]),
            "retry_safe": spec.get("retry_safe") is True}


def contract_hash(manifest):
    identity = manifest.get("comparison_identity")
    if manifest.get("schema_version") != SCHEMA or not isinstance(identity, dict):
        raise ValueError("missing v2 experiment identity")
    expected = sha(identity)
    if manifest.get("comparison_hash") != expected:
        raise ValueError("experiment identity hash mismatch")
    return expected


def compatible(flow, candidate):
    manifests = []
    for variant in ("baseline", candidate):
        manifest = read_json(in_root(flow, f"{variant}/manifest.json"))
        contract_hash(manifest)
        results_path = in_root(flow, f"{variant}/results.jsonl")
        if manifest.get("results_sha256") != sha(read_bytes(results_path)):
            raise ValueError(f"{variant}: result bytes changed since export; re-export/regrade with provenance")
        if manifest.get("status") != "complete":
            raise ValueError(f"{variant}: run is not complete")
        if manifest.get('attempts_sha256') is not None:
            if manifest['attempts_sha256'] != sha(read_bytes(in_root(flow, f'{variant}/attempts.jsonl'))):
                raise ValueError(f'{variant}: attempt journal changed since export')
        manifests.append(manifest)
    if manifests[0]["comparison_hash"] != manifests[1]["comparison_hash"]:
        left, right = [m["comparison_identity"] for m in manifests]
        differing = sorted(k for k in set(left) | set(right) if left.get(k) != right.get(k))
        raise ValueError("incompatible experiments: " + ", ".join(differing))
    if manifests[0].get('selection_certificate_hash') != manifests[1].get('selection_certificate_hash'):
        raise ValueError('final test selection certificates differ')
    for variant, manifest in zip(('baseline', candidate), manifests):
        if manifest.get('result_identity_required'):
            for row in read_jsonl(in_root(flow, f'{variant}/results.jsonl')):
                expected = {'comparison_hash': manifest['comparison_hash'],
                            'treatment_hash': manifest.get('treatment_hash'),
                            'case_id': row.get('prompt_id'), 'rep': row.get('rep')}
                if row.get('result_identity') != expected:
                    raise ValueError(f'{variant}: result identity differs from its measurement/treatment/case')
    return manifests
