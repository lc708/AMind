# Review artifact publication package

The October 18 and 19 studies retain their original bytes and scores. Their numerous raw execution files are transported as three deterministic archives instead of thousands of individual Git entries. The original directories remain on the author's machine. This packaging step makes no model or API calls, changes no product package, and reruns no model evaluation.

| Archive | Original regular files | Payload bytes | Archive bytes |
| --- | ---: | ---: | ---: |
| `artifacts/october-18-agent-runs.tar.gz` | 155 | 5,575,530 | 1,007,894 |
| `artifacts/october-19-workplace-runs.tar.gz` | 4,400 | 17,194,511 | 2,544,686 |
| `artifacts/october-19-reconciliation-fixtures.tar.gz` | 16 | 278,528 | 5,649 |
| Total | 4,571 | 23,048,569 | 3,558,229 |

[artifact-manifest.json](artifact-manifest.json) lists each exact repository-relative path, byte count and SHA-256, plus archive hashes. The run archive includes all 21 `.log` files that the repository's generic ignore rule would otherwise omit. Every member in the October 19 main and confirmation capture fingerprints is represented with its original hash: 4,221 plus 179 files. October 18's actual directory is `agent-runs/`.

Six diagnostic symbolic links are retained only as inert link-target metadata in the manifest. Two originally point to absolute host paths. They are never tar link entries and the restore tool never creates or follows them. The two diagnostic `physical/` directories contain only their archived regular files after a fresh restore. Reproducing a diagnostic that deliberately creates aliases requires separately reviewing and running its source; restoration itself executes no artifact code.

## Check and restore

From the repository root, with Python 3.9+ on a POSIX host supporting no-follow and directory-descriptor operations:

```sh
python3 -B scripts/restore_amind_review_artifacts.py
python3 -B scripts/restore_amind_review_artifacts.py --apply
```

The default command validates the archive and member hashes, the exact allowed member sets, and all current destinations. It reports missing files without writing. `--apply` restores missing regular files under the selected repository root. Existing files with identical contents are accepted; any different existing file, file/link conflict, or symlink parent rejects the operation before restoration begins. Files are installed through no-follow directory descriptors and an atomic operation that cannot replace an existing destination. Runtime races or I/O failures can still stop an apply after earlier missing files were restored; a repeated apply safely accepts those identical files.

To check or restore another existing checkout, add `--root /path/to/checkout`. The manifest defaults to this script's checkout; `--manifest` selects another copy of the same archive-manifest format. Archive names and destination prefixes are fixed in the tool: a manifest cannot route data into `skills/`, `.git/`, or another arbitrary destination. The tool rejects traversal, absolute paths, duplicate or unexpected members, tar symlinks/hardlinks, invalid checksums, excessive sizes, and gzip expansion beyond the declared inventory bound. All member paths and parent prefixes also undergo a conservative Unicode NFD/casefold collision check, rejecting file/directory conflicts and aliases before writing, including on case-insensitive macOS volumes. Checksums establish byte integrity against the selected manifest, not independent provenance or a signature.

Study links into `agent-runs/` and `runs/` resolve locally after restoration. To check the original October 19 fingerprints after restoring into this checkout:

```sh
python3 -B reviews/2026-10-19-workplace/capture_fingerprint.py --verify
python3 -B reviews/2026-10-19-workplace/capture_fingerprint.py --plan repair-plan.json --verify
```

## Packaging and verification

```sh
python3 -B scripts/package_amind_review_artifacts.py
python3 -B scripts/test_restore_amind_review_artifacts.py
```

The packager reads the complete original directories, including ignored files, and sorts all member paths. Tar timestamps, owner IDs and names are fixed, modes are `0644`, and gzip has zero timestamp and no filename. It refuses to replace a different existing archive or manifest; its original regular-file bytes remain authoritative. Repeating the build in the recorded environment produced identical archive and manifest bytes. Codec versions may produce different compressed bytes on another host even with matching payload hashes.

[archive-validation.json](archive-validation.json) records 15 shipping-specific tests. They include an actual fresh-tree restore of all 4,571 files with every hash checked, repeated identical restoration, CLI check-only behavior, changed-content conflict preflight, traversal, arbitrary destination, archive/member checksum failures, duplicate/extra/missing members, links, symlink parents/destinations, case/Unicode/file-prefix aliases and bounded gzip expansion. These tests are separate from the current 220 product checks and from the 48 target model executions. Independent review reproduced a case-insensitive path collision before the namespace check was added; that failed implementation was corrected before shipping.

Full third-party source captures in the October 18 release remain a separate self-contained research artifact. Some public page HTML includes public client bootstrap keys and telemetry; the publication audit did not identify user/provider authentication credentials. Third-party material retains its original rights and is not relicensed as project software. Historical host paths in receipts remain provenance metadata. This shipping package does not improve the studies' inference, isolation or production-representativeness limits.
