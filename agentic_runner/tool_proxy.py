import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

from .approval_client import request_and_wait
from .events import EventLog
from .policy import PolicyEngine


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    risk: str


class ToolProxy:
    def __init__(self, workspace_dir: Path, policy: PolicyEngine, log: EventLog):
        self.workspace_dir = workspace_dir
        self.policy = policy
        self.log = log
        self.tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def call(self, name: str, **kwargs: Any) -> Any:
        if name not in self.tools:
            self.log.emit("tool_denied", tool=name, reason="Tool not allowlisted")
            raise PermissionError(f"Tool not allowlisted: {name}")

        spec = self.tools[name]
        decision = self.policy.decide(tool_name=name, args=kwargs, tool_risk=spec.risk)
        self.log.emit("policy_decision", tool=name, decision=decision.__dict__, args=kwargs)

        if not decision.allow:
            raise PermissionError(decision.reason)

        if decision.requires_approval:
            approval_server = os.environ.get("APPROVAL_SERVER")
            if approval_server:
                trace_id = uuid.uuid4().hex[:12]
                self.log.emit("approval_requested", tool=name, args=kwargs, trace_id=trace_id)
                approved = request_and_wait(
                    tool=name,
                    args=kwargs,
                    reason=decision.reason,
                    trace_id=trace_id,
                    risk=decision.risk,
                )
                self.log.emit("approval_result", tool=name, approved=approved, trace_id=trace_id)
                if not approved:
                    raise PermissionError("Remote approval denied or timed out")
            else:
                prompt = f"[APPROVAL REQUIRED] Tool '{name}' requested with args={kwargs}. Approve? (y/N): "
                approved = input(prompt).strip().lower() == "y"
                self.log.emit("approval", tool=name, approved=approved)
                if not approved:
                    raise PermissionError("User denied approval")

        self.log.emit("tool_call", tool=name, args=kwargs)
        out = spec.fn(self.workspace_dir, **kwargs)
        self.log.emit("tool_result", tool=name, result=out if _is_jsonable(out) else str(out))
        return out


def _is_jsonable(value: Any) -> bool:
    try:
        json.dumps(value)
    except Exception:
        return False
    return True
