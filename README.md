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

See [docs/PRIVACY.md](docs/PRIVACY.md) for the isolation model and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it fits together.

## Requirements

- Apple Silicon Mac, macOS 14 Sonoma or later
- Xcode 16 or later (for building)
- Optional, for the AI review: `llama.xcframework` (see [Vendor/README.md](Vendor/README.md)) and a GGUF model

## Build

```sh
scripts/build-app.sh                 # → build/QDVC Articulate.app (sandboxed, ad-hoc signed)
open "build/QDVC Articulate.app"
```

Without `Vendor/llama.xcframework`, the app builds without the AI engine. Everything else works.
To sign with your own certificate (this also enables the Hardened Runtime):

```sh
SIGN_IDENTITY="Apple Development: Your Name (TEAMID)" scripts/build-app.sh
```

> `swift run QDVCArticulate` also works for quick UI iteration, but that binary is **not sandboxed**.
> The app detects this and shows an orange warning banner. Use `build-app.sh` for real use.

## Adding the AI model

1. Put `llama.xcframework` into `Vendor/` (see [Vendor/README.md](Vendor/README.md)), then
   `rm -rf .build && scripts/build-app.sh`.
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

The checking engine is platform-neutral and its tests also run on Linux:

```sh
swift test
```

## Project layout

```
Package.swift
Sources/ArticulateCore/     platform-neutral engine (rules, statistics, AI pipeline)
Sources/ArticulateLLM/      llama.cpp wrapper (stub when the framework is absent)
Sources/QDVCArticulate/     macOS app (SwiftUI + AppKit)
Tests/ArticulateCoreTests/  unit tests
Resources/                  Info.plist, entitlements (sandbox on, no network)
scripts/                    build-app.sh, verify-isolation.sh
Vendor/                     put llama.xcframework here
docs/                       privacy model, architecture
```

## Status

Version 0.1.0 is the first iteration. It was written without access to a Mac, so expect a small
round of compiler fixes on the first Xcode build. `LlamaEngine.swift` targets the llama.cpp C API
as of release b8637+. See CHANGELOG.md.
