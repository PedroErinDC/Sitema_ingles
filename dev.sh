#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK_PID=""
FRONT_PID=""

cleanup() {
  if [[ -n "${BACK_PID}" ]] && kill -0 "${BACK_PID}" 2>/dev/null; then
    kill "${BACK_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONT_PID}" ]] && kill -0 "${FRONT_PID}" 2>/dev/null; then
    kill "${FRONT_PID}" 2>/dev/null || true
  fi
}

ensure_port_free() {
  local port="$1"
  if lsof -t -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "El puerto ${port} ya esta en uso. Ejecuta ./dev-stop.sh o libera ese proceso antes de iniciar."
    exit 1
  fi
}

trap cleanup EXIT INT TERM

cd "${ROOT_DIR}"

if [[ ! -x "venv/bin/python" ]]; then
  echo "Falta el entorno virtual en ${ROOT_DIR}/venv"
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  echo "Faltan dependencias del frontend. Ejecuta: cd frontend && npm install"
  exit 1
fi

ensure_port_free 8000
ensure_port_free 5173

echo "Levantando backend con autoreload en http://localhost:8000"
./venv/bin/python -m uvicorn backend.app.main:app --reload &
BACK_PID=$!

echo "Levantando frontend con HMR en http://localhost:5173"
(
  cd frontend
  npm run dev -- --host 0.0.0.0
) &
FRONT_PID=$!

echo
echo "Dev stack activo."
echo "- Backend:  http://localhost:8000"
echo "- Frontend: http://localhost:5173"
echo
echo "Guarda cambios y ambos se actualizaran solos."
echo "Pulsa Ctrl+C para detener los dos procesos."

wait -n "${BACK_PID}" "${FRONT_PID}"
