# QDVC Articulate for GNOME — Maintenance Guide

The shared conventions of the QDVC GTK apps are in the **QDVC Python desktop applications specification**,
<https://github.com/qdvc-apps/qdvc-python-gtk-app-specification/>. This guide covers only what is specific
to this app, and every place it departs from the specification (§5).

The one rule that matters most: **the checking is the contract.** How text is checked is documented in
[../../docs/CHECKING.md](../../docs/CHECKING.md) and shared with the macOS edition in `../macos`. The core
here is a port of `ArticulateCore`, and `tests/test_core.py` holds ports of its tests: a change to a rule,
a phrase list, the prompt or the grammar is made in both editions together.

## 1. Layout

```
qdvc_articulate.py        entry point (checks Python, GTK 4, libadwaita ≥ 1.5)
qdvc/                     pure core: no GTK imports
qdvc/gtk4/                the GTK 4 / libadwaita front-end (every module gtk4_*)
native/                   articulate_llama.c/.h: the only code that calls llama.cpp
vendor/                   put llama.cpp here (README.md); ignored by Git
tests/                    test_core.py (ported core tests, regex translation, offline), test_documents.py,
                          test_session.py, test_engine.py (needs build/native and a test model),
                          test_gtk4_smoke.py (stub-gi imports; the window with a display)
tests/stubs/gi/           the permissive fake gi used by the smoke test
data/                     desktop file, metainfo, launcher, icons (generated)
flatpak/                  the manifest, qdvc.articulate.gtk4app.yml
scripts/build-app.sh      checks, tests, builds and installs the Flatpak (with or without the AI engine)
tools/build-native.sh     builds llama.cpp and the native library into build/native/ (running from a checkout)
tools/make_test_model.py  a tiny random GGUF for tests/test_engine.py
tools/make_samples.py     ../sample-texts/imports/ from ../sample-texts/sample.md
tools/make_icon.py        regenerates data/icons/
docs/                     DESIGN, PRIVACY, this guide
```

The app is a port of the macOS edition and shares no code with it.

### 1.1 Offline

The app must never access the network, and sees only the files the user chooses.

- **The Flatpak has no network and no filesystem permission**: the manifest's finish-args are only ipc,
  Wayland, fallback X11 and the GPU. `scripts/build-app.sh` and `OfflineTests` refuse a manifest that
  grants network or filesystem access. Documents and the model come through the file chooser portal
  (`Gtk.FileDialog`), whose document-portal paths (`/run/user/…/doc/…`) stay valid across launches, so
  recent documents and the model's location can be remembered.
- **No networking in the sources**: no `socket`, `urllib`, `http`, `requests`, `webbrowser`, WebKit, Soup,
  `Gio.Socket*`, `Gtk.UriLauncher` or `show_uri`, and no `http://` or `https://` strings in `qdvc/`
  except XML namespace names, whose lines say `# XML namespace` (`OfflineTests`). The isolation check
  (`qdvc/isolation.py`) reads `/.flatpak-info` and `/sys/class/net` instead of opening a socket.
- **llama.cpp without its network code**: built with `LLAMA_BUILD_COMMON`, `_TOOLS`, `_SERVER`, `_APP`,
  `_EXAMPLES` and `_TESTS` off and `LLAMA_CURL`/`LLAMA_OPENSSL` off. The library itself has no networking;
  the native shim is checked for none either.
- **Nothing to download to build**: the Flatpak's sources are this folder and `vendor/llama.cpp`; nothing
  beyond the GNOME runtime is needed. The YAML reader and writer (`qdvc/yamlio.py`) is the suite's own.

## 2. Modules

Pure core (`qdvc/`), with the macOS file each was ported from:

| Module | Responsibility | macOS origin |
| --- | --- | --- |
| `model.py` | dialects, goals, `CheckSettings`, issues, categories, groups, severities, `TextSpan` | `Model/Issue.swift`, `Model/CheckSettings.swift` |
| `uregex.py` | `\p{L}`, `\p{Lu}`, `\p{Ll}`, `\p{N}` for Python's `re` | (ICU) |
| `textutil.py` | case matching, character classes, excerpts | `Text/TextUtilities.swift` |
| `text.py` | exclusion zones, sentences, statistics, `IssueAdjuster`, `IssueMerger` | `Text/*.swift` |
| `phrases.py`, `dialect.py`, `rules.py` | phrase lists, the spelling lexicon, the rules and `RuleEngine` | `Rules/*.swift` |
| `ai.py` | chunking, prompt formats, the prompt, the grammar, parsing, anchoring, `AIReviewer`, `ReviewCache` | `AI/*.swift` |
| `llm.py` | the llama.cpp engine through ctypes and `libqdvc-articulate-llama.so` | `ArticulateLLM/LlamaEngine.swift` |
| `engine.py` | `ModelManager`: the shared engine, loading on a thread, reviews | `AI/ModelManager.swift` |
| `editor.py` | `EditorState`: quick checks, the AI review, edits, merging, focus, actions | `Editor/EditorController.swift` |
| `spelling.py` | Enchant through ctypes | `Checking/SystemSpellChecker.swift` |
| `documents.py` | reading and writing text, importing .docx, .doc, .odt, .rtf | `Document/*.swift` |
| `session.py` | documents, drafts, the restored tabs | (DocumentGroup autosave) |
| `preferences.py` | preferences in YAML | `Settings/SettingsStore.swift` |
| `isolation.py` | the sandbox's own description and network interfaces | `Privacy/IsolationChecker.swift` |
| `ui_prefs.py` | `SHORTCUTS`, group colours, formatting | `Issues/IssueStyle.swift` |

Front-end (`qdvc/gtk4/`):

| Module | Responsibility |
| --- | --- |
| `gtk4_app.py` | `Adw.Application`: shared preferences, engine and spelling checker; accelerators from `ui_prefs.SHORTCUTS`; CSS, icon, app actions, About |
| `gtk4_window.py` | the window: tabs, header bar, goals menu, inspector, banner, status bar, every `win.*` action, opening, importing, saving, drafts, the session |
| `gtk4_editor.py` | `EditorPage`: the text view, underline tags, the context menu, find; the view of an `EditorState` |
| `gtk4_issues.py` | the inspector |
| `gtk4_statusbar.py` | the status bar and the statistics popover |
| `gtk4_preferences.py` | Preferences and Keyboard Shortcuts |
| `gtk4_widgets.py` | CSS, small widgets, file and alert dialogs, `GLibEnvironment` (timers, worker threads, posting to the main loop) |

### 2.1 Threads

The window never checks text itself: `EditorState` (one per tab) runs the rules, statistics and spelling
on a worker thread 0.35 s after typing stops and discards a result if the text changed meanwhile; the AI
review runs its generator on a worker thread and posts each paragraph's results to the main loop, where
they are mapped through the edits made since. ctypes releases the GIL during llama.cpp calls, so the
window stays responsive. The engine allows one generation at a time; Stop sets a flag the native loop
checks before each token. Enchant is called under a lock.

### 2.2 The native library

`native/articulate_llama.c` is compiled against the `llama.h` of `vendor/llama.cpp` (by the manifest, or
`tools/build-native.sh`) and offers Python a fixed interface of plain C types (`articulate_llama.h`,
`QAL_API_VERSION`). Python never sees llama.cpp's structs, whose layout changes between releases. It keeps
the instructions' tokens in the KV cache (sequence 0) and removes only the paragraph after each review
(`llama_memory_seq_rm`), as the macOS engine does. `llm.py` refuses a library of another API version.

## 3. Behaviour to preserve

- The ported tests: rules (a/an with acronyms and “un-” words, “could of” but not “could of course”,
  dialect spelling with Oxford -ize, deletions taking one adjacent space), the AI pipeline (truncated and
  fenced JSON, anchoring ignoring case and curly quotes, the dialect guard, the cache) and text (sentence
  splitting, adjusting, merging).
- Offsets are characters, as Gtk.TextIter counts them (an emoji is one): `RuleTests.test_offsets_are_characters`.
- A file is saved with its own line endings, atomically when the portal allows it, keeping its mode.
- Unsaved changes are never lost on quit: drafts, restored with the tabs (`SessionTests`).
- Row titles in libadwaita are markup: escape text (`gtk4_widgets.escape`); Gio menu labels treat `_` as a
  mnemonic (`_menu_label`).
- Icons must exist outside Adwaita's `legacy/` set.

## 4. llama.cpp versions

The shim compiles against b8637 (the first with Gemma 4) and b12559. In the newest releases
`llama_decode` and `llama_batch_get_one` are deprecated in favour of `llama_process` and the
`llama_batch_ext` functions; they are kept, with `-Wno-deprecated-declarations`, because the replacements
don't exist in the older releases. When the old calls are removed, port `decode_all` and the generation
loop to the new ones (the macOS `LlamaEngine.swift` will need the same).

## 5. Deviations from the specification

| Spec | This app | Why |
| --- | --- | --- |
| §1, §2, §3, §8: GTK 3 primary front-end, `--gtk3`/`--gtk4` dispatcher, `ui_backend` | **GTK 4 / libadwaita only**; `--gtk4` is accepted and ignored. | A GNOME-native port, as QDVC Case Manager and Empirics for GNOME. `qdvc/` is pure, so another front-end could be added. |
| §4: PyYAML required | Not used: `qdvc/yamlio.py` for the preferences and session. | Nothing to add to the Flatpak. |
| §4: pure Python | A small native library for llama.cpp (`native/`), and ctypes for Enchant. | llama.cpp is C/C++; Enchant has no GObject bindings. |
| §7.1: application ID `qdvc.<App>` | `qdvc.articulate.gtk4app` | Requested for the Flatpak; the GApplication ID, desktop file, icon and metainfo all use it. |
| §7.3: a stock themed icon | A bundled icon; `accessories-text-editor` when run from a checkout. | Recognisable in the Dock; Flatpak apps export their own icon. |
| §7.4: a `.desktop` launcher in `~/.local` | Installed by Flatpak. | Flatpak only. |
| §9: `Adw.PreferencesWindow`, `Adw.MessageDialog`, `Adw.AboutWindow` | `Adw.PreferencesDialog`, `Adw.AlertDialog`, `Adw.AboutDialog` (libadwaita 1.5). | The window forms are deprecated from libadwaita 1.6. |
| §9: `Adw.ViewStack` for a multi-view app | `Adw.TabView`: documents in tabs. | A document editor, as GNOME Text Editor. |
| File access: `--filesystem=home` in the other QDVC Flatpaks | None: the file chooser portal only. | Requested: the closest to the macOS sandbox's user-selected files. |
| §8: status bar is a GTK 3 element | A small status bar in GTK 4 too. | The macOS edition's word count, readability and AI state. |

## 6. Tasks

**Add a command.** Add the `win.*` action in `MainWindow._install_actions`, a menu item, and, with a
shortcut, an entry in `ui_prefs.SHORTCUTS` (which registers the accelerator and lists it).

**Change a rule, the prompt or the grammar.** Change both editions and their tests together, and
`../../docs/CHECKING.md` (§ the contract above).

**Update llama.cpp.** Replace `vendor/llama.cpp`, run `scripts/build-app.sh --install`; compile errors are
in `native/articulate_llama.c`. Then `tools/build-native.sh && python3 tools/make_test_model.py && python3
-m unittest tests.test_engine`.

**Change the runtime.** Change `runtime-version` in the manifest; the build script reads it from there.
libadwaita 1.5 is the minimum the code uses.

**Change the icon.** Edit `tools/make_icon.py` and run it (`--preview` writes `build/icon-preview.png`).

## 7. Tests

```sh
python3 -m unittest discover -s tests               # also run by scripts/build-app.sh
xvfb-run -a python3 -m unittest discover -s tests   # with the window test
```

## 8. Roadmap

- A Vulkan build of llama.cpp for GPU inference (the GNOME SDK lacks `glslc`; it would need shaderc as a
  module).
- A narrow-window layout (the inspector overlays already; the header bar could move controls to the menu).
- A grammar checker beside Enchant, if one appears that works offline in-process.
