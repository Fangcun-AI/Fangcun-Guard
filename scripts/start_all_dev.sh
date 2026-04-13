#!/bin/bash
# FangcunGuard Development Startup Script
# Starts all model services and backend services for development/testing.
#
# Usage: bash scripts/start_all_dev.sh
#
# Prerequisites:
#   - PostgreSQL running on localhost:5432
#   - Model files downloaded to /opt/models/
#   - Python .venv at backend/.venv
#   - vLLM env at /opt/vllm-env/

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  FangcunGuard Dev Startup"
echo "============================================"

# --- Configuration ---
# Model paths (override with env vars if needed)
QWEN3GUARD_MODEL="${QWEN3GUARD_MODEL:-/opt/models/Qwen3Guard-Gen-8B}"
QWEN3_MODEL="${QWEN3_MODEL:-/opt/models/Qwen3-8B}"
PROMPT_GUARD_MODEL="${PROMPT_GUARD_MODEL:-/opt/models/deberta-v3-prompt-injection-v2}"

# Ports
QWEN3GUARD_PORT=58002
QWEN3_PORT=58008
PROMPT_GUARD_PORT=58006
ADMIN_PORT=5000
DETECTION_PORT=5001
PROXY_PORT=5002

# GPU assignment
QWEN3GUARD_GPU="${QWEN3GUARD_GPU:-0}"
QWEN3_GPU="${QWEN3_GPU:-1}"
PROMPT_GUARD_GPU="${PROMPT_GUARD_GPU:-2}"

# --- Helper functions ---
check_port() {
    ss -tlnp 2>/dev/null | grep -q ":$1 " && return 0 || return 1
}

wait_for_port() {
    local port=$1
    local name=$2
    local timeout=${3:-60}
    local elapsed=0
    while ! check_port "$port"; do
        sleep 2
        elapsed=$((elapsed + 2))
        if [ $elapsed -ge $timeout ]; then
            echo -e "  ${RED}✗ $name (port $port) failed to start after ${timeout}s${NC}"
            return 1
        fi
    done
    echo -e "  ${GREEN}✓ $name (port $port) is ready${NC}"
    return 0
}

kill_port() {
    local port=$1
    local pids
    pids=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K\d+' | sort -u)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
    fi
}

# --- Ensure .env has correct values ---
echo ""
echo "[1/6] Checking backend .env configuration..."
ENV_FILE="$BACKEND_DIR/.env"

# Create .env if it doesn't exist
touch "$ENV_FILE"

ensure_env() {
    local key=$1
    local value=$2
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Update existing
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        # Append
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

ensure_env "GUARDRAILS_MODEL_API_URL" "http://localhost:${QWEN3GUARD_PORT}/v1"
ensure_env "GENERAL_LLM_API_URL" "http://localhost:${QWEN3_PORT}/v1"
ensure_env "PROMPT_GUARD_URL" "http://127.0.0.1:${PROMPT_GUARD_PORT}"
echo -e "  ${GREEN}✓ .env configured${NC}"

# --- 1. Check PostgreSQL ---
echo ""
echo "[2/6] Checking PostgreSQL..."
if check_port 5432; then
    echo -e "  ${GREEN}✓ PostgreSQL (5432) is running${NC}"
else
    echo -e "  ${RED}✗ PostgreSQL (5432) is NOT running. Please start it first.${NC}"
    exit 1
fi

# --- 2. Start model services ---
echo ""
echo "[3/6] Starting model services..."

# Qwen3Guard (vLLM)
if check_port $QWEN3GUARD_PORT; then
    echo -e "  ${YELLOW}● Qwen3Guard ($QWEN3GUARD_PORT) already running, skipping${NC}"
else
    echo "  Starting Qwen3Guard on GPU $QWEN3GUARD_GPU..."
    CUDA_VISIBLE_DEVICES=$QWEN3GUARD_GPU /opt/vllm-env/bin/vllm serve "$QWEN3GUARD_MODEL" \
        --host 0.0.0.0 --port $QWEN3GUARD_PORT \
        --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --max-model-len 8192 \
        --served-model-name Qwen3Guard-Gen-8B \
        > "$LOG_DIR/qwen3guard.log" 2>&1 &
    wait_for_port $QWEN3GUARD_PORT "Qwen3Guard" 120
fi

# Qwen3-8B (vLLM)
if check_port $QWEN3_PORT; then
    echo -e "  ${YELLOW}● Qwen3-8B ($QWEN3_PORT) already running, skipping${NC}"
else
    echo "  Starting Qwen3-8B on GPU $QWEN3_GPU..."
    CUDA_VISIBLE_DEVICES=$QWEN3_GPU /opt/vllm-env/bin/vllm serve "$QWEN3_MODEL" \
        --host 0.0.0.0 --port $QWEN3_PORT \
        --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --max-model-len 8192 \
        --served-model-name Qwen/Qwen3-8B \
        > "$LOG_DIR/qwen3.log" 2>&1 &
    wait_for_port $QWEN3_PORT "Qwen3-8B" 120
fi

# Prompt Guard (ProtectAI DeBERTa)
if check_port $PROMPT_GUARD_PORT; then
    echo -e "  ${YELLOW}● Prompt Guard ($PROMPT_GUARD_PORT) already running, skipping${NC}"
else
    echo "  Starting Prompt Guard on GPU $PROMPT_GUARD_GPU..."
    CUDA_VISIBLE_DEVICES=$PROMPT_GUARD_GPU /opt/vllm-env/bin/python3 \
        "$BACKEND_DIR/prompt_guard_server.py" \
        --model "$PROMPT_GUARD_MODEL" --port $PROMPT_GUARD_PORT \
        > "$LOG_DIR/prompt_guard.log" 2>&1 &
    wait_for_port $PROMPT_GUARD_PORT "Prompt Guard" 30
fi

# --- 3. Start backend services ---
echo ""
echo "[4/6] Starting backend services..."

cd "$BACKEND_DIR"
source .venv/bin/activate 2>/dev/null || true

# Admin service
if check_port $ADMIN_PORT; then
    echo -e "  ${YELLOW}● Admin ($ADMIN_PORT) already running, skipping${NC}"
else
    echo "  Starting Admin service..."
    python start_admin_service.py > "$LOG_DIR/admin.log" 2>&1 &
    wait_for_port $ADMIN_PORT "Admin" 30
fi

# Detection service
if check_port $DETECTION_PORT; then
    echo -e "  ${YELLOW}● Detection ($DETECTION_PORT) already running, skipping${NC}"
else
    echo "  Starting Detection service..."
    python start_detection_service.py > "$LOG_DIR/detection.log" 2>&1 &
    wait_for_port $DETECTION_PORT "Detection" 30
fi

# Proxy service
if check_port $PROXY_PORT; then
    echo -e "  ${YELLOW}● Proxy ($PROXY_PORT) already running, skipping${NC}"
else
    echo "  Starting Proxy service..."
    python start_proxy_service.py > "$LOG_DIR/proxy.log" 2>&1 &
    wait_for_port $PROXY_PORT "Proxy" 30
fi

# --- 4. Health check ---
echo ""
echo "[5/6] Running health checks..."
echo -n "  Qwen3Guard:   "; curl -sf --max-time 3 http://localhost:$QWEN3GUARD_PORT/health > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "  Qwen3-8B:     "; curl -sf --max-time 3 http://localhost:$QWEN3_PORT/health > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "  Prompt Guard: "; curl -sf --max-time 3 http://localhost:$PROMPT_GUARD_PORT/health > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "  Admin:        "; curl -sf --max-time 3 http://localhost:$ADMIN_PORT/health > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "  Detection:    "; curl -sf --max-time 3 http://localhost:$DETECTION_PORT/health > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"
echo -n "  Proxy:        "; curl -sf --max-time 3 http://localhost:$PROXY_PORT/health > /dev/null && echo -e "${GREEN}OK${NC}" || echo -e "${RED}FAIL${NC}"

# --- 5. Summary ---
echo ""
echo "[6/6] Startup complete!"
echo "============================================"
echo "  Model Services:"
echo "    Qwen3Guard:   http://localhost:$QWEN3GUARD_PORT"
echo "    Qwen3-8B:     http://localhost:$QWEN3_PORT"
echo "    Prompt Guard: http://localhost:$PROMPT_GUARD_PORT"
echo "  Backend Services:"
echo "    Admin:        http://localhost:$ADMIN_PORT"
echo "    Detection:    http://localhost:$DETECTION_PORT"
echo "    Proxy:        http://localhost:$PROXY_PORT"
echo "  Logs:           $LOG_DIR/"
echo "============================================"
