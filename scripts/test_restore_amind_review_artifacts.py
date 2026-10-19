#!/usr/bin/env python3
"""Exercise restore trust boundaries with small fixtures and the real archives."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

import restore_amind_review_artifacts as restore


class RestoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="amind-restore-test-")
        self.base = Path(self.temporary.name)
        self.archive_root = self.base / "source"
        self.destination = self.base / "target"
        (self.archive_root / "artifacts").mkdir(parents=True)
        self.destination.mkdir()
        self.manifest = self.archive_root / "artifact-manifest.json"
        self.rows = []
        self.payloads = {}
        for index, (archive, prefixes) in enumerate(restore.BUNDLES.items()):
            name = prefixes[0] + "fixture-" + str(index) + ".txt"
            data = ("frozen evidence " + str(index) + "\n").encode()
            self.payloads[name] = data
            self.rows.append(self.bundle(archive, [(name, data, None)]))
        self.write_manifest()

    def tearDown(self):
        self.temporary.cleanup()

    def bundle(self, archive_name, entries):
        raw = io.BytesIO()
        members = []
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, data, link_type in entries:
                member = tarfile.TarInfo(name)
                member.size = len(data) if link_type is None else 0
                if link_type is not None:
                    member.type = link_type
                    member.linkname = "../../outside"
                archive.addfile(member, io.BytesIO(data) if link_type is None else None)
                members.append({"path": name, "size_bytes": member.size,
                                "sha256": hashlib.sha256(data).hexdigest()})
        compressed = gzip.compress(raw.getvalue(), mtime=0)
        (self.archive_root / archive_name).write_bytes(compressed)
        return {"archive": archive_name, "size_bytes": len(compressed),
                "sha256": hashlib.sha256(compressed).hexdigest(),
                "member_count": len(members),
                "uncompressed_bytes": sum(m["size_bytes"] for m in members),
                "members": members}

    def write_manifest(self):
        self.manifest.write_text(json.dumps({"schema_name": "amind-review-artifact-archive",
                                             "schema_version": 1, "bundles": self.rows,
                                             "inert_symlinks": [{"path": "untrusted", "target": "/never/restored"}]}))

    def rejects_without_writes(self):
        before = {str(p.relative_to(self.destination)): p.read_bytes()
                  for p in self.destination.rglob("*") if p.is_file() and not p.is_symlink()}
        with self.assertRaises((restore.ArtifactError, OSError, ValueError)):
            restore.restore(self.manifest, self.destination, apply=True)
        after = {str(p.relative_to(self.destination)): p.read_bytes()
                 for p in self.destination.rglob("*") if p.is_file() and not p.is_symlink()}
        self.assertEqual(before, after)

    def test_default_check_does_not_write_and_apply_is_idempotent(self):
        result = restore.restore(self.manifest, self.destination)
        self.assertEqual(result["missing_before"], 3)
        self.assertEqual(list(self.destination.iterdir()), [])
        result = restore.restore(self.manifest, self.destination, apply=True)
        self.assertEqual(result["restored"], 3)
        self.assertEqual(result["inert_symlinks_not_restored"], 1)
        for name, data in self.payloads.items():
            self.assertEqual((self.destination / name).read_bytes(), data)
        self.assertFalse(any(p.is_symlink() for p in self.destination.rglob("*")))
        result = restore.restore(self.manifest, self.destination, apply=True)
        self.assertEqual(result["restored"], 0)
        self.assertEqual(result["already_matching"], 3)

    def test_cli_defaults_to_check(self):
        completed = subprocess.run([sys.executable, str(Path(restore.__file__)),
                                    "--root", str(self.destination), "--manifest", str(self.manifest)],
                                   text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(completed.stdout)["mode"], "check")
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_archive_checksum_is_checked(self):
        self.rows[0]["sha256"] = "0" * 64
        self.write_manifest()
        self.rejects_without_writes()

    def test_member_checksum_is_checked_even_if_archive_hash_matches(self):
        self.rows[0]["members"][0]["sha256"] = "0" * 64
        self.write_manifest()
        self.rejects_without_writes()

    def test_changed_existing_file_prevents_all_restores(self):
        # Put the conflict last, so validation must inspect all destinations
        # before restoring an earlier missing file.
        name = sorted(self.payloads)[-1]
        target = self.destination / name
        target.parent.mkdir(parents=True)
        target.write_bytes(b"local change must survive\n")
        self.rejects_without_writes()

    def test_traversal_path_is_rejected_even_if_manifest_and_archive_agree(self):
        for name in ["../escape", "/absolute/escape", "reviews/../escape", "C:\\escape"]:
            with self.subTest(name=name):
                self.rows[0] = self.bundle(self.rows[0]["archive"], [(name, b"bad", None)])
                self.write_manifest()
                self.rejects_without_writes()

    def test_member_outside_allowlisted_roots_is_rejected(self):
        self.rows[0] = self.bundle(self.rows[0]["archive"], [("skills/amind/SKILL.md", b"bad", None)])
        self.write_manifest()
        self.rejects_without_writes()

    def test_tar_symlink_and_hardlink_members_are_rejected(self):
        name = self.rows[0]["members"][0]["path"]
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE]:
            with self.subTest(kind=kind):
                self.rows[0] = self.bundle(self.rows[0]["archive"], [(name, b"", kind)])
                self.write_manifest()
                self.rejects_without_writes()

    def test_duplicate_tar_member_is_rejected(self):
        old = self.rows[0]
        name = old["members"][0]["path"]
        replacement = self.bundle(old["archive"], [(name, b"same", None), (name, b"same", None)])
        replacement["members"] = replacement["members"][:1]
        replacement["member_count"] = 1
        replacement["uncompressed_bytes"] = len(b"same")
        self.rows[0] = replacement
        self.write_manifest()
        self.rejects_without_writes()

    def test_extra_and_missing_tar_members_are_rejected(self):
        first = self.rows[0]
        name = first["members"][0]["path"]
        extra = name + "-extra"
        replacement = self.bundle(first["archive"], [(name, b"same", None), (extra, b"extra", None)])
        replacement["members"] = replacement["members"][:1]
        replacement["member_count"] = 1
        replacement["uncompressed_bytes"] = len(b"same")
        self.rows[0] = replacement
        self.write_manifest()
        self.rejects_without_writes()
        replacement["members"].append({"path": name + "-absent", "size_bytes": 0,
                                        "sha256": hashlib.sha256(b"").hexdigest()})
        replacement["member_count"] = 2
        self.rows[0] = self.bundle(first["archive"], [(name, b"same", None)])
        self.rows[0]["members"] = replacement["members"]
        self.rows[0]["member_count"] = 2
        self.write_manifest()
        self.rejects_without_writes()

    def test_symlink_parent_and_destination_are_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.destination / "reviews").symlink_to(outside, target_is_directory=True)
        self.rejects_without_writes()
        (self.destination / "reviews").unlink()
        name = sorted(self.payloads)[0]
        target = self.destination / name
        target.parent.mkdir(parents=True)
        actual = outside / "unchanged.txt"
        actual.write_bytes(self.payloads[name])
        target.symlink_to(actual)
        self.rejects_without_writes()
        self.assertEqual(actual.read_bytes(), self.payloads[name])

    def test_gzip_expansion_is_bounded_by_inventory(self):
        row = self.rows[0]
        compressed = gzip.compress(b"\0" * 200000, mtime=0)
        (self.archive_root / row["archive"]).write_bytes(compressed)
        row["sha256"] = hashlib.sha256(compressed).hexdigest()
        row["size_bytes"] = len(compressed)
        self.write_manifest()
        self.rejects_without_writes()

    def test_archive_path_cannot_escape_manifest_directory(self):
        self.rows[0]["archive"] = "../elsewhere.tar.gz"
        self.write_manifest()
        self.rejects_without_writes()

    def test_case_unicode_and_file_directory_aliases_reject_before_writes(self):
        prefix = next(iter(restore.BUNDLES.values()))[0]
        pairs = [("alias.txt", "ALIAS.TXT"),
                 ("caf\u00e9.txt", "cafe\u0301.txt"),
                 ("parent", "parent/child.txt"),
                 ("SomeDir/a.txt", "somedir/b.txt")]
        for first, second in pairs:
            with self.subTest(paths=(first, second)):
                self.rows[0] = self.bundle(self.rows[0]["archive"],
                                           [(prefix + first, b"first", None),
                                            (prefix + second, b"second", None)])
                self.write_manifest()
                self.rejects_without_writes()
                self.assertEqual(list(self.destination.iterdir()), [])


class FrozenArchiveRoundTripTests(unittest.TestCase):
    def test_real_archives_restore_every_file_in_fresh_tree(self):
        if not restore.DEFAULT_MANIFEST.is_file():
            self.skipTest("Run package_amind_review_artifacts.py first")
        manifest = json.loads(restore.DEFAULT_MANIFEST.read_text())
        with tempfile.TemporaryDirectory(prefix="amind-review-fresh-") as directory:
            root = Path(directory)
            before = restore.restore(restore.DEFAULT_MANIFEST, root)
            self.assertEqual(list(root.iterdir()), [])
            result = restore.restore(restore.DEFAULT_MANIFEST, root, apply=True)
            count = 0
            for bundle in manifest["bundles"]:
                for row in bundle["members"]:
                    payload = (root / row["path"]).read_bytes()
                    self.assertEqual(len(payload), row["size_bytes"])
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), row["sha256"])
                    count += 1
            self.assertEqual(count, before["missing_before"])
            self.assertEqual(count, result["restored"])
            self.assertEqual(result["inert_symlinks_not_restored"], 6)
            again = restore.restore(restore.DEFAULT_MANIFEST, root, apply=True)
            self.assertEqual(again["already_matching"], count)
            self.assertEqual(again["restored"], 0)
            self.assertFalse(any(path.is_symlink() for path in root.rglob("*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
