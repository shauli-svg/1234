from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agentic_runner.runner import run_pipeline

BASE_DIR = Path(__file__).resolve().parents[2]
RUNS_DIR = BASE_DIR / "_runs"
WORK_DEFAULT = BASE_DIR / "_demo_workspace"
SPECS_DIR = BASE_DIR / "examples"
APPROVAL_DB = BASE_DIR / "services" / "approval_server" / "approval_db.json"

app = FastAPI(title="MergePack Agent Runner API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    spec_path: str
    workspace: Optional[str] = None
    auto_approve: bool = False
    llm_provider: str = "mock"


class ApprovalDecision(BaseModel):
    approved: bool
    by: str = "human"
    note: Optional[str] = None


def _load_approval_db() -> Dict[str, Any]:
    if not APPROVAL_DB.exists():
        return {"requests": {}}
    return json.loads(APPROVAL_DB.read_text(encoding="utf-8"))


def _save_approval_db(db: Dict[str, Any]) -> None:
    APPROVAL_DB.parent.mkdir(parents=True, exist_ok=True)
    APPROVAL_DB.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/api/runs")
def create_run(req: RunRequest, background_tasks: BackgroundTasks) -> Dict[str, str]:
    spec_file = BASE_DIR / req.spec_path
    if not spec_file.exists():
        raise HTTPException(status_code=400, detail="Spec not found")

    raw_spec = json.loads(spec_file.read_text(encoding="utf-8"))
    run_id = raw_spec.get("run_id") or uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    base_status = {"run_id": run_id, "status": "pending", "error": None, "spec_path": req.spec_path}
    (run_dir / "status.json").write_text(json.dumps(base_status), encoding="utf-8")

    workspace_dir = Path(req.workspace).resolve() if req.workspace else WORK_DEFAULT

    def _job() -> None:
        try:
            (run_dir / "status.json").write_text(json.dumps({**base_status, "status": "running"}), encoding="utf-8")
            spec = {**raw_spec, "run_id": run_id}
            run_pipeline(
                spec=spec,
                workspace_dir=workspace_dir,
                out_dir=RUNS_DIR,
                auto_approve=req.auto_approve,
                llm_provider=req.llm_provider,
            )
            (run_dir / "status.json").write_text(json.dumps({**base_status, "status": "completed"}), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            (run_dir / "status.json").write_text(
                json.dumps({**base_status, "status": "failed", "error": str(exc)}),
                encoding="utf-8",
            )

    background_tasks.add_task(_job)
    return {"run_id": run_id}


@app.get("/api/runs")
def list_runs() -> List[Dict[str, Any]]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    for path in RUNS_DIR.glob("*"):
        if not path.is_dir():
            continue
        status_file = path / "status.json"
        if status_file.exists():
            status = json.loads(status_file.read_text(encoding="utf-8"))
        else:
            status = {"run_id": path.name, "status": "unknown", "error": None}
        results.append(status)
    return sorted(results, key=lambda item: item["run_id"], reverse=True)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    status_file = run_dir / "status.json"
    status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else None

    final_file = run_dir / "final.json"
    final = json.loads(final_file.read_text(encoding="utf-8")) if final_file.exists() else None

    return {"status": status, "final": final}


@app.get("/api/runs/{run_id}/events")
def get_events(run_id: str) -> List[Dict[str, Any]]:
    log_file = RUNS_DIR / run_id / "run.jsonl"
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.get("/api/runs/{run_id}/artifacts")
def list_artifacts(run_id: str) -> List[str]:
    art_dir = RUNS_DIR / run_id / "artifacts"
    if not art_dir.exists():
        return []
    files: List[str] = []
    for path in art_dir.rglob("*"):
        if path.is_file():
            files.append(str(path.relative_to(art_dir)))
    return sorted(files)


@app.get("/api/runs/{run_id}/artifacts/{artifact_path:path}")
def get_artifact(run_id: str, artifact_path: str) -> FileResponse:
    art_dir = RUNS_DIR / run_id / "artifacts"
    target = (art_dir / artifact_path).resolve()
    if not str(target).startswith(str(art_dir.resolve())) or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(target)


@app.get("/api/specs")
def list_specs() -> List[Dict[str, str]]:
    specs: List[Dict[str, str]] = []
    for path in SPECS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        specs.append({"name": data.get("name", path.name), "file": str(path.relative_to(BASE_DIR))})
    return sorted(specs, key=lambda item: item["file"])


@app.get("/api/specs/{spec_name}")
def get_spec(spec_name: str) -> Dict[str, Any]:
    path = SPECS_DIR / spec_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Spec not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/approvals")
def list_approvals(status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _load_approval_db()
    items = list(db.get("requests", {}).values())
    if status:
        items = [item for item in items if item.get("status") == status]
    items.sort(key=lambda item: item.get("created_at", 0), reverse=True)
    return items


@app.get("/api/approvals/{request_id}")
def get_approval(request_id: str) -> Dict[str, Any]:
    db = _load_approval_db()
    item = db.get("requests", {}).get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    return item


@app.post("/api/approvals/{request_id}/decide")
def decide_approval(request_id: str, decision: ApprovalDecision) -> Dict[str, Any]:
    db = _load_approval_db()
    item = db.get("requests", {}).get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    if item.get("status") != "pending":
        raise HTTPException(status_code=400, detail="already decided")

    item["decision"] = decision.model_dump()
    item["status"] = "approved" if decision.approved else "denied"
    db["requests"][request_id] = item
    _save_approval_db(db)
    return item
