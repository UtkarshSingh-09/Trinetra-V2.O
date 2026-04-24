"""
╔══════════════════════════════════════════════════════════════════╗
║  TRINETRA — FastAPI Backend (Central Orchestrator)              ║
║  Python-native backend                                          ║
╠══════════════════════════════════════════════════════════════════╣
║  Stack: FastAPI + Actian storage adapter + Redis Pub/Sub        ║
║  Designed for local edge + cloud sync workflows                 ║
╚══════════════════════════════════════════════════════════════════╝

Run:  cd backend && python main.py
"""
import asyncio
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from actian_vectorai import Field, FilterBuilder, VectorAIClient as ActianVectorAIClient
from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sentence_transformers import SentenceTransformer

from config import CORS_ORIGINS, HOST, PORT, AGENT_SERVICE_TOKEN, VECTORAI_URL
from models import (
    ApplicationCreate,
    ApplicationResponse,
    NoteRequest,
    StressTriggerRequest,
)
from redis_broker import AsyncRedisBroker
from storage.router import get_storage_client
from websocket_manager import WebSocketManager

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("trinetra-backend")

# ── Global instances ──
storage = get_storage_client()
redis_broker = AsyncRedisBroker()
ws_manager = WebSocketManager()

ALLOWED_NAMESPACES = {
    "applicant",
    "compliance",
    "documents",
    "financials",
    "derived_features",
    "gst_analysis",
    "bank_reconciliation",
    "mca_intelligence",
    "pan_intelligence",
    "web_intel",
    "pd_intelligence",
    "risk",
    "bias_checks",
    "stress_results",
    "ews_monitoring",
    "decision_confidence",
    "cam_output",
    "human_notes",
    "audit_log",
}


# ── Background task: Redis → WebSocket bridge ──
async def redis_to_websocket_bridge():
    """
    Listens to the 'agent_status' Redis channel and broadcasts
    every agent update to connected WebSocket clients.
    This replaces Spring Boot's KafkaConsumerService + STOMP bridge.
    """
    try:
        await redis_broker.connect()
        await redis_broker.subscribe("agent_status")
        logger.info("🔗 Redis → WebSocket bridge started (listening on 'agent_status')")

        async for msg in redis_broker.listen():
            data = msg["data"]
            app_id = data.get("application_id", "")
            if app_id:
                await ws_manager.broadcast(app_id, data)
                logger.info(
                    f"📡 WS broadcast: {data.get('agent', '?')} → {data.get('status', '?')} "
                    f"(app: {app_id[:8]}..., clients: {ws_manager.connection_count})"
                )
    except asyncio.CancelledError:
        logger.info("Redis → WebSocket bridge stopped")
    except Exception as e:
        logger.error(f"Redis bridge error: {e}")


# ── App lifecycle ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, clean up on shutdown."""
    # Start the Redis → WebSocket bridge
    bridge_task = asyncio.create_task(redis_to_websocket_bridge())
    logger.info("╔══════════════════════════════════════════════════════╗")
    logger.info("║   TRINETRA FastAPI Backend — ONLINE                 ║")
    logger.info("╚══════════════════════════════════════════════════════╝")
    yield
    # Shutdown
    bridge_task.cancel()
    await redis_broker.close()
    logger.info("Backend shut down.")


# ═══════════════════════════════════════════════════════════
#  FASTAPI APP
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="Trinetra OS — Backend API",
    description="Central Orchestrator for Intelli-Credit Agentic AI System",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS (for Devraj's React frontend) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════
#  PILLAR 1: Application Initialization
# ═══════════════════════════════════════════════════════════

@app.post("/api/application", response_model=ApplicationResponse)
async def create_application(payload: ApplicationCreate):
    """
    Create a new loan application.
    Initializes the UCSO with 14 empty agent namespaces.
    """
    applicant_data = payload.model_dump()
    result = storage.create_application(applicant_data)

    app_id = result["id"]
    logger.info(f"📋 Application created: {app_id}")

    return ApplicationResponse(
        id=app_id,
        status="CREATED",
        message="Application created. Upload documents to trigger AI pipeline.",
    )


# ═══════════════════════════════════════════════════════════
#  PILLAR 2: Data Fetching (UCSO)
# ═══════════════════════════════════════════════════════════

@app.get("/api/application/{application_id}")
async def get_application(application_id: str):
    """
    Fetch the full UCSO for an application.
    Used by both frontend (UI rendering) and agents (data fetching).
    """
    ucso = storage.get_ucso(application_id)
    if not ucso:
        raise HTTPException(status_code=404, detail="Application not found")
    return ucso


# ═══════════════════════════════════════════════════════════
#  PILLAR 3: File Ingestion
# ═══════════════════════════════════════════════════════════

@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    application_id: str = Form(...),
    type: str = Form("DOCUMENT"),
):
    """
    Upload a file (PDF, DOCX, etc.) to configured storage.
    Appends file metadata to the UCSO's documents.files array.
    After upload, publishes 'application_created' event to trigger AI pipeline.
    """
    file_bytes = await file.read()
    filename = file.filename or "uploaded_file"

    result = storage.upload_file(application_id, file_bytes, filename, type)

    # Fire the Genesis Event — triggers the AI pipeline
    # Do not trigger if the file is a CAM generated by the system itself
    if type != "CAM":
        await redis_broker.publish("application_created", {
            "application_id": application_id,
        })
    
    logger.info(
        f"📤 File uploaded: {filename} ({len(file_bytes)} bytes) → "
        f"Storage: {result['storage_path']} | Event: {'application_created fired' if type != 'CAM' else 'skipped (CAM)'}"
    )

    return {
        "storage_path": result["storage_path"],
        "file_url": result["file_url"],
        "s3_key": result["storage_path"],  # Backward compatibility for agents
        "status": "UPLOADED",
    }


# ═══════════════════════════════════════════════════════════
#  PILLAR 4: Agent Namespace Commits (PATCH)
# ═══════════════════════════════════════════════════════════

@app.patch("/api/application/{application_id}/namespace/{namespace}")
async def patch_namespace(
    application_id: str,
    namespace: str,
    data: dict,
    x_idempotency_key: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None),
):
    """
    Patch a specific namespace within the UCSO.
    Exclusively used by Python AI agents to inject their results.
    """
    if namespace not in ALLOWED_NAMESPACES:
        raise HTTPException(status_code=400, detail=f"Invalid namespace '{namespace}'")
    if AGENT_SERVICE_TOKEN and x_agent_token != AGENT_SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid agent service token")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")
    if len(data.keys()) == 0:
        raise HTTPException(status_code=400, detail="Payload cannot be empty")

    try:
        result = storage.patch_namespace(
            application_id,
            namespace,
            data,
            idempotency_key=x_idempotency_key,
        )
        logger.info(f"✏️ PATCH {namespace} for {application_id[:8]}... ({list(data.keys())})")
        return result.get("ucso_data", result) if isinstance(result, dict) else result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ═══════════════════════════════════════════════════════════
#  PILLAR 5: File Retrieval (Download)
# ═══════════════════════════════════════════════════════════

@app.get("/api/files/{application_id}")
async def get_file(
    application_id: str,
    filename: str = Query(None, description="Specific filename to download (e.g. CAM.docx)"),
):
    """
    Download a file for an application.
    Default: prioritizes .pdf files (backward compat for agents).
    With ?filename=CAM.docx: downloads specific file.
    """
    result = storage.get_file(application_id, filename)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")

    file_bytes, actual_filename = result

    # Determine content type
    content_type = "application/octet-stream"
    if actual_filename.lower().endswith(".pdf"):
        content_type = "application/pdf"
    elif actual_filename.lower().endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={actual_filename}"},
    )


@app.get("/api/files/download")
async def get_file_by_key(
    s3_key: str = Query(..., description="Storage path key, e.g. app_id/TYPE/file.pdf"),
):
    """Download a file by storage path key. Added for PD/audio compatibility."""
    result = storage.get_file_by_key(s3_key)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")

    file_bytes, actual_filename = result
    content_type = "application/octet-stream"
    if actual_filename.lower().endswith(".pdf"):
        content_type = "application/pdf"
    elif actual_filename.lower().endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif actual_filename.lower().endswith(".mp3"):
        content_type = "audio/mpeg"

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={actual_filename}"},
    )


# ═══════════════════════════════════════════════════════════
#  PILLAR 6: Interactive Triggers
# ═══════════════════════════════════════════════════════════

@app.post("/api/application/{application_id}/notes")
async def add_notes(application_id: str, payload: NoteRequest):
    """Add a human note from the credit officer."""
    try:
        ucso = storage.add_note(application_id, payload.note, payload.author)
        logger.info(f"📝 Note added for {application_id[:8]}... by {payload.author}")
        return {"status": "OK", "note_count": len(ucso.get("human_notes", {}).get("notes", []))}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/application/{application_id}/stress")
async def trigger_stress_test(application_id: str, payload: StressTriggerRequest):
    """Re-trigger the Stress Agent with custom parameters."""
    interest_rate_hike = payload.interest_rate_hike
    if payload.interest_rate_hike_bps is not None:
        interest_rate_hike = payload.interest_rate_hike_bps / 100.0

    revenue_drop_pct = payload.revenue_drop_pct
    if payload.revenue_shock_pct is not None:
        # Frontend can send negative shock for drop, e.g. -20
        revenue_drop_pct = abs(payload.revenue_shock_pct)

    # Publish event to Redis → Stress Agent picks it up
    await redis_broker.publish("stress_retrigger", {
        "application_id": application_id,
        "interest_rate_hike": interest_rate_hike,
        "revenue_drop_pct": revenue_drop_pct,
    })
    logger.info(
        f"🔄 Stress re-trigger for {application_id[:8]}... "
        f"(rate+{interest_rate_hike}%, rev-{revenue_drop_pct}%)"
    )
    return {"status": "TRIGGERED", "message": "Stress agent will re-process with new parameters"}


@app.post("/api/application/{application_id}/pd")
async def trigger_pd(application_id: str):
    """Re-trigger the PD Transcript Agent."""
    await redis_broker.publish("pd_submitted", {
        "application_id": application_id,
    })
    return {"status": "TRIGGERED", "message": "PD agent will re-process"}


# ═══════════════════════════════════════════════════════════
#  WEBSOCKET — Real-Time Agent Updates
# ═══════════════════════════════════════════════════════════

@app.websocket("/ws/{application_id}")
async def websocket_endpoint(websocket: WebSocket, application_id: str):
    """
    Native WebSocket endpoint for real-time agent status updates.
    Replaces STOMP/SockJS. Frontend connects to ws://host:8000/ws/{id}
    """
    await ws_manager.connect(websocket, application_id)
    logger.info(
        f"🔌 WebSocket connected: {application_id[:8]}... "
        f"(total: {ws_manager.connection_count})"
    )

    try:
        # Keep connection alive — listen for client messages (ping/pong)
        while True:
            data = await websocket.receive_text()
            # Client can send a ping, we respond with pong
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, application_id)
        logger.info(f"🔌 WebSocket disconnected: {application_id[:8]}...")


# ═══════════════════════════════════════════════════════════
#  UTILITY ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "OK",
        "service": "Trinetra FastAPI Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "websocket_connections": ws_manager.connection_count,
    }


@app.get("/api/applications")
async def list_applications():
    """List all applications (for dashboard)."""
    try:
        if hasattr(storage, "client") and hasattr(storage.client, "table"):
            result = storage.client.table("applications").select(
                "id, company_name, pan, status, created_at"
            ).order("created_at", desc=True).limit(50).execute()
            return result.data or []
        if hasattr(storage, "app_dir"):
            import json
            import os

            records = []
            for name in os.listdir(storage.app_dir):
                if not name.endswith(".json"):
                    continue
                full_path = os.path.join(storage.app_dir, name)
                with open(full_path, "r", encoding="utf-8") as fh:
                    row = json.load(fh)
                records.append({
                    "id": row.get("id"),
                    "company_name": row.get("company_name", ""),
                    "pan": row.get("pan", ""),
                    "status": row.get("status", "CREATED"),
                    "created_at": row.get("created_at"),
                    "ucsoData": row.get("ucso_data", {}),
                })
            records.sort(key=lambda item: item.get("created_at") or "", reverse=True)
            return records[:50]
        return []
    except Exception as e:
        logger.error(f"Failed to list applications: {e}")
        return []


# ═══════════════════════════════════════════════════════════
#  ACTIAN VECTORAI EXPLORER ENDPOINTS (Demo / Hackathon)
# ═══════════════════════════════════════════════════════════

# Lazy-load official SDK client + embedding model for explorer endpoints
_vectorai_client = None
_vectorai_model = None


def _get_vectorai_client():
    global _vectorai_client
    if _vectorai_client is None:
        _vectorai_client = ActianVectorAIClient(VECTORAI_URL)
        _vectorai_client.connect()
    return _vectorai_client


def _get_vectorai_model():
    global _vectorai_model
    if _vectorai_model is None:
        _vectorai_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _vectorai_model


def _embed_query(text: str) -> list[float]:
    return _get_vectorai_model().encode(text).tolist()


def _build_vectorai_filter(filters: dict | None):
    if not filters:
        return None

    builder = FilterBuilder()
    for key, value in filters.items():
        if value is None or value == "":
            continue
        field = Field(key)

        if isinstance(value, (list, tuple, set)):
            builder.must(field.any_of(list(value)))
            continue

        if isinstance(value, dict):
            if "between" in value and isinstance(value["between"], (list, tuple)):
                low, high = value["between"][:2]
                builder.must(field.between(low, high))
                continue
            if any(k in value for k in ("gte", "gt", "lte", "lt")):
                builder.must(
                    field.range(
                        gte=value.get("gte"),
                        gt=value.get("gt"),
                        lte=value.get("lte"),
                        lt=value.get("lt"),
                    )
                )
                continue

        builder.must(field.eq(value))

    return builder.build()


def _normalize_search_result(result) -> dict:
    payload = getattr(result, "payload", None)
    if payload is None:
        payload = getattr(result, "metadata", None)
    if payload is None and isinstance(result, dict):
        payload = result.get("payload") or result.get("metadata") or {}

    return {
        "id": getattr(result, "id", None) if not isinstance(result, dict) else result.get("id"),
        "score": getattr(result, "score", None) if not isinstance(result, dict) else result.get("score"),
        "metadata": payload or {},
    }

VECTORAI_COLLECTIONS = [
    {"name": "document_chunks", "icon": "📄", "label": "Document Chunks", "owner": "doc-agent"},
    {"name": "financial_profiles", "icon": "💰", "label": "Financial Profiles", "owner": "doc-agent"},
    {"name": "gst_patterns", "icon": "📊", "label": "GST Patterns", "owner": "gst-agent"},
    {"name": "bank_recon_profiles", "icon": "🏦", "label": "Bank Reconciliation", "owner": "bank-recon-agent"},
    {"name": "news_articles", "icon": "📰", "label": "News Articles", "owner": "web-agent"},
    {"name": "litigation_records", "icon": "⚖️", "label": "Litigation Records", "owner": "web-agent"},
    {"name": "rbi_circulars", "icon": "🏛️", "label": "RBI Circulars", "owner": "web-agent"},
    {"name": "mca_filings", "icon": "🏢", "label": "MCA Filings", "owner": "mca-agent"},
    {"name": "pan_profiles", "icon": "🆔", "label": "PAN Profiles", "owner": "pan-agent"},
    {"name": "risk_decisions", "icon": "⚠️", "label": "Risk Decisions", "owner": "risk-agent"},
    {"name": "pd_transcripts", "icon": "🎤", "label": "PD Transcripts", "owner": "pd-agent"},
    {"name": "stress_scenarios", "icon": "📈", "label": "Stress Scenarios", "owner": "stress-agent"},
    {"name": "audit_events", "icon": "🔍", "label": "Audit Events", "owner": "monitor-agent"},
    {"name": "application_summaries", "icon": "📋", "label": "Application Summaries", "owner": "all-agents"},
]


@app.get("/api/vectorai/collections")
async def vectorai_collections():
    """Return metadata for all 14 Actian VectorAI collections."""
    return {"collections": VECTORAI_COLLECTIONS, "count": len(VECTORAI_COLLECTIONS)}


@app.get("/api/vectorai/search")
async def vectorai_search(
    q: str = Query(..., description="Semantic query text"),
    collection: str = Query("news_articles", description="Collection to search"),
    top_k: int = Query(5, ge=1, le=20),
):
    """Semantic search across any Actian VectorAI collection."""
    try:
        client = _get_vectorai_client()
        query_vector = _embed_query(q)
        raw_results = client.points.search(
            collection,
            vector=query_vector,
            limit=top_k,
            score_threshold=0.0,
        )
        results = [_normalize_search_result(r) for r in raw_results]
        return {"query": q, "collection": collection, "top_k": top_k, "results": results}
    except Exception as e:
        logger.error(f"VectorAI search failed: {e}")
        raise HTTPException(status_code=500, detail=f"VectorAI search failed: {str(e)}")


@app.post("/api/vectorai/hybrid-search")
async def vectorai_hybrid_search(body: dict):
    """Hybrid search: vector similarity + metadata SQL filters."""
    try:
        client = _get_vectorai_client()
        query_text = body.get("query", "")
        collection = body.get("collection", "news_articles")
        top_k = body.get("top_k", 5)
        filter_obj = _build_vectorai_filter(body.get("filters", {}))

        raw_results = client.points.search(
            collection,
            vector=_embed_query(query_text),
            limit=top_k,
            score_threshold=0.0,
            filter=filter_obj,
        )
        results = [_normalize_search_result(r) for r in raw_results]
        return {"results": results, "filters": body.get("filters", {})}
    except Exception as e:
        logger.error(f"VectorAI hybrid search failed: {e}")
        raise HTTPException(status_code=500, detail=f"VectorAI hybrid search failed: {str(e)}")


# ═══════════════════════════════════════════════════════════
#  RUN SERVER
# ═══════════════════════════════════════════════════════════


if __name__ == "__main__":
    import uvicorn

    print("╔══════════════════════════════════════════════════════════╗")
    print("║   TRINETRA — FastAPI Backend Server                     ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  URL:    http://{HOST}:{PORT}                           ║")
    print(f"║  Docs:   http://{HOST}:{PORT}/docs                     ║")
    print(f"║  CORS:   {CORS_ORIGINS}                                 ║")
    print("║  Storage Provider: actian                         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
