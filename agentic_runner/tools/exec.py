import subprocess
from pathlib import Path
from typing import Any, Dict, List

ALLOWED = {"python", "pytest", "git"}


def run_cmd(workspace: Path, cmd: List[str], timeout_s: int = 120) -> Dict[str, Any]:
    if not cmd:
        raise ValueError("Empty cmd")
    if cmd[0] not in ALLOWED:
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
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }
