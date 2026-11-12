# Vendor: llama.cpp

QDVC Articulate uses [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT licence) as a local
inference library. The build never downloads it: you place it here yourself, and `Package.swift`
links it only if `Vendor/llama.xcframework` exists. Without it, the app still builds and runs with
the rule engine and macOS spelling, and the AI features show as unavailable.

Use a llama.cpp release **b8637 or newer**. That is the first release with Gemma 4 support.

## Option A: prebuilt XCFramework

1. On the llama.cpp GitHub *Releases* page, download `llama-bXXXX-xcframework.zip` for the tag you want.
2. (Recommended) Check the SHA-256 against the value shown on the release page:
   `shasum -a 256 llama-bXXXX-xcframework.zip`
3. Unzip it and move the `llama.xcframework` folder (it may be inside a `build-apple/` folder) to:

   ```
   Vendor/llama.xcframework
   ```

## Option B: build from source

```sh
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
git checkout bXXXX            # pin a tag
./build-xcframework.sh        # produces build-apple/llama.xcframework
cp -R build-apple/llama.xcframework /path/to/QDVCArticulate/Vendor/
```

`build-xcframework.sh` builds every Apple platform (iOS, visionOS, tvOS, macOS). If an SDK is
missing, edit the script to build only the macOS slice.

## After adding or updating the framework

```sh
rm -rf .build          # SwiftPM caches whether the framework was present
scripts/build-app.sh
```

If a newer llama.cpp renames a C function, the compiler errors will all be in
`Sources/ArticulateLLM/LlamaEngine.swift`. That file is the only one that touches the llama.cpp API.
