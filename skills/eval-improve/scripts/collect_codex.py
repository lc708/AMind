#!/usr/bin/env python3
"""Plan, or explicitly execute, bounded fresh Codex runs. Does not grade outputs."""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import unicodedata
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def append(path, value):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def prepare(args):
    if not re.fullmatch(r"baseline|v[1-9][0-9]*", args.variant):
        raise ValueError("variant must be baseline, v1, v2, ...")
    if args.reps < 1 or args.max_runs < 1 or not 1 <= args.timeout <= 3600:
        raise ValueError("reps/max-runs must be positive; timeout must be 1..3600 seconds")
    if not args.target_version.strip():
        raise ValueError("target-version must identify the actual target snapshot")
    if not args.workspace.is_dir():
        raise ValueError("workspace must be an existing directory")
    if (args.flow / args.variant).exists():
        raise ValueError("variant already exists; use a new flow/variant, not an overwrite or implicit resume")
    state_bytes = (args.flow / "_state.json").read_bytes()
    state = json.loads(state_bytes)
    if not isinstance(state, dict):
        raise ValueError("_state.json must be an object")
    seen = set()
    for split in ("train", "val", "test"):
        ids = state.get(f"{split}_ids", [])
        if (not isinstance(ids, list) or any(not isinstance(x, str) for x in ids)
                or len(ids) != len(set(ids)) or seen.intersection(ids)):
            raise ValueError("split IDs must be unique strings with no overlap")
        seen.update(ids)
    selected = state.get(f"{args.split}_ids", [])
    if not selected:
        raise ValueError("selected split must contain cases")
    if "reps" in state and (type(state["reps"]) is not int or state["reps"] != args.reps):
        raise ValueError("reps must match _state.json")
    cases_bytes = args.cases.read_bytes()
    cases = {}
    for line_no, line in enumerate(cases_bytes.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not isinstance(case, dict) or set(case) - {"id", "prompt", "tags"}:
            raise ValueError(f"case line {line_no}: allowed fields are id, prompt, tags; keep answers separate")
        case_id = case.get("id")
        if (not isinstance(case_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", case_id)):
            raise ValueError(f"case line {line_no}: use a path-safe case ID (1..80 characters)")
        folded = unicodedata.normalize("NFKC", case_id).casefold()
        if any(unicodedata.normalize("NFKC", previous).casefold() == folded for previous in cases):
            raise ValueError("duplicate or case-insensitive case ID collision")
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError(f"case {case_id}: prompt must be nonempty text")
        tags = case.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError(f"case {case_id}: tags must be a list of strings")
        cases[case_id] = case
    if set(cases) != set(selected):
        raise ValueError("case IDs must match exactly the selected split; supply a split-specific input file")
    count = len(selected) * args.reps
    if count > args.max_runs:
        raise ValueError(f"planned {count} runs exceed max-runs={args.max_runs}")
    plan = {
        "format_version": 1, "variant": args.variant, "split": args.split,
        "case_ids": selected, "reps": args.reps, "planned_runs": count,
        "max_runs": args.max_runs, "timeout_seconds_per_run": args.timeout,
        "target_version": args.target_version,
        "workspace": str(args.workspace.resolve()),
        "state_sha256": digest(state_bytes), "cases_sha256": digest(cases_bytes),
        "collector_sha256": digest(Path(__file__).read_bytes()),
        "requested_model": args.model, "requested_profile": args.profile,
        "codex_executable": args.codex, "sandbox": "read-only", "ephemeral": True,
        "grading": "none; successful captures remain ungraded",
        "limits": "Run/time limits are not a token/dollar cap. Read-only is not answer or tool isolation."
    }
    return plan, [cases[case_id] for case_id in selected]


def command(args, final_path, executable):
    cmd = [executable, "exec", "--json", "--ephemeral", "--sandbox", "read-only",
           "--skip-git-repo-check", "--color", "never", "--cd", str(args.workspace.resolve()),
           "--output-last-message", str(final_path.resolve())]
    if args.model:
        cmd += ["--model", args.model]
    if args.profile:
        cmd += ["--profile", args.profile]
    return cmd + ["-"]


def read_events(path):
    completed, usage, malformed, failed = 0, [], False, False
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("event must be an object")
            except ValueError:
                malformed = True
                continue
            if event.get("type") == "turn.completed":
                completed += 1
                if isinstance(event.get("usage"), dict):
                    usage.append(event["usage"])
            if event.get("type") in {"turn.failed", "error"}:
                failed = True
    return completed, usage, malformed, failed


def capture(args, case, rep, variant, executable):
    stem = f"{case['id']}_rep{rep}"
    events = variant / "raw" / f"{stem}.events.jsonl"
    stderr = variant / "raw" / f"{stem}.stderr.txt"
    final = variant / "raw" / f"{stem}.final.txt"
    cmd = command(args, final, executable)
    started = time.monotonic()
    timed_out = False
    with events.open("wb") as stdout_handle, stderr.open("wb") as stderr_handle:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=stdout_handle,
                                   stderr=stderr_handle, start_new_session=(os.name == "posix"))
        try:
            process.communicate(case["prompt"].encode("utf-8"), timeout=args.timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.communicate()
            if isinstance(exc, KeyboardInterrupt):
                raise
            timed_out = True
    completed, usage, malformed, failed = read_events(events)
    output = final.read_text(encoding="utf-8") if final.exists() else ""
    if timed_out:
        status = "timeout"
    elif process.returncode != 0 or failed:
        status = "runtime_error"
    elif malformed or completed != 1 or not output.strip():
        status = "incomplete"
    else:
        status = "ungraded"
    row = {
        "prompt_id": case["id"], "rep": rep, "attempt": 1,
        "prompt": case["prompt"], "tags": case.get("tags", []),
        "status": status, "grade": {}, "output": output,
        "latency_s": round(time.monotonic() - started, 6),
        "meta": {"target_version": args.target_version, "requested_model": args.model,
                 "requested_profile": args.profile, "provider_native_usage": usage,
                 "returncode": process.returncode, "raw_events": f"raw/{events.name}",
                 "stderr": f"raw/{stderr.name}", "command": cmd}
    }
    dump(variant / "traces" / f"{stem}.json",
         [{"role": "user", "content": case["prompt"]}, {"role": "assistant", "content": output}])
    append(variant / "captures.jsonl", row)
    if status != "ungraded":
        append(variant / "errors.jsonl", row)
    return status


def execute(args, plan, cases):
    executable = shutil.which(args.codex)
    if not executable:
        raise ValueError("Codex executable not found; plan mode does not require it")
    version = subprocess.run([executable, "--version"], capture_output=True, text=True,
                             timeout=10, check=True).stdout.strip()
    variant = args.flow / args.variant
    variant.mkdir()  # Exclusive creation prevents overwriting existing evidence.
    (variant / "raw").mkdir()
    (variant / "traces").mkdir()
    dump(variant / "run-plan.json", {**plan, "codex_version": version})
    summary = {"planned_runs": plan["planned_runs"], "attempted_runs": 0,
               "ungraded": 0, "failed": 0, "complete": False}
    dump(variant / "run-summary.json", summary)
    try:
        for case in cases:
            for rep in range(args.reps):
                summary["attempted_runs"] += 1
                dump(variant / "run-summary.json", summary)
                status = capture(args, case, rep, variant, executable)
                summary["ungraded" if status == "ungraded" else "failed"] += 1
                dump(variant / "run-summary.json", summary)
    finally:
        summary["complete"] = (summary["ungraded"] + summary["failed"] == plan["planned_runs"])
        dump(variant / "run-summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flow", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--split", required=True, choices=["train", "val", "test"])
    parser.add_argument("--target-version", required=True)
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--max-runs", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--model")
    parser.add_argument("--profile")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        plan, cases = prepare(args)
        if not args.execute:
            print(json.dumps({"mode": "plan", **plan}, ensure_ascii=False, indent=2))
            return 0
        summary = execute(args, plan, cases)
        print(json.dumps({"mode": "executed", **summary}, ensure_ascii=False, indent=2))
        return 0 if summary["complete"] and not summary["failed"] else 2
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False))
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "error": "Partial evidence retained; no automatic retry."}))
        return 130


if __name__ == "__main__":
    sys.exit(main())
