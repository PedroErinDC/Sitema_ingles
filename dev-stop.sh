#!/usr/bin/env bash

set -euo pipefail

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -t -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "${pids}" ]]; then
    echo "Nada escuchando en ${port}"
    return
  fi
  echo "Deteniendo procesos en puerto ${port}: ${pids}"
  kill ${pids} 2>/dev/null || true
}

stop_port 8000
stop_port 5173

echo "Puertos de desarrollo liberados."
