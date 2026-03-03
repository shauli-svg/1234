import json
import uuid
from pathlib import Path
from typing import Any, Dict

from .events import EventLog
from .llm.provider import LLMProvider, MockLLM
from .policy import PolicyEngine
from .tool_proxy import ToolProxy, ToolSpec
from .tools.exec import run_cmd
from .tools.files import read_text, write_text


def _load_llm(name: str) -> LLMProvider:
    if name == "mock":
        return MockLLM()
    raise ValueError("Unknown LLM provider. Implement your provider in agentic_runner/llm/provider.py")


def run_pipeline(*, spec: Dict[str, Any], workspace_dir: Path, out_dir: Path, auto_approve: bool, llm_provider: str) -> str:
    run_id = spec.get("run_id") or uuid.uuid4().hex[:12]
    run_path = out_dir / run_id
    artifacts = run_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    log = EventLog(run_path / "run.jsonl")
    log.emit("run_start", run_id=run_id, spec_name=spec.get("name"))

    policy = PolicyEngine(auto_approve=auto_approve)
    tools = ToolProxy(workspace_dir=workspace_dir, policy=policy, log=log)
    tools.register(ToolSpec(name="read_text", fn=read_text, risk="low"))
    tools.register(ToolSpec(name="write_text", fn=write_text, risk="high"))
    tools.register(ToolSpec(name="run_cmd", fn=run_cmd, risk="high"))

    llm = _load_llm(llm_provider)

    tasks = spec.get("tasks", [])
    if not tasks:
        raise ValueError("Spec must include tasks[]")

    final = {"run_id": run_id, "outputs": []}
    for task in tasks:
        output = _run_task(task=task, llm=llm, tools=tools, log=log)
        final["outputs"].append(output)

    (run_path / "final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    log.emit("run_end", run_id=run_id)
    return run_id


def _run_task(*, task: Dict[str, Any], llm: LLMProvider, tools: ToolProxy, log: EventLog) -> Dict[str, Any]:
    name = task.get("name", "task")
    goal = task.get("goal", "")
    context_files = task.get("context_files", [])

    context_blobs = []
    for path in context_files:
        try:
            context_blobs.append(tools.call("read_text", path=path))
        except Exception as exc:  # noqa: BLE001
            log.emit("context_read_error", path=path, error=str(exc))

    system = {"role": "system", "content": "You are an action-oriented agent. Always output structured JSON."}
    user = {
        "role": "user",
        "content": (
            f"Task: {name}\nGoal: {goal}\n"
            f"Context: {json.dumps(context_blobs, ensure_ascii=False)[:8000]}\n"
            "Return JSON with keys: plan, actions, final_output."
        ),
    }

    response = llm.chat([system, user], json_mode=True)
    content = response.get("content") or {}
    log.emit("llm_response", task=name, response=content, usage=response.get("usage"))

    executed = []
    for action in content.get("actions", []):
        tool = action.get("tool")
        args = action.get("args", {})
        if not tool:
            continue
        try:
            result = tools.call(tool, **args)
            executed.append({"tool": tool, "args": args, "result": result})
        except Exception as exc:  # noqa: BLE001
            executed.append({"tool": tool, "args": args, "error": str(exc)})

    checks = []
    for check in task.get("checks", []):
        kind = check.get("kind")
        if kind == "file_exists":
            path = (tools.workspace_dir / check["path"]).resolve()
            checks.append({"kind": kind, "ok": path.exists(), "path": str(path)})
        else:
            checks.append({"kind": kind, "ok": None, "note": "Unknown check kind in MVP"})

    return {
        "task": name,
        "goal": goal,
        "plan": content.get("plan"),
        "executed_actions": executed,
        "checks": checks,
        "final_output": content.get("final_output") or content,
    }
