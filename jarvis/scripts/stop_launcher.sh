#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/_env.sh"

notify() {
  /usr/bin/osascript -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
}

stop_pid_file() {
  local label="$1"
  local pid_file="$2"
  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  rm -f "$pid_file"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.5
    kill -9 "$pid" 2>/dev/null || true
    echo "Stopped $label (pid $pid)"
    return 0
  fi
  return 1
}

stopped=0
stop_pid_file "JARVIS Voice" "jarvis/logs/listen.pid" && stopped=1
stop_pid_file "JARVIS Browser" "jarvis/logs/browser.pid" && stopped=1

if [[ "$stopped" -eq 1 ]]; then
  notify "JARVIS" "Voice and browser stopped"
else
  notify "JARVIS" "Nothing was running"
fi
exit 0
