#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p run

stop_pidfile() {
  local pf="$1"
  if [[ -f "$pf" ]]; then
    local pid
    pid="$(cat "$pf" || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[stop] pid=$pid ($pf)"
      kill "$pid" 2>/dev/null || true
      sleep 0.4
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  fi
}

stop_pidfile run/hermes.pid
stop_pidfile run/upstream.pid

# Also clear stray listeners on known ports if still held
for port in 8000 8001; do
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    echo "[stop] freeing port $port: $pids"
    kill $pids 2>/dev/null || true
  fi
done
echo "[ok] stack stopped"
