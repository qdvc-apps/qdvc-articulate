# How QDVC Articulate checks text

This is the contract between the two editions: what each must do the same way, and where each keeps it.
The macOS edition's `ArticulateCore` (Swift) is the original; the GNOME edition's `qdvc/` (Python) is a
module-by-module port of it.

| What | macOS (`macos/Sources/ArticulateCore/`) | GNOME (`gtk4/qdvc/`) |
| --- | --- | --- |
| Issues, categories, groups, severities, settings | `Model/Issue.swift`, `Model/CheckSettings.swift` | `model.py` |
| Rules and the engine | `Rules/Rule.swift`, `BuiltInRules.swift`, `PhraseListRule.swift` | `rules.py` |
| Phrase lists | `Rules/PhraseData.swift` | `phrases.py` |
| US ⇄ Commonwealth spellings | `Rules/DialectLexicon.swift` | `dialect.py` |
| Sentences, statistics, exclusion zones, adjusting and merging | `Text/*.swift` | `text.py`, `textutil.py` |
| The AI pipeline | `AI/*.swift` | `ai.py` |
| The llama.cpp engine | `ArticulateLLM/LlamaEngine.swift` | `native/articulate_llama.c` through `llm.py` |
| Tests | `Tests/ArticulateCoreTests/` | `tests/test_core.py` (ported: keep in step) |

## Checking pipeline

1. **Quick checks** run 350 ms after typing stops, off the main thread: the rules, the statistics and the
   spelling checker (macOS: AppleSpell, with its grammar checker; GNOME: Enchant with Hunspell
   dictionaries, in the app's own process, with no grammar checker).
2. **The AI review** runs on demand (macOS ⇧⌘K, GNOME Ctrl+Shift+K), or 3 seconds after typing stops when
   that preference is on.
   - The text is split into paragraph chunks: paragraphs under 80 characters merge with the next, longer
     ones than the chunk size (1,200 characters by default) split at sentence boundaries. Boundaries depend
     only on local text, so after an edit only the changed paragraph misses the cache.
   - Each chunk is sent after the same instructions, rendered for the model's chat format (Gemma 4, Gemma
     2/3, ChatML, Llama 3, Mistral, Phi-3 or plain; detected from the GGUF's template and architecture). The
     instructions are the prompt *prefix*, kept in llama.cpp's KV cache and processed once.
   - A GBNF grammar forces the output to be exactly
     `{"issues":[{"original","replacement","category","explanation"}]}`. Truncated or fenced output still
     parses (every complete issue is kept).
   - The model quotes the text instead of giving offsets. Each quote is found in its paragraph, exactly,
     then ignoring case, then ignoring curly quotes, special spaces and dashes. Quotes that can't be found are
     dropped, and so are suggestions that would switch the user's variety of English.
   - Results arrive paragraph by paragraph; the model's answers are cached in memory only, keyed by model,
     format, variety of English, goals and paragraph text.
3. **Merging:** every source is validated (the text at the span must still be the quoted original),
   filtered (ignored issues, the personal dictionary for spelling, code and URL zones) and de-duplicated by
   span and group (suggestions combined, the higher severity kept), then sorted.
4. **Edits:** issues after an edit shift; issues touching it are dropped until the next check. AI results
   that arrive after further typing are mapped through the edits made since the review started.

**Exclusion zones** are never checked: fenced and inline Markdown code, URLs, e-mail addresses, Markdown
link targets and HTML-like tags.

**Units.** Spans are UTF-16 offsets on macOS (NSString) and character offsets on GNOME (Gtk.TextIter).
Nothing is stored in either unit, so the editions need not agree on this.

## Rules

| ID | Name | Category (group) | Default |
| --- | --- | --- | --- |
| `repeated-word` | Repeated words | Grammar (Correctness) | on |
| `a-an` | “a” vs “an” | Grammar (Correctness) | on |
| `common-errors` | Common mistakes | Grammar (Correctness) | on |
| `sentence-capitalization` | Sentence capitalisation | Grammar (Correctness) | on |
| `lowercase-i` | Lower-case “i” | Grammar (Correctness) | on |
| `proper-nouns` | Days, months and languages | Grammar (Correctness) | on |
| `dialect-spelling` | Regional spelling | Spelling (Correctness) | on |
| `multiple-spaces` | Multiple spaces | Typography (Delivery) | on |
| `space-before-punctuation` | Space before punctuation | Punctuation (Correctness) | on |
| `missing-space` | Missing space after punctuation | Punctuation (Correctness) | on |
| `double-punctuation` | Repeated punctuation | Punctuation (Correctness) | on |
| `unbalanced-pairs` | Unmatched brackets and quotes | Punctuation (Correctness) | on |
| `wordiness` | Wordy phrases | Concision (Clarity) | on |
| `redundancy` | Redundant phrases | Concision (Clarity) | on |
| `intensifiers` | Weak intensifiers | Word choice (Engagement) | on |
| `cliches` | Clichés | Style (Engagement) | on |
| `passive-voice` | Passive voice | Style (Engagement) | on |
| `long-sentence` | Long sentences | Clarity (Clarity) | on |
| `formality` | Formality | Tone (Delivery) | on |
| `fillers` | Filler words | Concision (Clarity) | off |
| `inclusive-language` | Inclusive language | Tone (Delivery) | off |
| `smart-typography` | Typographic dashes and ellipses | Typography (Delivery) | off |

Rule patterns are ICU regular expressions in the Swift sources and the same text in the Python sources;
`gtk4/qdvc/uregex.py` supplies the `\p{L}`, `\p{Lu}`, `\p{Ll}` and `\p{N}` classes Python's `re` lacks.
Messages, suggestions and severities are word for word the same.

## Changing how text is checked

Make the change in both editions, with a test in each (`RuleTests`/`AIPipelineTests`/`TextTests` and their
Python ports in `tests/test_core.py`), and update this document. The prompt text and the grammar are part of
the contract: a change to either changes what the AI review finds.
