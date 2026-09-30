#!/usr/bin/env bash
# Starts the Catalog Server and Intern in the background, runs the Salesperson, and shuts everything down on exit.
# Usage: ./run_demo.sh "find me electronics under 20 euros"
set -uo pipefail

QUERY="${1:-find me electronics under 20 euros}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -- Prerequisites -------------------------------------------------------------

# Load .env if it exists (does not override variables already exported in the shell)
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

if [[ -z "${GROQ_API_KEY:-}" ]]; then
    echo "Error: GROQ_API_KEY is not set."
    echo "       Create a .env file with: GROQ_API_KEY=gsk_..."
    echo "       (free key at console.groq.com)"
    exit 1
fi

source "$SCRIPT_DIR/venv/bin/activate"

# -- Cleanup on exit (Ctrl+C or normal exit) -----------------------------------

CATALOG_PID=""
INTERN_PID=""
TAIL_PID=""
QUIET="${QUIET:-0}"

log() { [[ "$QUIET" != "1" ]] && echo "$@" || true; }

cleanup() {
    echo ""
    echo "[demo] Shutting down servers..."
    [[ -n "$TAIL_PID" ]]    && kill "$TAIL_PID"    2>/dev/null || true
    [[ -n "$INTERN_PID" ]]  && kill "$INTERN_PID"  2>/dev/null || true
    [[ -n "$CATALOG_PID" ]] && kill "$CATALOG_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# -- Helpers -------------------------------------------------------------------

check_port() {
    python -c "
import socket, sys
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(('127.0.0.1', $1))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

wait_for_port() {
    local port=$1 name=$2
    for i in $(seq 1 30); do
        check_port "$port" && { echo "[demo] $name ready (port $port)"; return 0; }
        sleep 0.5
    done
    echo "[demo] Timeout: $name did not respond on port $port." >&2
    exit 1
}

# -- Check ports are free ------------------------------------------------------

if check_port 8100; then
    echo "[demo] Error: port 8100 is already in use. Stop the process and try again." >&2
    exit 1
fi
if check_port 9000; then
    echo "[demo] Error: port 9000 is already in use. Stop the process and try again." >&2
    exit 1
fi

# -- Logs directory ------------------------------------------------------------

mkdir -p "$SCRIPT_DIR/logs"

# -- Database ------------------------------------------------------------------

if [[ ! -f "$SCRIPT_DIR/catalog_server/catalog.db" ]]; then
    echo "[demo] Creating catalog.db..."
    (cd "$SCRIPT_DIR/catalog_server" && python seed_db.py)
fi

# -- Catalog Server ------------------------------------------------------------

log "[demo] Starting Catalog Server (port 8100)..."
(cd "$SCRIPT_DIR/catalog_server" && python server.py) > $SCRIPT_DIR/logs/catalog.log 2>&1 &
CATALOG_PID=$!
wait_for_port 8100 "Catalog Server"

# -- Intern -------------------------------------------------------------------

log "[demo] Starting Intern (port 9000)..."
(cd "$SCRIPT_DIR/intern" && LOG_REASONING=${LOG_REASONING:-1} python -u server.py) > $SCRIPT_DIR/logs/intern.log 2>&1 &
INTERN_PID=$!
wait_for_port 9000 "Intern"

# Stream [Intern] reasoning lines to terminal (skipped in QUIET mode)
if [[ "$QUIET" != "1" ]]; then
    tail -f $SCRIPT_DIR/logs/intern.log | grep --line-buffered "^\[Intern\]" &
    TAIL_PID=$!
fi

# -- Salesperson ---------------------------------------------------------------

[[ "$QUIET" != "1" ]] && echo "" && echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
(cd "$SCRIPT_DIR/salesperson" && python client.py "$QUERY")
[[ "$QUIET" != "1" ]] && echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log ""
log "[demo] Full logs at: $SCRIPT_DIR/logs/catalog.log  $SCRIPT_DIR/logs/intern.log"
