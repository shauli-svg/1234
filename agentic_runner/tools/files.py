from pathlib import Path
from typing import Any, Dict


def _safe_path(workspace: Path, path: str) -> Path:
    resolved = (workspace / path).resolve()
    if not str(resolved).startswith(str(workspace.resolve())):
        raise PermissionError("Path traversal blocked")
    return resolved


def read_text(workspace: Path, path: str) -> Dict[str, Any]:
    p = _safe_path(workspace, path)
    return {"path": str(p), "text": p.read_text(encoding="utf-8")}


def write_text(workspace: Path, path: str, text: str) -> Dict[str, Any]:
    p = _safe_path(workspace, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return {"path": str(p), "bytes": len(text.encode("utf-8"))}
