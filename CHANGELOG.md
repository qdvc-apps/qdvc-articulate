# Changelog

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
