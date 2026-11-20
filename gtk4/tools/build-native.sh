#!/usr/bin/env bash
# Build the AI engine for running from a checkout (without the Flatpak):
# llama.cpp from vendor/llama.cpp, CPU only, and the small native library
# Python calls (native/articulate_llama.c), into build/native/. The app looks
# there when it is started with python3 qdvc_articulate.py.
#
#   tools/build-native.sh            # needs cmake, ninja (or make) and a C/C++ compiler
#   LLAMA_SRC=/path/to/llama.cpp tools/build-native.sh
#
# The Flatpak build does the same in flatpak/qdvc.articulate.gtk4app.yml;
# keep the cmake options of both in step. Nothing is downloaded.
set -euo pipefail

cd "$(dirname "$0")/.."
SRC="${LLAMA_SRC:-vendor/llama.cpp}"
BUILD="build/llama"
PREFIX="build/llama-install"
OUT="build/native"

if [[ ! -f "$SRC/include/llama.h" ]]; then
    echo "error: no llama.cpp in $SRC (see vendor/README.md)" >&2
    exit 1
fi
generator=()
command -v ninja >/dev/null 2>&1 && generator=(-G Ninja)

echo "==> Building llama.cpp from $SRC (CPU)"
cmake -S "$SRC" -B "$BUILD" "${generator[@]}" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PWD/$PREFIX" \
    -DBUILD_SHARED_LIBS=ON -DGGML_NATIVE=ON -DGGML_BACKEND_DL=OFF \
    -DLLAMA_BUILD_COMMON=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_TOOLS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_APP=OFF -DLLAMA_CURL=OFF -DLLAMA_OPENSSL=OFF >/dev/null
cmake --build "$BUILD" --config Release -j "$(nproc 2>/dev/null || echo 4)" >/dev/null
cmake --install "$BUILD" >/dev/null

echo "==> Building $OUT/libqdvc-articulate-llama.so"
mkdir -p "$OUT"
libdir="$PREFIX/lib"
[[ -d "$libdir" ]] || libdir="$PREFIX/lib64"
cp -a "$libdir"/libllama.so* "$libdir"/libggml*.so* "$OUT"/
# -Wno-deprecated-declarations: llama_decode and llama_batch_get_one are deprecated in the newest
# llama.cpp but still the calls that work across the supported releases (MAINTENANCE.md §4).
cc -O2 -Wall -Wno-deprecated-declarations -shared -fPIC native/articulate_llama.c -I"$PREFIX/include" \
    -L"$OUT" -lllama -Wl,--disable-new-dtags,-rpath,'$ORIGIN' -o "$OUT/libqdvc-articulate-llama.so"
echo "==> Done: python3 qdvc_articulate.py now has the AI engine"
