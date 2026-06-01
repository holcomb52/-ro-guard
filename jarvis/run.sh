#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy .env.example and add Supabase credentials (same as RO Guard)."
  exit 1
fi

"$ROOT/jarvis/setup.sh"
exec "$ROOT/jarvis/bin/jarvis-python" -m streamlit run jarvis/app.py \
  --server.port "${JARVIS_PORT:-8765}" \
  --server.address 127.0.0.1 \
  --browser.gatherUsageStats false
