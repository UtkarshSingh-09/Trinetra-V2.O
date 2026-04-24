# Trinetra Canonical Event Contract (Redis)

This file is the source of truth for inter-agent event names and payload shape.

## Standard payload
Every event published to Redis MUST include:

```json
{
  "application_id": "uuid",
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "event": "topic_name",
  "source_agent": "agent-name"
}
```

`agent_status` uses:

```json
{
  "application_id": "uuid",
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "event": "agent_status",
  "agent": "agent-name",
  "status": "PROCESSING|COMPLETED|FAILED",
  "error_code": "Optional"
}
```

## Event map
- `application_created` -> consumed by `compliance-agent`, `pan-verification-agent`, `monitor-agent`
- `compliance_passed` -> consumed by `doc-intelligence-agent`, `monitor-agent`
- `compliance_failed` -> consumed by `monitor-agent`
- `parsing_completed` -> consumed by `gst-reconciliation-agent`, `bank-recon-agent`, `mca-intelligence-agent`, `monitor-agent`
- `gst_completed` -> consumed by `web-intelligence-agent`, `monitor-agent`
- `bank_recon_completed` -> consumed by `web-intelligence-agent`, `monitor-agent`
- `mca_completed` -> consumed by `model-selector-agent`, `monitor-agent`
- `web_intel_completed` -> consumed by `model-selector-agent`, `monitor-agent`
- `model_selected` -> consumed by `risk-agent`, `monitor-agent`
- `risk_generated` -> consumed by `bias-agent`, `stress-agent`, `monitor-agent`
- `bias_completed` -> consumed by `cam-generator-agent`, `monitor-agent`
- `stress_completed` -> consumed by `cam-generator-agent`, `monitor-agent`
- `cam_generated` -> consumed by `monitor-agent`
- `pd_submitted` -> consumed by `pd-transcript-agent`, `monitor-agent`
- `pd_completed` -> consumed by `monitor-agent`
- `agent_status` -> consumed by backend websocket bridge + `monitor-agent`
