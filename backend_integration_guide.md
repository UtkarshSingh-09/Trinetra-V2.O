# Trinetra Backend Integration Guide (FastAPI + Redis + Actian Storage)

This is the canonical backend contract for all agents and frontend integrations.

## Runtime stack
- API: FastAPI (`backend/main.py`)
- Event bus: Redis Pub/Sub
- Storage: Actian adapter (local edge mode + optional cloud sync)
- Realtime updates: WebSocket (`/ws/{application_id}`)

## API contracts

### Create application
- `POST /api/application`
- Returns: `{ id, status, message }`

### Get UCSO
- `GET /api/application/{application_id}`
- Returns raw UCSO JSON object (no `ucsoData` wrapper)

### Patch namespace (agent write path)
- `PATCH /api/application/{application_id}/namespace/{namespace}`
- Header (optional): `X-Idempotency-Key`
- Body: flat JSON object
- Validation:
  - namespace must be one of allowed UCSO namespaces
  - body must be non-empty JSON object

### File upload
- `POST /api/files/upload`
- Multipart fields: `file`, `application_id`, `type`

### File download by app
- `GET /api/files/{application_id}?filename=CAM.docx`

### File download by key (PD/audio compatibility)
- `GET /api/files/download?s3_key=<storage_path>`

### Health
- `GET /health`

## Event contract (Redis)
Every event payload must include:
- `application_id`
- `event_id`
- `timestamp` (ISO8601)
- `event`
- `source_agent` (or `agent` for `agent_status`)

Reference map: `agents/shared/event_contract.md`

## Startup sequence
1. Start Redis
2. Start backend (`python backend/main.py`)
3. Start agents (`agents/start_all_agents.sh`)
4. Frontend connects over REST + native WebSocket

## Storage behavior
`backend/storage/router.py` always returns the Actian adapter.
Configuration is controlled with:
- `ACTIAN_MODE=edge|cloud`
- `ACTIAN_LOCAL_DIR`
- `ACTIAN_CLOUD_API_URL`
- `ACTIAN_API_KEY`

## Security baseline
- Never commit `.env` with real keys
- Keep only `.env.example` templates in git
- Rotate compromised keys immediately
