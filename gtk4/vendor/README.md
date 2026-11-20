# Vendor: llama.cpp

QDVC Articulate for GNOME uses [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT licence) as a local
inference library for the AI review. The build never downloads it: you place a checkout of it here, and
`scripts/build-app.sh` builds it into the Flatpak only if `vendor/llama.cpp` exists. Without it, the app
still builds and runs with the rules and the spelling checker, and the AI review says how to add it.

Use llama.cpp release **b8637 or newer** (the first with Gemma 4). The native library that talks to it
(`../native/articulate_llama.c`) has been compiled against b8637 and b12559.

## Getting it

On any computer with network access, then copied here if need be:

```sh
git clone https://github.com/ggml-org/llama.cpp vendor/llama.cpp
git -C vendor/llama.cpp checkout b12559        # pin a release tag
```

Or download a release's source archive (`llama.cpp-bXXXX.tar.gz` on the Releases page), check its SHA-256,
and unpack it so that `vendor/llama.cpp/include/llama.h` exists.

## Building

```sh
scripts/build-app.sh --install
```

The script says which engine it builds, and after building:

```
==> AI engine: llama.cpp embedded
```

It is built for the CPU only, as shared libraries, without llama.cpp's tools, server, tests or download
code (`LLAMA_BUILD_*=OFF`, `LLAMA_CURL=OFF`, `LLAMA_OPENSSL=OFF`), and tuned for the processor of the
computer that builds it (`GGML_NATIVE=ON`). For a bundle to run on other computers, set `GGML_NATIVE=OFF`
in `../flatpak/qdvc.articulate.gtk4app.yml`.

To run from a checkout instead of the Flatpak, `tools/build-native.sh` builds the same into `build/native/`.

## After updating

Run `scripts/build-app.sh --install` again. If a newer llama.cpp renames a C function, the compiler errors
will all be in `native/articulate_llama.c`: it is the only file that touches the llama.cpp API. Python
reaches it through a fixed interface of plain C types (`native/articulate_llama.h`), so the Python side
does not change.

`vendor/llama.cpp` is ignored by Git.
