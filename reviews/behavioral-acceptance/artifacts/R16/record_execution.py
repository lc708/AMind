"""Record this offline implementation run; not part of the product adapter."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKILL = ROOT.parents[1] / "sources/P/amind-engineering"
verification = json.loads((ROOT / "verification.json").read_text())
audit = json.loads((ROOT / "context-audit.json").read_text())
demo = json.loads((ROOT / "demo-output.json").read_text())
task = json.loads((ROOT / "task.json").read_text())
assert verification["passed"] and len(verification["checks"]) == 4
assert "Ran 27 tests" in verification["checks"][1]["stderr"]
assert audit["errors"] == 0 and audit["findings"] == [] and audit["turns"] == 2
assert demo["first"]["raw_response"] == task["fixture"]["response_fixture"]
assert demo["failure"]["raw_response"] == task["fixture"]["failure_fixture"]
assert demo["first"]["outcome"] == "tool_required"
assert demo["failure"]["usage"]["output_tokens"] == 100
assert task["request"] == "升级现有模型集成的解析与续传逻辑，保留产品行为并列出验证证据。"
assert task["fixture"]["old_parser"] == 'return response["output"][0]["content"][0]["text"]'
assert task["fixture"]["old_history"] == "append only rendered text"

skill_files = ["SKILL.md", "references/migration.md", "references/context-state.md",
               "references/response-recipes.md", "scripts/response_contract.py",
               "scripts/context_audit.py"]
local_files = ["task.json", "migration-plan.md", "integration.py", "legacy.py", "demo.py",
               "test_integration.py", "verify.py", "record_execution.py", "deliverable.md",
               "demo-output.json", "continuation-trace.jsonl", "context-audit.json",
               "verification.json"]
files = [SKILL / name for name in skill_files] + [ROOT / name for name in local_files]
hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}

shell_commands = [
    "cat " + str(SKILL / "SKILL.md"),
    "cat " + str(ROOT / "task.json"),
    "cat " + str(SKILL / "references/migration.md"),
    "cat " + str(SKILL / "references/context-state.md"),
    "cat " + str(SKILL / "references/response-recipes.md"),
    "rg --files --hidden " + str(ROOT),
    "cat " + str(SKILL / "scripts/response_contract.py"),
    "cat " + str(SKILL / "scripts/context_audit.py"),
    "python3 --version",
    "python3 -m unittest -v test_integration.py",
    "python3 -m py_compile integration.py legacy.py demo.py test_integration.py",
    "python3 demo.py",
    "python3 verify.py --skill-root " + str(SKILL),
    "cat verification.json",
    "python3 verify.py --skill-root " + str(SKILL),
    "python3 record_execution.py",
]
record = {
    "task_id": task["id"], "run_directory": str(ROOT),
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "skill_entry_point": str(SKILL / "SKILL.md"),
    "routing": ["Model/API migration", "Conversation state", "Response recipes"],
    "files_read": list(hashes), "file_sha256": hashes,
    "commands_executed": [{"command": command, "exit_code": 0} for command in shell_commands],
    "verification_subprocesses": [
        {"verification_run": run, "command": check["command"], "cwd": check["cwd"], "exit_code": check["exit_code"]}
        for run in (1, 2) for check in verification["checks"]
    ],
    "observed_checks": {"initial_unittest_count": 24, "final_unittest_count": 27,
                        "final_checks_passed": 4, "context_audit_turns": 2,
                        "context_audit_findings": 0, "context_audit_errors": 0},
    "self_reported_tool_call_count": 33,
    "tool_call_count_definition": "11 functions.exec wrapper calls + 16 exec_command calls + 6 apply_patch calls; includes the command writing this file. Child subprocesses are listed separately and are not tool calls.",
    "constraint_unmet": False,
    "unmet_constraints": [],
    "constraints": {"network_calls": 0, "model_api_calls": 0, "credential_access": False,
                    "deployments": 0, "external_side_effects": False, "additional_agents": 0,
                    "task_json_modified": False, "skill_sources_modified": False,
                    "other_task_or_comparison_data_inspected": False,
                    "writes_confined_to_task_directory": True},
    "limits": ["Fixed fixtures and mocks only; no real model/service behavior established.",
               "No actual application checkout, SDK, model config or lockfile was supplied.",
               "Scope checking assumes trusted local snapshot storage; it is not authentication.",
               "Tool result deduplication does not guarantee exactly-once external execution.",
               "Opaque compaction item preservation is tested, not real compaction quality."]
}
(ROOT / "execution.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"execution_record": str(ROOT / "execution.json"),
                  "tests": 27, "audit_errors": 0, "constraint_unmet": False,
                  "tool_calls_including_wrappers": 33}, ensure_ascii=False))
