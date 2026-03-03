from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="ActionGate Approval Server (MVP)")
DB_PATH = Path("./approval_db.json")


def _load_db() -> Dict[str, Any]:
    if not DB_PATH.exists():
        return {"requests": {}}
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def _save_db(db: Dict[str, Any]) -> None:
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


class ApprovalRequestIn(BaseModel):
    tool: str
    args: Dict[str, Any]
    reason: str
    action_hash: str
    trace_id: str
    risk: str = "high"
    created_by: str = "agent"


class ApprovalDecision(BaseModel):
    approved: bool
    by: str = "human"
    note: Optional[str] = None


class ApprovalRequestOut(BaseModel):
    id: str
    status: str
    request: ApprovalRequestIn
    created_at: float
    decision: Optional[ApprovalDecision] = None


@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/requests", response_model=ApprovalRequestOut)
def create_request(req: ApprovalRequestIn) -> Dict[str, Any]:
    db = _load_db()
    request_id = uuid.uuid4().hex[:12]
    item: Dict[str, Any] = {
        "id": request_id,
        "status": "pending",
        "created_at": time.time(),
        "request": req.model_dump(),
        "decision": None,
    }
    db["requests"][request_id] = item
    _save_db(db)
    return item


@app.get("/requests", response_model=List[ApprovalRequestOut])
def list_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _load_db()
    items = list(db["requests"].values())
    if status:
        items = [item for item in items if item["status"] == status]
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items


@app.get("/requests/{request_id}", response_model=ApprovalRequestOut)
def get_request(request_id: str) -> Dict[str, Any]:
    db = _load_db()
    item = db["requests"].get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    return item


@app.post("/requests/{request_id}/decide", response_model=ApprovalRequestOut)
def decide(request_id: str, decision: ApprovalDecision) -> Dict[str, Any]:
    db = _load_db()
    item = db["requests"].get(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="not found")
    if item["status"] != "pending":
        raise HTTPException(status_code=400, detail="already decided")

    item["decision"] = decision.model_dump()
    item["status"] = "approved" if decision.approved else "denied"
    db["requests"][request_id] = item
    _save_db(db)
    return item
