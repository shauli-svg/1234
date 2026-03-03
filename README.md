# MergePack — Agentic Runner (E2E MVP)

A minimal, safe-by-default agentic runner that turns a task spec into:
- a deterministic pipeline (`plan → act → verify`)
- an auditable proof pack (logs + artifacts + policy decisions)
- optional human approval gates for high-impact actions

It ships with a deterministic **mock LLM**, so it runs out of the box. Replace it later in `agentic_runner/llm/provider.py`.

## Quickstart

```bash
python -m agentic_runner run --spec examples/spec_pr_fix.json --workspace ./_work --out ./_runs
```

Outputs are written under `_runs/<run_id>/`:
- `run.jsonl` — event log
- `final.json` — final structured output
- `artifacts/` — generated files

## Mobile/PWA approvals (MVP)

Run approval server:

```bash
pip install -r requirements.txt
uvicorn services.approval_server.app:app --reload --port 8008
```

Open `mobile_pwa/index.html` in a browser and set base URL to `http://localhost:8008`.

Run the agent with remote approvals:

```bash
export APPROVAL_SERVER=http://localhost:8008
python -m agentic_runner run --spec examples/spec_pr_fix.json
```

## Notes

- `ToolProxy` enforces allowlisted tools and policy decisions.
- `PolicyEngine` requires approvals for high-impact actions by default.
- Verification in this MVP is deterministic and intentionally simple.
