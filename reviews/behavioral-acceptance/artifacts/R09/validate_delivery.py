"""Final local artifact check; also records this audit's actual result."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
execution_path = ROOT / "execution.json"
record = json.loads(execution_path.read_text(encoding="utf-8"))
try:
    task = json.loads((ROOT / "task.json").read_text(encoding="utf-8"))
    assert task == {
        "id": "G04",
        "request": "修复流式与批处理的结果判定，写出本地可运行的契约测试。",
        "fixture": {
            "stream": [{"type": "response.created"}, {"type": "response.output_text.delta", "delta": "Done"}],
            "existing_stream_success": "any text received",
            "batch_requested": ["a", "b", "c"],
            "batch_returned": [
                {"custom_id": "b", "error": {"code": "expired"}},
                {"custom_id": "a", "response": {"status_code": 200, "body": {"status": "completed"}}}
            ],
            "existing_batch_join": "zip(requests,results)"
        },
        "constraints": [
            "仅使用本地固定数据，不调用目标模型 API",
            "允许在当前任务目录创建代码、测试和交付文档",
            "保持原始输入和约束；不得改评测要求以获得高分"
        ],
        "deliverable": "deliverable.md plus runnable code/tests when appropriate; report actual commands and results"
    }, "Original task content changed"
    report = json.loads((ROOT / "fixture_result.json").read_text(encoding="utf-8"))
    assert report["stream"]["status"] == "disconnected"
    assert report["stream"]["transport_success"] is False
    assert [(r["custom_id"], r["status"]) for r in report["batch"]["ordered"]] == [
        ("a", "completed"), ("b", "batch_error"), ("c", "missing")]
    assert report["batch"]["ordered"][1]["error"]["code"] == "expired"
    log = (ROOT / "verification.log").read_text(encoding="utf-8")
    assert "Ran 26 tests" in log and log.rstrip().endswith("OK")
    assert "26 个本地契约测试通过" in (ROOT / "deliverable.md").read_text(encoding="utf-8")
    for name in record["files_written"]:
        assert (ROOT / name).is_file(), name
    record["task_json_sha256"] = hashlib.sha256((ROOT / "task.json").read_bytes()).hexdigest()
    record["commands_executed"][-1].update(exit_code=0, result="Artifact audit passed; original task content is intact.")
    print("Artifact audit passed; original task content is intact.")
except Exception as exc:
    record["commands_executed"][-1].update(exit_code=1, result=str(exc))
    raise
finally:
    execution_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
