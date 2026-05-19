#!/usr/bin/env bash
set -euo pipefail
# Run backend with correct PYTHONPATH. Usage: ./run_dev.sh [--reload] [port]
cd "$(dirname "$0")"
export PYTHONPATH="$PWD"
PORT=${2:-${1:-8000}}
if [[ "$1" == "--reload" ]]; then
  python3 -m uvicorn app.api.main:create_app --factory --reload --port "$PORT"
else
  python3 -m uvicorn app.api.main:create_app --factory --port "$PORT"
fi
