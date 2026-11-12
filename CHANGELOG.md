# Changelog

## 0.2.3

- Fix: the app icon was garbled at 16 px (Finder list view). The .icns stored PNG under the
  `icp4`/`icp5` codes, which some macOS drawing paths read as raw RGB. 16 and 32 px are now
  written in the classic `is32`/`s8mk` and `il32`/`l8mk` formats (verified to decode exactly).
- `build-app.sh --install` touches the installed app, so Finder and the Dock refresh its icon.

## 0.2.2

- Fix: build error with current llama.cpp (`llama_model_params` has no member `use_mmap`). Newer
  releases replaced the mmap/mlock flags with a load mode, and the default already memory-maps
  the model, so the engine now keeps the default.

## 0.2.1

- Fix: adding `Vendor/llama.xcframework` had no effect until `.build` was deleted by hand.
  SwiftPM had cached the manifest's earlier "no llama.cpp" result, so the app said it had no AI
  engine. `build-app.sh` now fingerprints the framework, cleans `.build` when it changes, checks
  that the executable links llama.cpp, and reports whether the AI engine is included.
- The engine is compiled in through an explicit `QDVC_LLAMA` flag from `Package.swift` instead
  of `canImport(llama)`, so a framework that can't be imported fails the build instead of
  producing a quiet stub.
- The "no AI engine" message in Settings now explains how to fix it.

## 0.2.0

- Adopts the QDVC macOS build mechanism: `scripts/build-app.sh [--install] [--universal]`
  selects the newest installed Xcode (SwiftUIMacros plugin), builds through `xcrun`, reports
  the compiler and SDK, and records the real SDK in the binary with `vtool`, so the app gets
  Liquid Glass. The sandbox entitlements, llama.framework embedding and isolation checks are kept.
- App icon: a green bubble with a white tick on a pale green gradient ("Meadow" palette), made
  by `tools/make_icon.py` in the suite's template.
- Bundle identifier is now `org.qdvc.articulate.mac`, following the suite.
- The editor's text view always takes exactly the size SwiftUI offers.
- New docs/MAINTENANCE.md; README requirements and build instructions updated.

## 0.1.0

- Initial version.
- Platform-neutral `ArticulateCore`: issue model, about 20 rules, a US/UK/UK-Oxford/CA/AU spelling
  lexicon, text statistics, sentence splitting, Markdown/URL exclusion zones, and an AI review
  pipeline (chunking, prompt formats incl. Gemma 4, GBNF-constrained JSON, tolerant parsing,
  quote anchoring, cache).
- `ArticulateLLM`: llama.cpp engine with prompt-prefix KV reuse and grammar-constrained sampling.
  Built conditionally.
- macOS app: document-based editor, underlines, issue inspector, context-menu suggestions,
  writing goals, settings, a personal dictionary, statistics, and import from .docx/.doc/.odt/.rtf.
- Privacy: App Sandbox with no network entitlements, a build-time verification script, a runtime
  isolation check and live probe, and Writing Tools/Services/Share disabled in the editor.
