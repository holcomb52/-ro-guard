#!/usr/bin/env bash
# Shared env for JARVIS launchers — isolated venv, no RO Guard Python path.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

export PYTHONNOUSERSITE=1
unset PYTHONPATH
cd "$PROJECT_ROOT"

JARVIS_PY="$PROJECT_ROOT/jarvis/bin/jarvis-python"
if [[ ! -x "$JARVIS_PY" ]]; then
  "$PROJECT_ROOT/jarvis/setup.sh"
fi
PYTHON="$JARVIS_PY"
