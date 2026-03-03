import argparse
import json
from pathlib import Path

from .runner import run_pipeline


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentic_runner", description="MergePack safe-by-default runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    runp = sub.add_parser("run", help="Run a pipeline spec")
    runp.add_argument("--spec", required=True, help="Path to JSON spec file")
    runp.add_argument("--workspace", default="./_work", help="Workspace directory")
    runp.add_argument("--out", default="./_runs", help="Output runs directory")
    runp.add_argument("--auto-approve", action="store_true", help="Auto-approve high-impact actions")
    runp.add_argument("--llm", default="mock", help="LLM provider (mock)")

    args = parser.parse_args()

    spec_path = Path(args.spec).expanduser().resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    run_id = run_pipeline(
        spec=spec,
        workspace_dir=_ensure_dir(Path(args.workspace).expanduser().resolve()),
        out_dir=_ensure_dir(Path(args.out).expanduser().resolve()),
        auto_approve=args.auto_approve,
        llm_provider=args.llm,
    )
    print(run_id)
