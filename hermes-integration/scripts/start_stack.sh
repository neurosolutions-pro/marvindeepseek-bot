#!/usr/bin/env bash
# Start local upstream + Hermes OpenAI gateway (integration mode).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
set -a
# shellcheck disable=SC1091
source .env
set +a

mkdir -p logs run
python scripts/apply_config.py

stop_pidfile() {
  local pf="$1"
  if [[ -f "$pf" ]]; then
    local pid
    pid="$(cat "$pf" || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 0.5
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  fi
}

stop_pidfile run/upstream.pid
stop_pidfile run/hermes.pid

echo "[start] local upstream on ${UPSTREAM_HOST:-127.0.0.1}:${UPSTREAM_PORT:-8001}"
nohup python local_upstream.py \
  --host "${UPSTREAM_HOST:-127.0.0.1}" \
  --port "${UPSTREAM_PORT:-8001}" \
  --log-level "${HERMES_LOG_LEVEL:-info}" \
  > logs/upstream.stdout.log 2>&1 &
echo $! > run/upstream.pid

echo "[start] hermes gateway on ${HERMES_HOST:-0.0.0.0}:${HERMES_PORT:-8000}"
nohup python hermes_server.py \
  > logs/hermes.stdout.log 2>&1 &
echo $! > run/hermes.pid

# Wait for health
for i in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${HERMES_PORT:-8000}/health" >/dev/null; then
    echo "[ok] Hermes health endpoint ready"
    curl -s "http://127.0.0.1:${HERMES_PORT:-8000}/health" || true
    echo
    exit 0
  fi
  sleep 0.25
done

echo "[error] Hermes did not become healthy; see logs/"
tail -n 50 logs/hermes.stdout.log logs/upstream.stdout.log || true
exit 1
