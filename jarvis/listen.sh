#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy .env.example and add Supabase credentials (same as RO Guard)."
  exit 1
fi

"$ROOT/jarvis/setup.sh"
export PYTHONNOUSERSITE=1
unset PYTHONPATH
PYTHON="$ROOT/jarvis/.venv/bin/python"

echo ""
echo "Starting hands-free JARVIS (say: Hey Jarvis)…"
echo "Tip: omit --device to auto-use MacBook mic"
echo "Mic problems? Run: $PYTHON -m jarvis.scan_mics"
echo ""
"$PYTHON" -m jarvis.listen "$@"
