# Changelog (GNOME edition)

## 1.0.0

- First version: a GTK 4 / libadwaita port of QDVC Articulate 0.2.3 for macOS, packaged as a Flatpak for
  local use (`qdvc.articulate.gtk4app`) with no network and no filesystem permission.
- The checking core ported module by module from `ArticulateCore`, with its tests: the 22 rules, phrase
  lists, the US/UK/UK-Oxford/CA/AU spelling lexicon, statistics, sentence splitting, exclusion zones,
  merging, and the AI pipeline (chunking, prompt formats including Gemma 4, GBNF-constrained JSON,
  tolerant parsing, quote anchoring, the in-memory cache).
- The AI engine: llama.cpp from a checkout in `vendor/` (CPU), through a small native library with a fixed
  interface, reusing the instructions' KV cache between paragraphs, with cancellation.
- Spelling from Enchant and the runtime's Hunspell dictionaries, in-process.
- Documents in tabs, drafts of unsaved changes and the tabs restored at launch, import of .docx, .doc,
  .odt and .rtf, underlines, the issue inspector, right-click suggestions, find, statistics, writing goals
  in the header bar, Preferences with General, Rules, AI Model, Dictionary and Privacy.
