#!/usr/bin/env bash
# JARVIS-only Python environment — separate from RO Guard / Streamlit Cloud.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/jarvis/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating JARVIS virtual environment…"
  python3 -m venv "$VENV"
fi

echo "Installing JARVIS dependencies (isolated from RO Guard)…"
"$VENV/bin/python" -m pip install --upgrade pip -q
"$VENV/bin/python" -m pip install -r "$ROOT/jarvis/requirements.txt" -q

echo ""
echo "JARVIS environment ready:"
echo "  $VENV/bin/python"
echo ""
echo "Next: ./jarvis/build_apps.sh  (or double-click apps in jarvis/apps/)"
