"""
╔══════════════════════════════════════════════════════════════════╗
║  TRINETRA — FastAPI Backend (Central Orchestrator)              ║
║  Python-native backend                                          ║
║  Stack: FastAPI + Postgres/local storage adapter + Redis Pub/Sub ║
╚══════════════════════════════════════════════════════════════════╝
"""
import asyncio
import logging
import os
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import Response

from config import CORS_ORIGINS, HOST, PORT, LOCAL_STORAGE_DIR
from core import storage, redis_broker, ws_manager
from auth import verify_token, init_user_db

# Import routers
from routers.auth import router as auth_router
from routers.applications import router as apps_router
from routers.ml import router as ml_router
from routers.vectorai import router as vectorai_router

from workflow_orchestrator import WorkflowOrchestrator

orchestrator = WorkflowOrchestrator()

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("trinetra-backend")

# ── Background task: Redis → WebSocket bridge ──
async def redis_to_websocket_bridge():
    """
    Listens to Redis channels and broadcasts updates to connected WebSocket clients.
    """
    try:
        await redis_broker.connect()
        await redis_broker.subscribe("agent_status", "websocket_broadcast")
        logger.info("🔗 Redis → WebSocket bridge started (listening on 'agent_status', 'websocket_broadcast')")

        async for msg in redis_broker.listen():
            channel = msg.get("channel")
            data = msg.get("data")
            if not data:
                continue

            if channel == "websocket_broadcast":
                app_id = data.get("application_id")
                payload = data.get("payload")
                if app_id and payload:
                    await ws_manager.broadcast_local(app_id, payload)
            else:
                app_id = data.get("application_id", "")
                if app_id:
                    await ws_manager.broadcast_local(app_id, data)
                    logger.info(
                        f"📡 WS broadcast: {data.get('agent', '?')} → {data.get('status', '?')} "
                        f"(app: {app_id[:8]}..., clients: {ws_manager.connection_count})"
                    )
    except asyncio.CancelledError:
        logger.info("Redis → WebSocket bridge stopped")
    except Exception as e:
        logger.error(f"Redis bridge error: {e}", exc_info=True)

# ── App lifecycle ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, clean up on shutdown."""
    # Seed default users
    try:
        users_path = os.path.join(LOCAL_STORAGE_DIR, "users.json")
        init_user_db(users_path)
        logger.info(f"🔑 User database initialized/loaded from {users_path}")
    except Exception as e:
        logger.error(f"Failed to seed user database: {e}", exc_info=True)

    # Initialize DB (create tables)
    try:
        await storage.initialize_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

    # Start the Redis → WebSocket bridge
    bridge_task = asyncio.create_task(redis_to_websocket_bridge())
    await orchestrator.start()
    logger.info("╔══════════════════════════════════════════════════════╗")
    logger.info("║   TRINETRA FastAPI Backend — ONLINE                 ║")
    logger.info("╚══════════════════════════════════════════════════════╝")
    yield
    # Shutdown
    bridge_task.cancel()
    await orchestrator.stop()
    await redis_broker.close()
    logger.info("Backend shut down.")


# ═══════════════════════════════════════════════════════════
#  FASTAPI APP DEFINITION
# ═══════════════════════════════════════════════════════════
app = FastAPI(
    title="Trinetra OS — Backend API",
    description="Central Orchestrator for Intelli-Credit Agentic AI System. The native Swagger UI can be used to interact with all UCSO namespaces, trigger agents, and authenticate users.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    contact={
        "name": "Trinetra Developer Team",
        "url": "https://github.com/UtkarshSingh-09/Trinetra-V2.O",
    },
    lifespan=lifespan,
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Trace ID Middleware ──
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    import uuid
    from core import trace_id_var
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    token = trace_id_var.set(trace_id)
    try:
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
    finally:
        trace_id_var.reset(token)

# ── Security Headers Middleware ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss: http://localhost:8000 http://localhost:5173 http://localhost:50051; "
        "frame-ancestors 'none';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Register Routers
app.include_router(auth_router)
app.include_router(apps_router)
app.include_router(ml_router)
app.include_router(vectorai_router)

# ── Health Check Endpoint (Redis check) ──
@app.get("/health")
async def health():
    """Health check endpoint. Verifies Redis connectivity."""
    redis_status = "UNAVAILABLE"
    try:
        if not redis_broker.client:
            await redis_broker.connect()
        if redis_broker.client:
            pong = await redis_broker.client.ping()
            if pong:
                redis_status = "CONNECTED"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")

    return {
        "status": "OK" if redis_status == "CONNECTED" else "DEGRADED",
        "service": "Trinetra FastAPI Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "websocket_connections": ws_manager.connection_count,
        "dependencies": {
            "redis": redis_status
        }
    }

# ── WebSocket Endpoint ──
@app.websocket("/ws/{application_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    application_id: str,
    token: str | None = Query(None),
):
    """
    Native WebSocket endpoint for real-time agent status updates.
    """
    if token:
        user_payload = verify_token(token)
        if not user_payload:
            await websocket.close(code=4003)
            return
        is_admin = user_payload.get("role") == "admin"
        is_system = user_payload.get("role") == "system"
        if not is_admin and not is_system:
            app_data = storage.get_application(application_id)
            if not app_data or app_data.get("tenant_id") != user_payload.get("tenant_id"):
                await websocket.close(code=4003)
                return

    await ws_manager.connect(websocket, application_id)
    logger.info(
        f"🔌 WebSocket connected: {application_id[:8]}... "
        f"(total: {ws_manager.connection_count})"
    )

    try:
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, application_id)
        logger.info(f"🔌 WebSocket disconnected: {application_id[:8]}...")


# ── Run Server ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )
