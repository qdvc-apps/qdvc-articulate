# Changelog

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
