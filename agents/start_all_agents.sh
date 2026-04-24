#!/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║  TRINETRA — Start All 13 Agents                         ║
# ║  Each agent runs as a separate background process        ║
# ╚══════════════════════════════════════════════════════════╝

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Prefer project virtualenv if present so all agent deps resolve consistently.
if [ -x "$SCRIPT_DIR/../.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/../.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

# Load .env values
if [ -f .env ]; then
    export BACKEND_URL=$(grep "^BACKEND_URL=" .env | cut -d= -f2-)
    export REDIS_URL=$(grep "^REDIS_URL=" .env | cut -d= -f2-)
fi
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   TRINETRA — Starting All 13 Agents                     ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Backend:  ${BACKEND_URL}                                ║"
echo "║  Redis:    ${REDIS_URL}                                  ║"
echo "╚══════════════════════════════════════════════════════════╝"

# ── Pre-flight checks ──
echo ""
echo "🔍 Running pre-flight checks..."

# Check backend
if curl -s --connect-timeout 3 "${BACKEND_URL}/health" > /dev/null 2>&1; then
    echo "  ✅ Backend is reachable at ${BACKEND_URL}"
else
    echo "  ❌ Backend is NOT reachable at ${BACKEND_URL}"
    echo "     Make sure FastAPI backend is running!"
    exit 1
fi

# Check Redis
REDIS_HOST=$(echo ${REDIS_URL#redis://} | cut -d: -f1)
REDIS_PORT=$(echo ${REDIS_URL#redis://} | cut -d: -f2)
if nc -z -w3 "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
    echo "  ✅ Redis is reachable at ${REDIS_URL}"
else
    echo "  ❌ Redis is NOT reachable at ${REDIS_URL}"
    echo "     Make sure Redis is running!"
    exit 1
fi

echo ""
echo "🚀 Starting agents..."

# Create logs directory
mkdir -p logs

# ── Start each agent as a background process ──
AGENTS=(
    "compliance-agent"
    "doc-agent"
    "pd-agent"
    "gst-agent"
    "bank-recon-agent"
    "mca-agent"
    "web-agent"
    "model-selector-agent"
    "risk-agent"
    "bias-agent"
    "stress-agent"
    "cam-agent"
    "monitor-agent"
)

PIDS=()
for agent in "${AGENTS[@]}"; do
    if [ -f "$agent/main.py" ]; then
        "$PYTHON_BIN" "$agent/main.py" > "logs/${agent}.log" 2>&1 &
        PID=$!
        PIDS+=($PID)
        echo "  ✅ Started ${agent} (PID: $PID)"
    else
        echo "  ❌ ${agent}/main.py not found!"
    fi
done

echo ""
echo "════════════════════════════════════════════════════════"
echo "  🎉 All ${#PIDS[@]} agents started!"
echo "  📋 Logs: agents/logs/<agent-name>.log"
echo ""
echo "  To view live logs:"
echo "    tail -f agents/logs/compliance-agent.log"
echo ""
echo "  To stop all agents:"
echo "    pkill -f 'python.*agent.*main.py'"
echo "════════════════════════════════════════════════════════"

# Save PIDs for cleanup
echo "${PIDS[@]}" > logs/agent_pids.txt

# Wait for all — press Ctrl+C to stop
echo ""
echo "  Press Ctrl+C to stop all agents..."
cleanup() {
    echo ""
    echo "Stopping all agents..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    echo "Done."
    exit 0
}
trap cleanup INT TERM
wait
