#!/usr/bin/env python3
"""Preview/install AMind application skills; preserve replaced copies outside skill discovery."""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import subprocess
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "skills"
PACKAGES = ("amind-engineering", "eval-improve")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def inventory(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc" or path.name == ".DS_Store":
            continue
        if path.is_symlink():
            raise ValueError(f"symlink in skill package: {path}")
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def install(destination, apply=False, replace=False, with_knowledge=False):
    if destination.is_symlink():
        raise ValueError("destination must not be a symlink")
    destination = destination.resolve()
    packages = ("amind", *PACKAGES) if with_knowledge else PACKAGES
    if with_knowledge:
        validation = subprocess.run([sys.executable, '-B', str(SOURCE/'amind/scripts/verify.py')],
            capture_output=True, text=True)
        if validation.returncode:
            raise ValueError('knowledge package validation failed before installation: '+validation.stderr.strip())
    changes = []
    for name in packages:
        source, target = SOURCE / name, destination / name
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValueError(f"refusing non-directory/symlink target: {target}")
        if source == target or source in target.parents or target in source.parents:
            raise ValueError("source and installation paths must not overlap")
        expected = inventory(source)
        if not expected or "SKILL.md" not in expected:
            raise ValueError(f"incomplete source package: {source}")
        same = target.exists() and inventory(target) == expected
        action = "unchanged" if same else "replace" if target.exists() else "install"
        changes.append({"name": name, "action": action, "destination": str(target)})
    result = {"mode": "apply" if apply else "plan", "skills": changes}
    active = [item for item in changes if item["action"] != "unchanged"]
    if not apply or not active:
        return result
    if any(item["action"] == "replace" for item in active) and not replace:
        raise ValueError("existing skill differs; use --replace to preserve a backup and replace it")
    destination.mkdir(parents=True, exist_ok=True)
    backup_root = destination.parent / "skill-backups"
    backup_root.mkdir(exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix="amind-series-", dir=backup_root))
    installed, saved = [], []
    try:
        with tempfile.TemporaryDirectory(prefix=".amind-stage-", dir=destination.parent) as temporary:
            stage = Path(temporary)
            for item in active:
                name = item["name"]
                shutil.copytree(SOURCE / name, stage / name, ignore=IGNORE)
                if inventory(stage / name) != inventory(SOURCE / name):
                    raise ValueError(f"staged copy differs: {name}")
            for item in active:
                name, target = item["name"], Path(item["destination"])
                if target.exists():
                    target.rename(backup / name)
                    saved.append(name)
                (stage / name).rename(target)
                installed.append(name)
                if inventory(target) != inventory(SOURCE / name):
                    raise ValueError(f"installed copy differs: {name}")
    except BaseException:
        for name in reversed(installed):
            shutil.rmtree(destination / name)
        for name in reversed(saved):
            (backup / name).rename(destination / name)
        if not any(backup.iterdir()):
            backup.rmdir()
        raise
    if saved:
        result["backup"] = str(backup)
    else:
        backup.rmdir()
    result["verified"] = True
    return result


def main():
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=codex_home / "skills")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--with-knowledge", action="store_true", help="validate and install all three AMind skills with one rollback backup")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.dest, args.apply, args.replace, args.with_knowledge), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
