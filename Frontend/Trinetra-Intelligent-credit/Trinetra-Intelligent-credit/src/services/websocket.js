import { BASE_URL } from './api';

/**
 * EVENT_TYPES — Maps event_type values from Sankalp's backend
 * to human-readable labels for the agent feed.
 */
export const EVENT_TYPES = {
    compliance_passed: 'Compliance Passed',
    compliance_failed: 'Compliance Failed',
    parsing_completed: 'PDF Parsing Done',
    risk_generated: 'Risk Score Ready',
    cam_generated: 'Final Report Ready',
    stress_completed: 'Stress Test Done',
    bias_checked: 'Bias Check Done',
};

/**
 * WebSocket — Live Agent Feed (Real-Time)
 *
 * Uses NATIVE WebSocket to connect to FastAPI backend.
 * Subscribes to `/ws/{applicationId}`
 *
 * @param {string}   applicationId  The UUID returned from createApplication
 * @param {Function} onMessage      Callback with parsed agentUpdate object
 * @returns {WebSocket}  The active WebSocket instances (call ws.close() on cleanup)
 */
export function subscribeToAgentFeed(applicationId, onMessage) {
    if (!applicationId) return null;

    // Convert http(s):// to ws(s)://
    // e.g., http://localhost:8000 -> ws://localhost:8000/ws/{id}
    const wsBaseUrl = BASE_URL.replace(/^http/, 'ws');
    const wsUrl = `${wsBaseUrl}/ws/${applicationId}`;

    console.log(`[WS] Attempting connection to ${wsUrl}`);
    const ws = new WebSocket(wsUrl);

    // Track deduplication if necessary (though Native WS might not need it as much as STOMP)
    const seen = new Set();

    ws.onopen = () => {
        console.log(`🟢 Connected to Trinetra WebSocket at ${wsUrl}`);
    };

    ws.onmessage = (event) => {
        try {
            const update = JSON.parse(event.data);

            // Dedupe: skip if we already processed this exact message
            const msgKey = `${update.application_id}_${update.agent}_${update.status}_${update.event_type || ''}`;
            if (seen.has(msgKey)) return;
            seen.add(msgKey);

            // Prevent unbounded growth
            if (seen.size > 200) seen.clear();

            console.log(`Agent ${update.agent || 'System'}: ${update.status}`);

            // Pass it up to Context
            onMessage(update);
        } catch (err) {
            console.warn('[WS] Failed to parse message:', event.data, err);
        }
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };

    return ws;
}
