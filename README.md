# Safe AI Agent Runner (MergePack Demo)

Plan → Act → Verify, עם אישורים אנושיים ו-full audit trail.

> Built as a **marketing-friendly free demo** that proves end-to-end flow and showcases what we can build as a custom enterprise agent platform.

## What you get

- `agentic_runner`: spec-driven agent pipeline (`plan → act → verify`)
- LLM providers:
  - `mock` (offline demo)
  - `openai` (real LLM demo)
- Unified API (`services/api/main.py`) for runs/specs/events/artifacts/approvals
- Web dashboard (`web/index.html`) and approvals UI (`mobile_pwa/index.html`)
- Approval server data model + audit outputs (`run.jsonl`, `final.json`)

---

## Quickstart (local)

```bash
pip install -r requirements.txt
uvicorn services.api.main:app --reload --port 8000
```

Open:
- Dashboard: `web/index.html`
- Approvals UI: `mobile_pwa/index.html`

Set API base to `http://localhost:8000`.

### Run from CLI (direct)

```bash
python -m agentic_runner run --spec examples/spec_pr_fix.json --workspace ./_demo_workspace --out ./_runs --llm mock --auto-approve
```

---

## OpenAI provider

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
python -m agentic_runner run --spec examples/spec_doc_summary.json --workspace ./_demo_workspace --out ./_runs --llm openai --auto-approve
```

If `--llm openai` is used without `OPENAI_API_KEY`, the runner fails fast with a clear error.

---

## API endpoints

- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/artifacts`
- `GET /api/runs/{run_id}/artifacts/{artifact_path}`
- `GET /api/specs`
- `GET /api/specs/{spec_name}`
- `GET /api/approvals`
- `GET /api/approvals/{id}`
- `POST /api/approvals/{id}/decide`

---

## Demo specs

- `examples/spec_doc_summary.json`
- `examples/spec_run_tests.json`
- `examples/spec_pr_fix.json`

Demo workspace files:
- `_demo_workspace/README.md`
- `_demo_workspace/app.py`
- `_demo_workspace/test_app.py`

---

## Docker

```bash
docker build -t mergepack-demo .
docker run --rm -p 8000:8000 -e OPENAI_API_KEY=$OPENAI_API_KEY mergepack-demo
```

---

## Branding / CTA

- Product headline in UI: **Safe AI Agent Runner**
- CTA: **Need this in your org?**

Use this free demo to show capabilities, then offer custom enterprise implementation.
