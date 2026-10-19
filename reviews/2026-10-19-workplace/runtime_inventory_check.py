#!/usr/bin/env python3
"""No-model preflight for a study that explicitly requires zero enabled MCP servers."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Do not overwrite a preflight receipt")
    argv = [args.cli, "--no-daemon", "--profile", args.profile, "mcp", "list", "--json"]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    servers = json.loads(result.stdout) if result.returncode == 0 else None
    if servers is not None and (not isinstance(servers, list) or any(not isinstance(s.get("enabled"), bool) for s in servers)):
        raise ValueError("Unknown tool inventory schema; fail closed")
    effective = [{"name": s["name"], "enabled": s["enabled"]} for s in servers] if servers is not None else None
    passed = result.returncode == 0 and not any(s["enabled"] for s in effective)
    receipt = {"at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "argv": argv,
               "cwd": str(Path.cwd()), "returncode": result.returncode, "effective_mcp_servers": effective,
               "all_effective_mcp_disabled": passed, "model_calls": 0,
               "limits": "Inventory check only; does not establish every OS or network boundary. Audit all actual tool calls after execution as well."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": passed, "profile": args.profile, "receipt": str(args.out)}))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
