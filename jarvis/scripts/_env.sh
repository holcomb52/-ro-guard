#!/usr/bin/env bash
# Shared env for JARVIS launchers — isolated venv, no RO Guard Python path.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

export PYTHONNOUSERSITE=1
unset PYTHONPATH
cd "$PROJECT_ROOT"

VENV_PYTHON="$PROJECT_ROOT/jarvis/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  "$PROJECT_ROOT/jarvis/setup.sh"
fi
PYTHON="$VENV_PYTHON"
