#!/usr/bin/env bash
# JARVIS-only Python environment — separate from RO Guard / Streamlit Cloud.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/jarvis/.venv"
REQ="$ROOT/jarvis/requirements.txt"

run_py() {
  if [[ "$(uname -m)" == "arm64" ]]; then
    arch -arm64 "$@"
  else
    "$@"
  fi
}

SYSTEM_PYTHON="/usr/bin/python3"
if [[ ! -x "$SYSTEM_PYTHON" ]]; then
  SYSTEM_PYTHON="$(command -v python3)"
fi

if [[ -d "$VENV" ]] && [[ "${JARVIS_REBUILD_VENV:-}" != "1" ]]; then
  echo "Installing/updating JARVIS dependencies…"
  run_py "$VENV/bin/python" -m pip install --upgrade pip -q
  run_py "$VENV/bin/python" -m pip install -r "$REQ" -q
  echo ""
  echo "JARVIS environment ready:"
  echo "  $ROOT/jarvis/bin/jarvis-python"
  exit 0
fi

if [[ -d "$VENV" ]]; then
  echo "Recreating JARVIS virtual environment…"
  rm -rf "$VENV"
fi

echo "Creating JARVIS virtual environment…"
run_py "$SYSTEM_PYTHON" -m venv "$VENV"

echo "Installing JARVIS dependencies (isolated from RO Guard)…"
run_py "$VENV/bin/python" -m pip install --upgrade pip -q
run_py "$VENV/bin/python" -m pip install -r "$REQ" -q

echo ""
echo "JARVIS environment ready:"
echo "  $ROOT/jarvis/bin/jarvis-python"
echo ""
echo "Next: ./jarvis/build_apps.sh  (or double-click apps in jarvis/apps/)"
