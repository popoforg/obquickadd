#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

APP_NAME="Obsidian QuickAdd"
ICON_PATH="assets/obquickadd.icns"
APP_BUNDLE="dist/${APP_NAME}.app"
PLIST_PATH="${APP_BUNDLE}/Contents/Info.plist"

echo "[1/3] Generating app icon assets..."
python3 scripts/generate_icon.py

echo "[2/3] Building .app with PyInstaller..."
rm -rf build dist "${APP_NAME}.spec"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  quick_add_gui.py

echo "[3/4] Enabling menu-bar-only mode (hide Dock icon)..."
if /usr/libexec/PlistBuddy -c "Print :LSUIElement" "$PLIST_PATH" >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST_PATH"
else
  /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST_PATH"
fi

echo "[4/4] Re-signing app bundle..."
codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null

echo "Build complete"
echo "App path: $ROOT_DIR/$APP_BUNDLE"
