#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JARVIS="$ROOT/jarvis"
APPS="$JARVIS/apps"

mkdir -p "$APPS" "$JARVIS/logs"

echo "Setting up isolated JARVIS Python environment…"
"$JARVIS/setup.sh"

PYTHON="$JARVIS/.venv/bin/python"

cat >"$JARVIS/scripts/config.env" <<EOF
PROJECT_ROOT=$ROOT
PYTHON=$PYTHON
JARVIS_PORT=8765
EOF

chmod +x "$JARVIS/scripts/"*.sh

build_app() {
  local name="$1"
  local launcher="$2"
  local bundle_id="$3"
  local app_dir="$APPS/${name}.app"

  rm -rf "$app_dir"
  mkdir -p "$app_dir/Contents/MacOS" "$app_dir/Contents/Resources"

  cp "$JARVIS/scripts/config.env" "$app_dir/Contents/Resources/config.env"

  cat >"$app_dir/Contents/MacOS/launcher" <<LAUNCHER
#!/usr/bin/env bash
set -euo pipefail
RESOURCES="\$(cd "\$(dirname "\$0")/../Resources" && pwd)"
# shellcheck source=/dev/null
source "\$RESOURCES/config.env"
exec "$JARVIS/scripts/${launcher}"
LAUNCHER
  chmod +x "$app_dir/Contents/MacOS/launcher"

  cat >"$app_dir/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>${bundle_id}</string>
  <key>CFBundleName</key>
  <string>${name}</string>
  <key>CFBundleDisplayName</key>
  <string>${name}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>LSUIElement</key>
  <true/>
</dict>
</plist>
PLIST

  echo "Built $app_dir"
}

build_app "JARVIS Voice" "voice_launcher.sh" "com.roguard.jarvis.voice"
build_app "JARVIS Browser" "browser_launcher.sh" "com.roguard.jarvis.browser"
build_app "Stop JARVIS" "stop_launcher.sh" "com.roguard.jarvis.stop"

echo ""
echo "Done. Double-click apps in:"
echo "  $APPS"
echo ""
echo "First time: macOS will ask for Microphone access for JARVIS Voice — click Allow."
echo "Optional: drag JARVIS Voice.app to Login Items to start at sign-in."
