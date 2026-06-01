#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_env.sh"

mkdir -p jarvis/logs

PID_FILE="jarvis/logs/browser.pid"
LOG_FILE="jarvis/logs/browser.log"
PORT="${JARVIS_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"

notify() {
  /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
}

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    open "$URL"
    notify "JARVIS Browser" "Opened in your web browser"
    exit 0
  fi
fi

"$PYTHON" -m pip install -r jarvis/requirements.txt -q 2>/dev/null || true

nohup "$PYTHON" -m streamlit run jarvis/app.py \
  --server.port "$PORT" \
  --server.address 127.0.0.1 \
  --browser.gatherUsageStats false \
  >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

for _ in $(seq 1 30); do
  if curl -sf "$URL/_stcore/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

open "$URL" 2>/dev/null || true
notify "JARVIS Browser" "Running at ${URL}"
exit 0
