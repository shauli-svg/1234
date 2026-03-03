import hashlib
import json
import os
import time
import urllib.request
from typing import Any, Dict


def action_hash(tool: str, args: Dict[str, Any]) -> str:
    payload = json.dumps({"tool": tool, "args": args}, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def request_and_wait(
    tool: str,
    args: Dict[str, Any],
    reason: str,
    trace_id: str,
    risk: str = "high",
    timeout_s: int = 600,
) -> bool:
    base = os.environ.get("APPROVAL_SERVER")
    if not base:
        raise RuntimeError("APPROVAL_SERVER is not set")

    req = {
        "tool": tool,
        "args": args,
        "reason": reason,
        "action_hash": action_hash(tool, args),
        "trace_id": trace_id,
        "risk": risk,
        "created_by": "agent",
    }
    rid = _post_json(f"{base}/requests", req)["id"]

    start = time.time()
    while time.time() - start < timeout_s:
        cur = _get_json(f"{base}/requests/{rid}")
        if cur["status"] == "approved":
            return True
        if cur["status"] == "denied":
            return False
        time.sleep(2)
    return False


def _get_json(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))
