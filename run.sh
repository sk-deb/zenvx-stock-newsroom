#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

VENV_DIR="$(pwd)/.venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ZenvX Stock] python3 not found. Install Python 3.10+ first."
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "[ZenvX Stock] Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

echo "[ZenvX Stock] Installing / updating dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r backend/requirements.txt

echo ""
echo "[ZenvX Stock] Starting on http://127.0.0.1:8421"
echo "[ZenvX Stock] Press Ctrl+C to stop."
echo ""
exec "$VENV_DIR/bin/python" -m uvicorn backend.main:app --host 0.0.0.0 --port 8421
