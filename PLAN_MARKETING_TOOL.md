# MergePack – Marketing-Friendly Free Tool Plan

## מטרת המסמך

להפוך את ה-MVP הקיים לכלי חינמי, מרשים וקל להרצה, שישמש **כדמו שיווקי ליכולות שלכם**:
- משתמש נכנס → מריץ scenario אמיתי → רואה UI מלא, LLM אמיתי, approvals, artifacts.
- המסר: *"מה שאתם רואים כאן, אנחנו יודעים לבנות מותאם אישית לארגון שלכם."*

---

## High-Level Architecture

- **Core**: `agentic_runner` – pipelines, tools, policy, approvals.
- **API**: FastAPI – חשיפת הכל כ-REST.
- **Frontend**: SPA (React / פשוט) – Dashboard + Run details + Approvals.
- **LLM**: pluggable – `mock` (ברירת מחדל), `openai` (לדמו אמיתי).
- **Spec-Driven**: דוגמאות שימוש תחת `examples/`.
- **Audit & Compliance**: `run.jsonl`, approvals, policy, artifacts.

---

## Phase 1 – LLM אמיתי (OpenAI Provider)

### 1.1 הרחבת `LLMProvider`

קובץ: `agentic_runner/llm/provider.py`

1. השאר את:
   - `LLMProvider` (interface)
   - `MockLLM` (לדמו אופליין)

2. הוסף `OpenAILLM`:

   ```python
   import os
   import openai
   from typing import Any, Dict, List

   class OpenAILLM(LLMProvider):
       def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
           self.client = openai.OpenAI(api_key=api_key)
           self.model = model

       def chat(self, messages: List[Dict[str, str]], *, json_mode: bool = False) -> Dict[str, Any]:
           params: Dict[str, Any] = {
               "model": self.model,
               "messages": messages,
           }
           if json_mode:
               params["response_format"] = {"type": "json_object"}

           resp = self.client.chat.completions.create(**params)
           content = resp.choices[0].message.content or "{}"
           usage = {
               "tokens_in": resp.usage.prompt_tokens if resp.usage else None,
               "tokens_out": resp.usage.completion_tokens if resp.usage else None,
           }
           return {
               "content": json.loads(content),
               "usage": usage,
           }
   ```

3. הגדרת prompt מערכת:

   ```python
   SYSTEM_PROMPT = """
   You are an action-oriented agent. You MUST respond with valid JSON only.
   Output format: {"plan": [...], "actions": [{"tool": "...", "args": {...}}], "final_output": "..."}.
   Available tools: read_text(path), write_text(path, text), run_cmd(cmd: array of strings).
   All file paths are relative to the workspace. Be concise. Use the minimum number of actions.
   """
   ```

   ומשתמשים בו ב-`_run_task`:

   ```python
   system = {"role": "system", "content": SYSTEM_PROMPT}
   ```

### 1.2 Loader דינמי לפי שם Provider

קובץ: `agentic_runner/runner.py`

```python
import os
from .llm.provider import LLMProvider, MockLLM, OpenAILLM

def _load_llm(name: str) -> LLMProvider:
    if name == "mock":
        return MockLLM()
    if name == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY required for openai provider")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        return OpenAILLM(api_key=api_key, model=model)
    raise ValueError(f"Unknown LLM provider: {name}")
```

### 1.3 טיפול בשגיאות LLM

- עטוף את הקריאה ב-try/except, ובלוג:
  - `kind="llm_error"`, כולל `error=str(e)` אבל בלי פרטי API.
- החזר `final_output` בסגנון:
  - `"LLM_ERROR: <short_message>"` כדי שה-frontend יציג הודעה ברורה.

---

## Phase 2 – API מאוחד (FastAPI)

### 2.1 יצירת שירות API

קובץ חדש: `services/api/main.py`

```python
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Any, Dict
import json
import uuid

from agentic_runner.runner import run_pipeline

BASE_DIR = Path(__file__).resolve().parents[2]
RUNS_DIR = BASE_DIR / "_runs"
WORK_DEFAULT = BASE_DIR / "_demo_workspace"

app = FastAPI(title="MergePack Agent Runner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # בדמו
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.2 מודל ריצה ברקע

1. פורמט סטטוס לכל run:
   - `status.json`:

     ```json
     {
       "run_id": "...",
       "status": "pending|running|completed|failed",
       "error": null
     }
     ```

2. `POST /api/runs`:

   ```python
   from pydantic import BaseModel

   class RunRequest(BaseModel):
       spec_path: str  # e.g. "examples/spec_doc_summary.json"
       workspace: str | None = None
       auto_approve: bool = False
       llm_provider: str = "mock"

   @app.post("/api/runs")
   async def create_run(req: RunRequest, background_tasks: BackgroundTasks):
       spec_file = BASE_DIR / req.spec_path
       if not spec_file.exists():
           raise HTTPException(status_code=400, detail="Spec not found")

       spec = json.loads(spec_file.read_text(encoding="utf-8"))
       run_id = spec.get("run_id") or uuid.uuid4().hex[:12]
       run_dir = RUNS_DIR / run_id
       run_dir.mkdir(parents=True, exist_ok=True)

       status = {"run_id": run_id, "status": "pending", "error": None}
       (run_dir / "status.json").write_text(json.dumps(status), encoding="utf-8")

       workspace_dir = Path(req.workspace).resolve() if req.workspace else WORK_DEFAULT

       def _job():
           try:
               (run_dir / "status.json").write_text(
                   json.dumps({**status, "status": "running"}), encoding="utf-8"
               )
               run_pipeline(
                   spec=spec,
                   workspace_dir=workspace_dir,
                   out_dir=RUNS_DIR,
                   auto_approve=req.auto_approve,
                   llm_provider=req.llm_provider,
               )
               (run_dir / "status.json").write_text(
                   json.dumps({**status, "status": "completed"}), encoding="utf-8"
               )
           except Exception as e:  # noqa: BLE001
               (run_dir / "status.json").write_text(
                   json.dumps(
                       {
                           **status,
                           "status": "failed",
                           "error": str(e),
                       }
                   ),
                   encoding="utf-8",
               )

       background_tasks.add_task(_job)
       return {"run_id": run_id}
   ```

3. Endpoints משלימים:

   ```python
   @app.get("/api/runs")
   def list_runs():
       results = []
       for p in RUNS_DIR.glob("*"):
           if not p.is_dir():
               continue
           status_file = p / "status.json"
           if status_file.exists():
               st = json.loads(status_file.read_text(encoding="utf-8"))
           else:
               st = {"run_id": p.name, "status": "unknown", "error": None}
           results.append(st)
       return sorted(results, key=lambda x: x["run_id"], reverse=True)

   @app.get("/api/runs/{run_id}")
   def get_run(run_id: str):
       run_dir = RUNS_DIR / run_id
       if not run_dir.exists():
           raise HTTPException(status_code=404, detail="Run not found")

       status_file = run_dir / "status.json"
       status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else None

       final_file = run_dir / "final.json"
       final = json.loads(final_file.read_text(encoding="utf-8")) if final_file.exists() else None

       return {"status": status, "final": final}

   @app.get("/api/runs/{run_id}/events")
   def get_events(run_id: str):
       run_dir = RUNS_DIR / run_id
       log_file = run_dir / "run.jsonl"
       if not log_file.exists():
           return []
       lines = log_file.read_text(encoding="utf-8").splitlines()
       return [json.loads(l) for l in lines]

   @app.get("/api/runs/{run_id}/artifacts")
   def list_artifacts(run_id: str):
       run_dir = RUNS_DIR / run_id
       art_dir = run_dir / "artifacts"
       if not art_dir.exists():
           return []
       files = []
       for p in art_dir.rglob("*"):
           if p.is_file():
               rel = p.relative_to(art_dir)
               files.append(str(rel))
       return files
   ```

### 2.3 Specs API

```python
SPECS_DIR = BASE_DIR / "examples"

@app.get("/api/specs")
def list_specs():
    specs = []
    for p in SPECS_DIR.glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        specs.append({"name": data.get("name", p.name), "file": str(p.relative_to(BASE_DIR))})
    return specs

@app.get("/api/specs/{spec_name}")
def get_spec(spec_name: str):
    p = SPECS_DIR / spec_name
    if not p.exists():
        raise HTTPException(status_code=404, detail="Spec not found")
    return json.loads(p.read_text(encoding="utf-8"))
```

---

## Phase 3 – Frontend (SPA)

### 3.1 בחירת טכנולוגיה

- **מומלץ:** React + Vite + TypeScript.
- למינימום תלויות אפשר גם HTML+JS יחיד, אבל React יראה "מודרני" יותר.

### 3.2 מבנה עיקרי

#### מסך 1 – Dashboard (`/`)

- טבלה של `runs`:
  - ID
  - Spec name
  - Status (badge)
  - Created (מ-`run_id`/event הראשון)
  - כפתור "View"
- כפתור "Start New Run".

Front-end logic:
- קריאה ל-`GET /api/runs` כל 5–10 שניות כאשר חלון פתוח.
- מיון לפי זמן (run_id או `ts` מה-events).

#### מסך 2 – New Run (`/runs/new`)

- Dropdown/spec list מ-`GET /api/specs`.
- הצגת JSON של ה-spec בצד ימין.
- שדה `Workspace` (ברירת מחדל `_demo_workspace`).
- Checkbox `Auto-approve high-risk actions`.
- Dropdown `LLM provider`: `mock` / `openai`.
- כפתור "Run":
  - שולח `POST /api/runs`.
  - Redirect אוטומטי ל-`/runs/{run_id}`.

#### מסך 3 – Run Detail (`/runs/{run_id}`)

Sections:

- **Header:**
  - Run ID
  - Status badge:
    - `pending` – אפור
    - `running` – כחול/טוען
    - `completed` – ירוק
    - `failed` – אדום + error message

- **Summary:**
  - Spec name (מתוך `final.outputs[0].task` / `spec.name` אם שמור)
  - Goal
  - זמן התחלה/סיום (מ-events `run_start`/`run_end`).

- **Plan:**
  - רשימת צעדים מ-`final.outputs[0].plan`.

- **Executed Actions:**
  - טבלה:
    - Tool
    - Args (קליק פותח JSON)
    - Result / Error (תקציר)
  - מקור: `final.outputs[0].executed_actions`.

- **Checks:**
  - רשימה עם check name + סטטוס OK/Fail.
  - מקור: `final.outputs[0].checks`.

- **Final Output:**
  - block של JSON/טקסט יפה.
  - מקור: `final.outputs[0].final_output`.

- **Artifacts:**
  - `GET /api/runs/{id}/artifacts` → רשימת קבצים.
  - כל קובץ: לינק ל-`/api/runs/{id}/artifacts/{path}` (הורדה/תצוגה).

- **Event Log:**
  - קריאה ל-`GET /api/runs/{id}/events`.
  - הצגה ברשימת timeline:
    - `ts` → `kind` → חלק מ-`data`.

Polling:
- כל עוד status `running` – Poll כל 2–3 שניות.
- אחרי `completed`/`failed` – עצור.

#### מסך 4 – Approvals (`/approvals`)

- מבוסס על הקוד הקיים של `mobile_pwa/index.html`, אבל:
  - משתמש ב-`/api/approvals/...` (לא ישירות ל-approval_server).
  - משולב בהפרדת layout עם שאר האפליקציה.

---

## Phase 4 – Demo Specs & Workspace

### 4.1 Demo Workspace

צור תיקייה: `_demo_workspace/`:

- `README.md` – תיאור קצר של דמו.
- `app.py` – קוד פייתון פשוט.
- `test_app.py` – בדיקה.

### 4.2 Specs לדמו

#### 1. `examples/spec_doc_summary.json`

```json
{
  "name": "Documentation Summary",
  "tasks": [
    {
      "name": "summarize_readme",
      "goal": "Read README.md and produce a short 3-bullet summary.",
      "context_files": ["README.md"],
      "checks": [
        { "kind": "file_exists", "path": "README.md" }
      ]
    }
  ]
}
```

#### 2. `examples/spec_run_tests.json`

```json
{
  "name": "Run Demo Tests",
  "tasks": [
    {
      "name": "run_pytests",
      "goal": "Run pytest on the demo workspace and summarize results.",
      "context_files": [],
      "checks": []
    }
  ]
}
```

ה-LLM יונחה להשתמש ב-`run_cmd` עם `["pytest", "-q"]` (סעיף ב-prompt + דוגמה ב-docs).

---

## Phase 5 – שיפורי Tools & Policy

### 5.1 הרחבת `run_cmd`

קובץ: `agentic_runner/tools/exec.py`

1. **Allowlist דינמי:**

   ```python
   import os

   DEFAULT_ALLOWED = {"python", "pytest", "git", "ls", "dir", "cat", "type"}

   def _allowed_cmds() -> set[str]:
       env = os.environ.get("ALLOWED_CMDS")
       if not env:
           return DEFAULT_ALLOWED
       return {item.strip() for item in env.split(",") if item.strip()}
   ```

2. עדכון פונקציית `run_cmd`:

   ```python
   import shlex
   from typing import Union, List

   def run_cmd(workspace: Path, cmd: Union[List[str], str], timeout_s: int = 120) -> Dict[str, Any]:
       if isinstance(cmd, str):
           cmd = shlex.split(cmd)

       if not cmd:
           raise ValueError("Empty cmd")

       allowed = _allowed_cmds()
       if cmd[0] not in allowed:
           raise PermissionError(f"Command not allowlisted: {cmd[0]}")
       ...
   ```

### 5.2 מדיניות חכמה יותר

קובץ: `agentic_runner/policy.py`

- דוגמה לשדרוג – בדיקה לפי path:

  ```python
  def decide(self, tool_name: str, args: Dict[str, Any], tool_risk: str) -> Decision:
      # write_text ל-requirements.txt → תמיד requires_approval
      if tool_name == "write_text":
          path = args.get("path", "")
          if "requirements" in path:
              return Decision(
                  allow=True,
                  requires_approval=True,
                  reason="Editing dependencies always requires approval.",
                  risk="high",
              )
      ...
  ```

---

## Phase 6 – Packaging & Deployment

### 6.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 הרצה מקומית

```bash
# Backend
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
uvicorn services.api.main:app --reload --port 8000

# Frontend (אם React)
cd web
npm install
npm run dev
```

---

## Phase 7 – מיתוג שיווקי

### 7.1 טקסטים בפרונט

- כותרת: **"Safe AI Agent Runner"**
- תת-כותרת:
  **"Plan → Act → Verify, עם אישורים אנושיים ו-full audit trail."**
- Badge קטן:
  **"Built by [שם החברה] – Custom AI Agents for Enterprises"**

### 7.2 Call To Action

- בפוטר / פינה עליונה:
  - כפתור: **"Need this in your org?"**
  - מוביל לטופס / מייל / Calendly.

---

## Checklist (לביצוע בפועל)

- [ ] `OpenAILLM` ממומש ומחובר ל-`_load_llm`.
- [ ] `POST /api/runs` + `GET /api/runs{...}` עובדים.
- [ ] `_demo_workspace` קיים עם קבצים.
- [ ] Specs לדמו קיימים (`spec_doc_summary`, `spec_run_tests`).
- [ ] Frontend:
  - [ ] Dashboard – ריצות אחרונות.
  - [ ] New Run – בחירת spec ו-LLM.
  - [ ] Run Detail – plan, actions, checks, final, artifacts, events.
- [ ] Approvals UI מחובר ל-API המאוחד.
- [ ] Docker image נבנה ורץ.
- [ ] README מעודכן עם:
  - [ ] הרצה מקומית.
  - [ ] הרצה דרך Docker.
  - [ ] שימוש ב-mock / OpenAI.
- [ ] טקסטי מיתוג ברורים + CTA.
