#!/usr/bin/env bash
# Build QDVC Articulate (GTK 4 / libadwaita) as a Flatpak and install it for
# the current user (no root, no Flathub publishing).
#
#   scripts/build-app.sh               # check, run the tests, build the Flatpak into build/
#   scripts/build-app.sh --install     # ...and install it for your user (restarts a running copy)
#   scripts/build-app.sh --run         # after building/installing, start it
#   scripts/build-app.sh --bundle      # also write build/qdvc-articulate.flatpak (a single-file bundle)
#   scripts/build-app.sh --uninstall   # remove the installed app (documents, drafts and settings untouched)
#   scripts/build-app.sh --no-tests    # skip the unit tests
#
# The AI engine is built from vendor/llama.cpp when that checkout exists
# (vendor/README.md); without it the app is built without the AI review.
# Needs flatpak and flatpak-builder, and the GNOME runtime and SDK the
# manifest names (installed once from Flathub; the script says how).
# Building itself downloads nothing.
set -euo pipefail

cd "$(dirname "$0")/.."
APP_ID="qdvc.articulate.gtk4app"
MANIFEST="flatpak/$APP_ID.yml"
BUILD="build/flatpak-app"
STATE="build/flatpak-builder"
REPO="build/flatpak-repo"
RUNTIME_VERSION="$(sed -n "s/^runtime-version: *'\{0,1\}\([^']*\)'\{0,1\}/\1/p" "$MANIFEST")"

install=0 uninstall=0 tests=1 run=0 bundle=0
for arg in "$@"; do
    case "$arg" in
        --install) install=1 ;;
        --uninstall) uninstall=1 ;;
        --no-tests) tests=0 ;;
        --run) run=1 ;;
        --bundle) bundle=1 ;;
        -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg (see --help)" >&2; exit 2 ;;
    esac
done

say() { printf '==> %s\n' "$*"; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "error: $1 is not installed. $2" >&2; exit 1; }; }

need flatpak "Install it from your distribution (e.g. sudo apt install flatpak)."

running() { flatpak ps --columns=application 2>/dev/null | grep -qx "$APP_ID"; }
quit_running() {
    # Ask the running copy to quit through its D-Bus actions (it keeps drafts of unsaved work).
    if command -v gdbus >/dev/null 2>&1; then
        gdbus call --session --dest "$APP_ID" --object-path "/${APP_ID//./\/}" \
            --method org.gtk.Actions.Activate quit [] {} >/dev/null 2>&1 || true
    fi
    for _ in $(seq 1 30); do running || return 0; sleep 0.1; done
    flatpak kill "$APP_ID" 2>/dev/null || true
}

if [[ $uninstall -eq 1 ]]; then
    running && { say "Quitting the running copy"; quit_running; }
    flatpak uninstall --user -y "$APP_ID" || true
    say "Uninstalled (your documents and ~/.var/app/$APP_ID are untouched)"
    exit 0
fi

need flatpak-builder "Install it from your distribution (e.g. sudo apt install flatpak-builder)."

# --- the runtime ------------------------------------------------------------
missing=()
for ref in "org.gnome.Platform//$RUNTIME_VERSION" "org.gnome.Sdk//$RUNTIME_VERSION"; do
    flatpak info "$ref" >/dev/null 2>&1 || missing+=("$ref")
done
if [[ ${#missing[@]} -gt 0 ]]; then
    cat >&2 <<HELP
error: the GNOME $RUNTIME_VERSION runtime is not installed. Install it once (this is the only download):
  flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
  flatpak install --user flathub ${missing[*]}
(To build against another GNOME version, change runtime-version in $MANIFEST.)
HELP
    exit 1
fi
if ! flatpak run --command=python3 "org.gnome.Platform//$RUNTIME_VERSION" -c \
        'import ctypes.util, gi; gi.require_version("Adw", "1"); assert ctypes.util.find_library("enchant-2")' \
        >/dev/null 2>&1; then
    echo "error: the GNOME $RUNTIME_VERSION runtime lacks PyGObject, libadwaita or Enchant" >&2
    exit 1
fi
say "GNOME $RUNTIME_VERSION runtime: Python, PyGObject, libadwaita and Enchant present"

# --- checks and tests ---------------------------------------------------------
finish="$(sed -n '/^finish-args:/,/^[a-z]/p' "$MANIFEST")"
if grep -nE -- '--share=network|--socket=network|--filesystem' <<<"$finish"; then
    echo "error: $MANIFEST must not grant network or filesystem access" >&2
    exit 1
fi
if [[ $tests -eq 1 ]]; then
    say "Running the tests"
    python3 -m unittest discover -s tests -q
fi
command -v desktop-file-validate >/dev/null 2>&1 && desktop-file-validate "data/$APP_ID.desktop"
command -v appstreamcli >/dev/null 2>&1 && appstreamcli validate --no-net --explain "data/$APP_ID.metainfo.xml" >/dev/null \
    || true

# --- the AI engine: vendor/llama.cpp or none ------------------------------------
if [[ -f vendor/llama.cpp/include/llama.h ]]; then
    effective="$MANIFEST"
    engine="llama.cpp from vendor/llama.cpp ($(git -C vendor/llama.cpp describe --tags --always 2>/dev/null || echo 'version unknown'))"
else
    # The same manifest without the llama.cpp modules, beside it so that its relative paths still hold.
    effective="flatpak/.$APP_ID.no-ai.yml"
    sed '/# BEGIN llama.cpp/,/# END llama.cpp/d' "$MANIFEST" >"$effective"
    engine="none (no vendor/llama.cpp: the app is built without the AI review; see vendor/README.md)"
fi
say "AI engine: $engine"

# --- build ---------------------------------------------------------------------
was_running=0
if [[ $install -eq 1 ]] && running; then
    say "Quitting the running copy (it keeps drafts of unsaved work)"
    quit_running
    was_running=1
fi
say "Building $APP_ID (GNOME $RUNTIME_VERSION)"
builder=(flatpak-builder --force-clean --disable-rofiles-fuse --state-dir="$STATE")
if [[ $install -eq 1 ]]; then
    "${builder[@]}" --user --install "$BUILD" "$effective"
else
    "${builder[@]}" "$BUILD" "$effective"
fi
if [[ -f "$BUILD/files/lib/libqdvc-articulate-llama.so" ]]; then
    say "AI engine: llama.cpp embedded"
elif [[ "$effective" == "$MANIFEST" ]]; then
    echo "error: vendor/llama.cpp is present but the AI engine was not built" >&2
    exit 1
fi
if [[ $bundle -eq 1 ]]; then
    "${builder[@]}" --repo="$REPO" "$BUILD" "$effective" >/dev/null
    flatpak build-bundle "$REPO" "build/qdvc-articulate.flatpak" "$APP_ID"
    say "Wrote build/qdvc-articulate.flatpak (install elsewhere with flatpak install --user <file>)"
fi
if [[ $install -eq 1 ]]; then
    say "Installed: open QDVC Articulate from Activities, or run: flatpak run $APP_ID"
    say "Permissions: no network, no files beyond those you choose. Check them with Flatseal or: flatpak info --show-permissions $APP_ID"
    if [[ $was_running -eq 1 ]]; then run=1; fi
fi
if [[ $run -eq 1 ]]; then
    if [[ $install -eq 1 ]]; then
        say "Starting QDVC Articulate"
        nohup flatpak run "$APP_ID" >/dev/null 2>&1 &
    else
        say "Starting the build (not installed)"
        nohup flatpak-builder --run "$BUILD" "$effective" qdvc-articulate >/dev/null 2>&1 &
    fi
fi
say "Done"
