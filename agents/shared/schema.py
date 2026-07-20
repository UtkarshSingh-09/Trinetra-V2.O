"""
JSON Schema definitions for the Unified Credit Schema Object (UCSO).
This enforces strict validation before an agent PATCHes its namespace.
"""
from jsonschema import validate, ValidationError
import logging

logger = logging.getLogger("ucso-schema")

UCSO_SCHEMAS = {
    "risk": {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 0, "maximum": 1000},
            "band": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN", "REJECT"]},
            "decision": {"type": "string", "enum": ["APPROVE", "REVIEW", "REJECT", "DATA_INSUFFICIENT"]},
            "cam_generated": {"type": "boolean"},
            "tri_lens_details": {"type": "object"},
            "feature_vector": {"type": "object"},
            "shap_summary": {"type": "array"},
            "model_used": {"type": "string"},
            "model_version": {"type": "string"}
        }
    },
    "doc_analysis": {
        "type": "object",
        "properties": {
            "financial_statements": {"type": "object"},
            "dscr": {"type": "number"},
            "revenue": {"type": "number"}
        }
    },
    "gst_analysis": {
        "type": "object",
        "properties": {
            "discrepancy_amount": {"type": "number"},
            "circular_trading_risk": {"type": "boolean"},
            "tkg_propagated_risk": {"type": "number"}
        }
    },
    "web_analysis": {
        "type": "object",
        "properties": {
            "news_sentiment": {"type": "number"},
            "negative_flags": {"type": "array"}
        }
    }
}

def validate_namespace(namespace: str, data: dict):
    """
    Validates a namespace payload against its JSON Schema.
    Raises ValueError if validation fails.
    """
    schema = UCSO_SCHEMAS.get(namespace)
    if not schema:
        # If no strict schema defined yet, allow by default but warn
        logger.debug(f"No strict schema defined for namespace '{namespace}'. Skipping validation.")
        return

    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        logger.error(f"UCSO Schema Validation Error for namespace '{namespace}': {e.message}")
        raise ValueError(f"Invalid payload for {namespace}: {e.message}") from e
