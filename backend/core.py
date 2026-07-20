import logging
from contextvars import ContextVar
from storage.router import get_storage_client
from redis_broker import AsyncRedisBroker
from websocket_manager import WebSocketManager

logger = logging.getLogger("trinetra-backend.core")

trace_id_var = ContextVar("trace_id", default="")

# Global instances shared across routers
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
