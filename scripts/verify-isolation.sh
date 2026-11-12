#!/usr/bin/env bash
#
# Verifies that QDVC Articulate cannot use the network.
#
#   scripts/verify-isolation.sh --entitlements-only     # check the source entitlements file
#   scripts/verify-isolation.sh "build/QDVC Articulate.app"
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENTITLEMENTS="$ROOT/Resources/QDVCArticulate.entitlements"
FORBIDDEN=(
    "com.apple.security.network.client"
    "com.apple.security.network.server"
    "com.apple.security.temporary-exception"
    "com.apple.security.cs.disable-library-validation"
)

fail() { echo "✗ $*" >&2; exit 1; }

check_entitlements_text() {
    local text="$1" source="$2"
    for key in "${FORBIDDEN[@]}"; do
        if grep -q "$key" <<<"$text"; then
            fail "$source contains forbidden entitlement: $key"
        fi
    done
    grep -q "com.apple.security.app-sandbox" <<<"$text" || fail "$source does not enable the App Sandbox"
}

# Strip XML comments so the explanatory comment in the file doesn't trip the check.
SOURCE_TEXT="$(perl -0pe 's/<!--.*?-->//gs' "$ENTITLEMENTS")"
check_entitlements_text "$SOURCE_TEXT" "Resources/QDVCArticulate.entitlements"
echo "✓ Entitlements file: sandbox on, no network entitlements."

if [[ "${1:-}" == "--entitlements-only" ]]; then
    exit 0
fi

APP="${1:-$ROOT/build/QDVC Articulate.app}"
[[ -d "$APP" ]] || fail "App not found: $APP"

SIGNED="$(codesign -d --entitlements - --xml "$APP" 2>/dev/null || true)"
[[ -n "$SIGNED" ]] || fail "Could not read entitlements from the signed app."
check_entitlements_text "$SIGNED" "Signed app"
echo "✓ Signed app: sandbox on, no network entitlements."

PLIST="$APP/Contents/Info.plist"
if /usr/libexec/PlistBuddy -c "Print :NSAppTransportSecurity" "$PLIST" >/dev/null 2>&1; then
    fail "Info.plist contains NSAppTransportSecurity exceptions."
fi
echo "✓ Info.plist: no network exceptions."
