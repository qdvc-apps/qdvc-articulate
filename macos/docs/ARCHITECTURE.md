# Architecture

```
┌─────────────────────────── QDVCArticulate (macOS app) ───────────────────────────┐
│  SwiftUI DocumentGroup · NSTextView (TextKit 1) with underline overlays          │
│  EditorController · IssueListView · StatusBar · Settings · IsolationChecker      │
│  SystemSpellChecker (AppleSpell, optional)                                       │
└───────────────┬───────────────────────────────────────────────┬──────────────────┘
                │                                               │
┌───────────────▼─────────────── ArticulateCore ────────────────▼──────────────────┐
│  Platform-neutral (Foundation only) — compiles and tests on Linux.               │
│  Issue model · RuleEngine (~20 rules) · DialectLexicon · TextStatistics          │
│  SentenceSplitter · ExclusionZones · IssueAdjuster/IssueMerger                   │
│  AI pipeline: TextChunker → PromptBuilder/PromptFormat → JSONGrammar →           │
│               LLMResponseParser → IssueAnchorer   (AIReviewer + ReviewCache)     │
└───────────────────────────────────────┬──────────────────────────────────────────┘
                                        │ TextGenerating protocol
┌───────────────────────────────────────▼─────── ArticulateLLM ────────────────────┐
│  LlamaEngine (actor) — the only file that calls the llama.cpp C API.             │
│  Prompt-prefix KV reuse · GBNF-constrained sampling · cancellation               │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Checking pipeline

1. **Quick checks** run 350 ms after typing stops: rules plus macOS spelling and grammar. Rules run
   off the main thread.
2. **AI review** runs on demand (⇧⌘K), or automatically after a 3-second pause if enabled.
   - The document is split into paragraph chunks. Short paragraphs merge with the next one, and long
     ones split at sentence boundaries. Boundaries depend only on local text, so after an edit only
     the changed paragraph misses the cache.
   - Each chunk is sent with the same instruction prefix. llama.cpp keeps that prefix in its KV
     cache, so only the paragraph itself is processed per call.
   - A GBNF grammar forces output to be exactly `{"issues":[{original, replacement, category, explanation}]}`.
   - The model quotes the text instead of giving character offsets. `IssueAnchorer` finds each
     quote in the paragraph, tolerating case and smart-quote differences. It drops suggestions it
     can't find and ones that would switch the user's variety of English.
   - Results stream into the editor as each paragraph finishes.
3. **Merging:** all sources are validated (the text at the span must still equal the quoted original),
   filtered (ignored issues, personal dictionary, code/URL zones), de-duplicated by span and group, and
   sorted.
4. **Edits:** spans after an edit shift. Issues touching the edit are dropped until the next check.
   AI results that arrive after the user has kept typing are mapped through the edits made since
   the review started.

## Text coordinates

All spans are UTF-16 offsets (`TextSpan`). That matches `NSString`/`NSTextView`. A GTK port would
convert at the UI boundary, since GTK uses UTF-8 byte offsets or character offsets.

## Other platforms

The GNOME edition in [../../gtk4/](../../gtk4/README.md) is a Python port of `ArticulateCore` (it shares no
code with this one; [../../docs/CHECKING.md](../../docs/CHECKING.md) is the contract between them). It
replaces the macOS pieces as follows:

| macOS piece | GNOME edition |
|---|---|
| SwiftUI/AppKit UI | GTK 4 and libadwaita (PyGObject); `Gtk.TextView` with text-tag underlines |
| `SystemSpellChecker` (AppleSpell) | Enchant with the runtime's Hunspell dictionaries, in-process (no grammar checker) |
| llama.xcframework | llama.cpp built from `gtk4/vendor/llama.cpp`, reached through a small C library and ctypes |
| App Sandbox (network block) | Flatpak without `--share=network` (only the loopback interface) and without filesystem access |
| Security-scoped bookmarks | The file chooser and document portals |

A Windows port would need the Windows Spell Checking API, `llama.dll` and an AppContainer without the
`internetClient` capability. `LlamaEngine` has no Apple-specific code apart from how the framework is linked.
