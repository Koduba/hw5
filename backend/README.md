# Campus Customs backend

The FastAPI app and the agent team. All shop data goes through the `campus-customs` MCP server.

## Run

From `backend/`:

```bash
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

The API is at http://localhost:8000, with docs at http://localhost:8000/docs. Press Ctrl-C to stop both the reloader and the server.

From the repo root, `.venv/bin/python -m backend.main` also works, without the reloader.

## Routes

| Route | Purpose |
|---|---|
| `GET /api/tickets` | All tickets, `open` or `resolved` |
| `POST /api/tickets/{id}/run` | Run the agent team on a ticket. Returns a `run_id` at once; poll `GET /api/runs/{run_id}` |
| `GET /api/events?since=N` | Recent agent steps (who said what, which tool) from `output/audit_trail.json` |
| `POST /api/approvals/{id}/approve` `{"approver": "Name"}` | Human approval. **The only route that moves cash** |
| `POST /api/approvals/{id}/reject` | Human rejection |
| `GET /api/cash` | Checking balance from `cash_accounts` |
| `POST /api/reset` | Restore the working DB from the original |
| `GET /api/approvals`, `/api/board`, `/api/payments`, `/api/runs`, `/api/health` | Supporting reads for the dashboard |

## CLI (same MCP server)

```bash
.venv/bin/python -m backend.chat boss "your words" --trace
```

Other commands:
- `--ticket N`: run one ticket through the boss
- `--approvals`: list what's waiting on a person
- `--approve ID --by "Name"` / `--reject ID --by "Name"`
- `--reset`: restore the working DB from the original

## Settings

See `../.env.example`:
- `PORTKEY_API_KEY`
- `OPENAI_MODEL` (only `gpt-6-luna` is allowed)
- loop and token limits
- `DASHBOARD_ORIGINS` for CORS
