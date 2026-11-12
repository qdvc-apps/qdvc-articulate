#!/usr/bin/env bash
# Build "QDVC Articulate.app" from the Swift package, sandboxed, and sign it.
#
# No Apple Developer account is needed: ad-hoc signing ("Sign to Run
# Locally") is enough for the app to run on the Mac that built it. The app
# is signed with the App Sandbox ON and NO network entitlement, so macOS
# itself denies it every network connection (docs/PRIVACY.md).
#
#   scripts/build-app.sh              # release build into build/
#   scripts/build-app.sh --universal  # arm64 + x86_64
#   scripts/build-app.sh --install    # also copy to ~/Applications
#
#   SIGN_IDENTITY="Apple Development: …" scripts/build-app.sh
#                                     # sign with a real identity (adds the Hardened Runtime)
#
# Needs full Xcode (not just the Command Line Tools); the newest installed
# Xcode is used if xcode-select points at the Command Line Tools.
set -euo pipefail

cd "$(dirname "$0")/.."

universal=0
install=0
for arg in "$@"; do
    case "$arg" in
        --universal) universal=1 ;;
        --install) install=1 ;;
        -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

# --- Toolchain (shared with the other QDVC macOS apps; keep in step) ---------
# Build with full Xcode's toolchain. From Xcode 27, SwiftUI's @State is a
# macro, and its implementation (the SwiftUIMacros compiler plugin) comes
# with Xcode: a build with the Command Line Tools alone, or with a swift.org
# toolchain, fails with "plugin for module 'SwiftUIMacros' not found".
# The newest Xcode installed (by major version), or nothing.
newest_xcode() {
    local best="" best_major=0 x v major
    while IFS= read -r x; do
        [[ -d "$x" ]] || continue
        v="$(defaults read "$x/Contents/Info" CFBundleShortVersionString 2>/dev/null || echo 0)"
        major="${v%%.*}"
        [[ "$major" =~ ^[0-9]+$ ]] || continue
        if (( major > best_major )); then best="$x"; best_major=$major; fi
    done < <({ mdfind "kMDItemCFBundleIdentifier == 'com.apple.dt.Xcode'" 2>/dev/null || true
               ls -d /Applications/Xcode*.app 2>/dev/null || true; } | sort -u)
    echo "$best"
}

if [[ -z "${DEVELOPER_DIR:-}" ]] && [[ "$(xcode-select -p 2>/dev/null || true)" == *CommandLineTools* ]]; then
    xcode="$(newest_xcode)"
    if [[ -n "$xcode" ]]; then
        export DEVELOPER_DIR="$xcode/Contents/Developer"
        echo "==> Using $xcode (xcode-select points at the Command Line Tools)"
    else
        echo "warning: building with the Command Line Tools; if it fails with \"SwiftUIMacros\" not found, install Xcode" >&2
    fi
fi
# xcrun: Xcode's swift, even if another toolchain comes first on PATH.
echo "==> $(xcrun swift --version 2>&1 | head -n 1)"
sdk="$(xcrun --sdk macosx --show-sdk-version 2>/dev/null || echo unknown)"
echo "==> macOS SDK $sdk ($(xcode-select -p 2>/dev/null || true)${DEVELOPER_DIR:+, DEVELOPER_DIR=$DEVELOPER_DIR})"
sdk_major="${sdk%%.*}"
if [[ "$sdk_major" =~ ^[0-9]+$ ]] && (( sdk_major < 26 )); then
    newer="$(newest_xcode)"
    echo "warning: the macOS $sdk SDK predates Liquid Glass, so the app will have the classic look." >&2
    echo "         Build with Xcode 26 or later for Liquid Glass${newer:+ (newest installed: $newer)}." >&2
fi
# --- end of shared toolchain block --------------------------------------------

# Refuse to build at all if a network entitlement has crept in.
scripts/verify-isolation.sh --entitlements-only

if [[ -d Vendor/llama.xcframework ]]; then
    echo "==> Vendor/llama.xcframework found: building with the AI engine"
else
    echo "==> Vendor/llama.xcframework not found: building without the AI engine (rules and macOS spelling only)"
fi

build_args=(-c release --product QDVCArticulate)
if [[ $universal -eq 1 ]]; then
    build_args+=(--arch arm64 --arch x86_64)
fi

echo "==> swift build ${build_args[*]}"
xcrun swift build "${build_args[@]}"
bin_dir="$(xcrun swift build "${build_args[@]}" --show-bin-path)"

app="build/QDVC Articulate.app"
echo "==> Assembling $app"
rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$bin_dir/QDVCArticulate" "$app/Contents/MacOS/QDVCArticulate"

# Liquid Glass. AppKit gives an app the new look only if it was linked
# against the macOS 26 SDK or later, which it reads from the "sdk" field of
# the binary's LC_BUILD_VERSION load command. `swift build` writes the
# deployment target there instead (minos 14.0, sdk 14.0), so the app ran
# with the classic look whatever SDK it was built with. Record the SDK the
# build really used (the binary is re-signed below).
bin="$app/Contents/MacOS/QDVCArticulate"
build_field() { xcrun vtool -show-build "$bin" 2>/dev/null | awk -v k="$1" '$1 == k { print $2; exit }'; }
minos="$(build_field minos)"
linked_sdk="$(build_field sdk)"
if [[ "$sdk" =~ ^[0-9]+(\.[0-9]+)*$ ]] && [[ -n "$minos" ]] && [[ "$linked_sdk" != "$sdk" ]]; then
    echo "==> Recording macOS SDK $sdk in the binary (the linker wrote ${linked_sdk:-nothing})"
    xcrun vtool -set-build-version macos "$minos" "$sdk" -replace -output "$bin.tmp" "$bin"
    mv "$bin.tmp" "$bin"
fi
echo "==> Binary built for macOS $(build_field minos) and later, with SDK $(build_field sdk)"
cp Resources/Info.plist "$app/Contents/Info.plist"
printf 'APPL????' > "$app/Contents/PkgInfo"
# App icon (regenerate with tools/make_icon.py; Info.plist names it AppIcon).
cp Resources/AppIcon.icns "$app/Contents/Resources/AppIcon.icns"

# llama.cpp, when present, is a dynamic framework next to the executable.
if [[ -d "$bin_dir/llama.framework" ]]; then
    echo "==> Embedding llama.framework"
    mkdir -p "$app/Contents/Frameworks"
    ditto "$bin_dir/llama.framework" "$app/Contents/Frameworks/llama.framework"
    if ! otool -l "$bin" | grep -q "@executable_path/../Frameworks"; then
        install_name_tool -add_rpath "@executable_path/../Frameworks" "$bin"
    fi
fi

identity="${SIGN_IDENTITY:--}"
sign_args=(--force --sign "$identity" --timestamp=none)
if [[ "$identity" == "-" ]]; then
    echo "==> Ad-hoc signing (App Sandbox, no network entitlements)"
else
    # The Hardened Runtime's library validation needs a real identity.
    echo "==> Signing as \"$identity\" (App Sandbox, no network entitlements, Hardened Runtime)"
    sign_args+=(--options runtime)
fi
if [[ -d "$app/Contents/Frameworks/llama.framework" ]]; then
    codesign "${sign_args[@]}" "$app/Contents/Frameworks/llama.framework"
fi
codesign "${sign_args[@]}" --entitlements Resources/QDVCArticulate.entitlements "$app"
codesign --verify --verbose=1 "$app"
scripts/verify-isolation.sh "$app"

if [[ $install -eq 1 ]]; then
    mkdir -p "$HOME/Applications"
    rm -rf "$HOME/Applications/QDVC Articulate.app"
    ditto "$app" "$HOME/Applications/QDVC Articulate.app"
    echo "==> Installed to ~/Applications/QDVC Articulate.app"
fi

echo "Done: $(pwd)/$app"
