#!/usr/bin/env bash
#
# Builds "QDVC Articulate.app" (Apple Silicon) with the App Sandbox enabled and no network entitlements.
#
# Usage:
#   scripts/build-app.sh                       # release build, ad-hoc signed
#   CONFIG=debug scripts/build-app.sh          # debug build
#   SIGN_IDENTITY="Apple Development: Jane Doe (TEAMID)" scripts/build-app.sh
#
# Requirements: Xcode 16 or later (or its command-line tools) on macOS 14+.
# Nothing is downloaded by this script.
#
set -euo pipefail

CONFIG="${CONFIG:-release}"
SIGN_IDENTITY="${SIGN_IDENTITY:--}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="QDVC Articulate"
PRODUCT="QDVCArticulate"
OUT_DIR="$ROOT/build"
APP="$OUT_DIR/$APP_NAME.app"
ENTITLEMENTS="$ROOT/Resources/QDVCArticulate.entitlements"

cd "$ROOT"

if [[ -d "Vendor/llama.xcframework" ]]; then
    echo "▸ llama.xcframework found: building with the AI engine."
else
    echo "▸ Vendor/llama.xcframework not found: building WITHOUT the AI engine (rules + macOS spelling only)."
fi

# Refuse to build if anyone ever adds a network entitlement.
"$ROOT/scripts/verify-isolation.sh" --entitlements-only

echo "▸ Compiling ($CONFIG)…"
swift build -c "$CONFIG" --arch arm64 --product "$PRODUCT"
BIN_DIR="$(swift build -c "$CONFIG" --arch arm64 --show-bin-path)"

echo "▸ Assembling $APP_NAME.app…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$APP/Contents/Frameworks"
cp "$BIN_DIR/$PRODUCT" "$APP/Contents/MacOS/$PRODUCT"
cp "$ROOT/Resources/Info.plist" "$APP/Contents/Info.plist"
if [[ -f "$ROOT/Resources/AppIcon.icns" ]]; then
    cp "$ROOT/Resources/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
    /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$APP/Contents/Info.plist" >/dev/null 2>&1 || true
fi

if [[ -d "$BIN_DIR/llama.framework" ]]; then
    ditto "$BIN_DIR/llama.framework" "$APP/Contents/Frameworks/llama.framework"
    install_name_tool -add_rpath "@executable_path/../Frameworks" "$APP/Contents/MacOS/$PRODUCT" 2>/dev/null || true
fi

echo "▸ Signing (identity: $SIGN_IDENTITY)…"
CODESIGN_FLAGS=(--force --timestamp=none --sign "$SIGN_IDENTITY")
if [[ "$SIGN_IDENTITY" != "-" ]]; then
    # Hardened Runtime needs a real identity (library validation fails for ad-hoc signatures).
    CODESIGN_FLAGS+=(--options runtime)
fi
if [[ -d "$APP/Contents/Frameworks/llama.framework" ]]; then
    codesign "${CODESIGN_FLAGS[@]}" "$APP/Contents/Frameworks/llama.framework"
fi
codesign "${CODESIGN_FLAGS[@]}" --entitlements "$ENTITLEMENTS" "$APP"

echo "▸ Verifying isolation…"
"$ROOT/scripts/verify-isolation.sh" "$APP"

echo
echo "✓ Built: $APP"
echo "  Open it with:  open \"$APP\""
