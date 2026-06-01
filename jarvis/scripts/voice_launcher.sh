#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_env.sh"

mkdir -p jarvis/logs

PID_FILE="jarvis/logs/listen.pid"
LOG_FILE="jarvis/logs/listen.log"

notify() {
  /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
}

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    notify "JARVIS Voice" "Already listening for Hey Jarvis"
    exit 0
  fi
fi

"$PYTHON" -m pip install -r jarvis/requirements.txt -q 2>/dev/null || true

nohup "$PYTHON" -m jarvis.listen >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

notify "JARVIS Voice" "Listening for Hey Jarvis — no Terminal needed"
exit 0
