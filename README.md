# QDVC Articulate

A 100% offline writing checker for macOS: spelling, grammar, punctuation, wording, clarity and
tone. Think Grammarly or LanguageTool, but nothing ever leaves your Mac, and macOS itself blocks
the app from using the network.

- **Instant checks while you type.** About 20 deterministic rules (repeated words, a/an, “could of”,
  then/than, capitalisation, spacing, unmatched brackets, US/UK/CA/AU spelling consistency, wordiness,
  redundancy, clichés, passive voice, long sentences, formality), plus the built-in macOS spelling and
  grammar checker.
- **In-depth AI review on demand (⇧⌘K).** Runs a local GGUF model through llama.cpp. Gemma 4 E4B
  is recommended. Output is grammar-constrained JSON, results appear paragraph by paragraph, and
  unchanged paragraphs come from the cache.
- **Writing goals:** variety of English (US, UK, UK-Oxford, Canada, Australia), formality, audience
  and domain. These steer both the rules and the AI.
- **Editor:** plain text and Markdown documents with autosave and versions. Import `.docx`, `.doc`,
  `.odt` and `.rtf`. Colour-coded underlines, an issue inspector, right-click suggestions, keyboard
  navigation, a personal dictionary, and statistics (word count, reading time, Flesch readability).
- **Markdown/code aware:** code blocks, inline code, URLs and e-mail addresses are never “corrected”.

Part of the QDVC suite's native macOS family. See [docs/PRIVACY.md](docs/PRIVACY.md) for the
isolation model, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it fits together, and
[docs/MAINTENANCE.md](docs/MAINTENANCE.md) for the toolchain, icon and pitfalls.

## Requirements

- Apple Silicon Mac, macOS 14 Sonoma or later
- **Full Xcode** to build, not just the Command Line Tools. From Xcode 27, SwiftUI's `@State` is a
  macro whose compiler plugin (SwiftUIMacros) ships only with Xcode, so a Command Line Tools build
  fails with "plugin for module 'SwiftUIMacros' not found". The build script finds the newest
  installed Xcode by itself.
- **Xcode 26 or later** for the macOS 26 Liquid Glass look. With an older SDK the app has the
  classic look, and the build script warns you.
- Optional, for the AI review: `llama.xcframework` (see [Vendor/README.md](Vendor/README.md)) and
  a GGUF model.

## Build

```sh
scripts/build-app.sh --install       # → build/QDVC Articulate.app, also copied to ~/Applications
scripts/build-app.sh                 # build only
scripts/build-app.sh --universal     # arm64 + x86_64
```

The script uses the newest Xcode (it sets `DEVELOPER_DIR` when `xcode-select` points at the
Command Line Tools) and builds through `xcrun`. It records the real macOS SDK in the executable
with `vtool`, which is what turns on Liquid Glass. It then signs the app ad-hoc with the App
Sandbox and **no network entitlement**, and checks that the signed app really is isolated.
No Apple Developer account is needed. To sign with your own certificate, which also enables the
Hardened Runtime:

```sh
SIGN_IDENTITY="Apple Development: Your Name (TEAMID)" scripts/build-app.sh --install
```

Without `Vendor/llama.xcframework`, the app builds without the AI engine. Everything else works.

For `swift build`, `swift run` and `swift test` outside the script, point the tools at Xcode:

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer   # this shell only
# or, system-wide:  sudo xcode-select --switch /Applications/Xcode.app
```

> A `swift run` binary is **not sandboxed** and has the classic look. The app detects the
> missing sandbox and shows an orange warning banner. Use the build script for real use.

## Adding the AI model

1. Put `llama.xcframework` into `Vendor/` (see [Vendor/README.md](Vendor/README.md)), then run
   `scripts/build-app.sh --install` again. The script notices the new framework, rebuilds from
   scratch and ends with `==> AI engine: llama.cpp embedded`.
2. Get an instruction-tuned GGUF on any device and copy it to the Mac. Recommended:
   **Gemma 4 E4B Instruct, Q4_K_M** (about 5 GB, Apache 2.0). Lighter: Gemma 4 E2B. Alternative:
   Qwen3 4B/8B Instruct.
3. In the app, open Settings → AI Model → **Choose GGUF File…**. The app remembers the file with a
   security-scoped bookmark and loads it at launch.

## Keyboard shortcuts

| Action | Shortcut |
|---|---|
| Check with AI | ⇧⌘K |
| Stop AI check | ⌘. |
| Next / previous issue | ⌥⌘↓ / ⌥⌘↑ |
| Accept first suggestion | ⌥⌘↩ |
| Ignore issue | ⌥⌘⌫ |
| Import Word/RTF/ODT | ⇧⌘I |

## Tests

The checking engine is platform-neutral, and its tests also run with a Linux Swift toolchain:

```sh
swift test        # on a Mac, with DEVELOPER_DIR pointing at Xcode (see Build)
```

## Project layout

```
Package.swift
Sources/ArticulateCore/     platform-neutral engine (rules, statistics, AI pipeline)
Sources/ArticulateLLM/      llama.cpp wrapper (stub when the framework is absent)
Sources/QDVCArticulate/     macOS app (SwiftUI + AppKit)
Tests/ArticulateCoreTests/  unit tests
Resources/                  Info.plist, entitlements (sandbox on, no network), AppIcon.svg/.icns
scripts/                    build-app.sh, verify-isolation.sh
tools/make_icon.py          regenerates the app icon
Vendor/                     put llama.xcframework here
docs/                       privacy model, architecture, maintenance
```

## Status

Version 0.2.2. It was written without access to a Mac, so expect a small round of compiler
fixes on the first Xcode build: `scripts/build-app.sh 2>&1 | grep -E "error:" | sort -u` collects
them all at once. `LlamaEngine.swift` targets the llama.cpp C API
as of release b8637+. See CHANGELOG.md.
