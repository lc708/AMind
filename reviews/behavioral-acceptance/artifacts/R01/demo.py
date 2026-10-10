"""Replay task.json's crash timeline using two local SQLite databases."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from recovery import Recovery, FixedRemote, fixture, fixture_context


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--crash-worker", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.crash_worker:
        remote = FixedRemote(args.out / "remote.sqlite")
        worker = Recovery(args.out / "local.sqlite", remote, lambda: 100.0)
        worker.execute(fixture_context(), fixture()["operation"], after_remote=lambda: os._exit(73))
        raise RuntimeError("crash seam was not reached")
    if (args.out / "local.sqlite").exists() or (args.out / "remote.sqlite").exists():
        parser.error("choose a fresh output directory; existing evidence is preserved")
    crashed = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                              "--out", str(args.out), "--crash-worker"], check=False)
    if crashed.returncode != 73:
        raise RuntimeError(f"unexpected worker exit: {crashed.returncode}")
    remote = FixedRemote(args.out / "remote.sqlite")
    worker = Recovery(args.out / "local.sqlite", remote, lambda: 102.0)
    try:
        before = worker.inspect(fixture_context(), fixture()["operation"])
        recovered = worker.execute(fixture_context(), fixture()["operation"])
        replayed = worker.execute(fixture_context(), fixture()["operation"])
        report = {"evidence_kind": "fixed local mock; real subprocess exit and SQLite restart",
                  "worker_exit": crashed.returncode, "before_recovery": before,
                  "recovered": recovered, "replayed": replayed,
                  "remote_effect_count": remote.count(),
                  "recovery_charge_requests": remote.charge_calls,
                  "recovery_lookup_requests": remote.lookup_calls}
        assert before["state"] == "unknown"
        assert recovered["result"]["operation_id"] == "op1"
        assert recovered == replayed
        assert remote.count() == 1 and remote.charge_calls == 0 and remote.lookup_calls == 1
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        (args.out / "report.json").write_text(rendered)
        print(rendered)
    finally:
        worker.close()
        remote.close()


if __name__ == "__main__":
    main()
