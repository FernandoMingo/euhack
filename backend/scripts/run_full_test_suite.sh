#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS_DIR="${ROOT_DIR}/.deps"

mkdir -p "${DEPS_DIR}"
python3 -m pip install --target "${DEPS_DIR}" fastapi uvicorn sqlmodel pydantic pytest pytest-cov httpx

export PYTHONPATH="${DEPS_DIR}:${ROOT_DIR}"

echo "==> Running full pytest suite with coverage"
python3 -m pytest "${ROOT_DIR}/tests"

echo "==> Running deterministic demo scenario runner"
python3 "${ROOT_DIR}/scenario_runner.py"

echo "==> Full test suite completed successfully"
