"""
Trinetra Shared Logger
Standardized JSON logging for all agents.
"""
import logging
import json
import sys
from datetime import datetime, timezone


from contextvars import ContextVar

trace_id_var = ContextVar("trace_id", default="")


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON for easy parsing."""

    def format(self, record):
        trace_id = trace_id_var.get()
        message = record.getMessage()
        if trace_id:
            message = f"[Trace: {trace_id}] - {message}"
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "agent": getattr(record, "agent_name", "unknown"),
            "application_id": getattr(record, "application_id", None),
            "trace_id": trace_id or None,
            "message": message,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_logger(agent_name: str) -> logging.Logger:
    """
    Creates a named logger with JSON output for a specific agent.

    Args:
        agent_name: Name of the agent (e.g., 'doc-agent', 'gst-agent').

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(agent_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
