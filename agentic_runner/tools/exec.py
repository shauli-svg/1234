import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Union

DEFAULT_ALLOWED = {"python", "pytest", "git", "ls", "dir", "cat", "type"}


def _allowed_cmds() -> set[str]:
    env_value = os.environ.get("ALLOWED_CMDS")
    if not env_value:
        return DEFAULT_ALLOWED
    return {item.strip() for item in env_value.split(",") if item.strip()}


def run_cmd(workspace: Path, cmd: Union[List[str], str], timeout_s: int = 120) -> Dict[str, Any]:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)

    if not cmd:
        raise ValueError("Empty cmd")

    allowed = _allowed_cmds()
    if cmd[0] not in allowed:
        raise PermissionError(f"Command not allowlisted: {cmd[0]}")

    proc = subprocess.run(
        cmd,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )
    return {
        "cmd": cmd,
        "allowed_cmds": sorted(allowed),
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }
