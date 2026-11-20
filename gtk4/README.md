# QDVC Articulate for GNOME

A 100% offline writing checker: spelling, grammar, punctuation, wording, clarity and tone. A GNOME app built
with GTK 4 and libadwaita, packaged as a Flatpak for local use, and the companion of
[QDVC Articulate for macOS](../macos/README.md): both check text the same way
([../docs/CHECKING.md](../docs/CHECKING.md)).

**Offline, and only your files.** The Flatpak has no network permission (no `--share=network`) and no
filesystem permission: it runs with only the loopback interface, so nothing can leave the computer, and it
sees only the documents and the model you choose in the file chooser. Check it in Flatseal. Building
downloads nothing once the GNOME runtime is installed. See [docs/PRIVACY.md](docs/PRIVACY.md).

## What it does

- **Instant checks while you type.** About 20 deterministic rules (repeated words, a/an, “could of”,
  then/than, capitalisation, spacing, unmatched brackets, US/UK/CA/AU spelling consistency, wordiness,
  redundancy, clichés, passive voice, long sentences, formality), plus spelling from Enchant and the
  Hunspell dictionaries of the GNOME runtime.
- **In-depth AI review on demand (Ctrl+Shift+K).** Runs a local GGUF model through llama.cpp, on the CPU.
  Gemma 4 E4B is recommended. Output is grammar-constrained JSON, results appear paragraph by paragraph,
  and unchanged paragraphs come from the cache.
- **Writing goals** in the header bar: variety of English (US, UK, UK-Oxford, Canada, Australia),
  formality, audience and domain. They steer both the rules and the AI.
- **Editor:** plain text and Markdown documents in tabs, with drafts of unsaved changes and the tabs
  restored at the next launch, as in GNOME Text Editor. Import `.docx`, `.doc`, `.odt` and `.rtf`.
  Colour-coded underlines, an issue inspector (F9) with suggestions to apply, right-click suggestions,
  F8 to move from issue to issue, a personal dictionary, find (Ctrl+F) and statistics (word count,
  reading time, Flesch readability) in the status bar.
- **Markdown and code aware:** code blocks, inline code, URLs and e-mail addresses are never “corrected”.

The layout and its GNOME precedents are explained in [docs/DESIGN.md](docs/DESIGN.md).

## Requirements

- Flatpak and flatpak-builder (`sudo apt install flatpak flatpak-builder`,
  `sudo dnf install flatpak flatpak-builder`).
- The GNOME 50 runtime and SDK from Flathub, installed once:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//50 org.gnome.Sdk//50
```

The runtime brings Python, PyGObject, GTK 4, libadwaita and Enchant. The app has no other dependencies.
- Optional, for the AI review: a llama.cpp checkout in `vendor/llama.cpp` (see
  [vendor/README.md](vendor/README.md)) and a GGUF model.

## Build and install

From the `gtk4/` folder:

```sh
scripts/build-app.sh --install   # check, test, build the Flatpak and install it for your user
scripts/build-app.sh --run       # build and start it without installing
scripts/build-app.sh --bundle    # also write build/qdvc-articulate.flatpak
scripts/build-app.sh --uninstall # remove it (your documents, drafts and settings are untouched)
scripts/build-app.sh --no-tests  # skip the unit tests
```

The script says which AI engine it builds: `llama.cpp embedded` with `vendor/llama.cpp`, or none. The app
then appears in Activities and can be pinned to the Dock; `flatpak run qdvc.articulate.gtk4app` starts it
from a terminal (documents may follow). Text and Word files can be opened with it from Files (Open With).
Run the install again after pulling or editing the code: a running copy is asked to quit (it keeps drafts
of unsaved work) and is restarted.

**Permissions** (Flatseal, or `flatpak info --show-permissions qdvc.articulate.gtk4app`): no network; no
files (documents and the model come through the file chooser portal, which grants access to each file you
choose and keeps it across launches); Wayland or X11 and the GPU, as any GTK app.

To try it, open `../sample-texts/sample.md` (it has deliberate mistakes of every kind), or import one of
`../sample-texts/imports/`.

## Adding the AI model

1. Put a llama.cpp checkout into `vendor/llama.cpp` ([vendor/README.md](vendor/README.md)), then run
   `scripts/build-app.sh --install` again. It ends with `==> AI engine: llama.cpp embedded`.
2. Get an instruction-tuned GGUF on any device and copy it to this computer. Recommended:
   **Gemma 4 E4B Instruct, Q4_K_M** (about 5 GB, Apache 2.0). Lighter: Gemma 4 E2B. Alternative:
   Qwen3 4B/8B Instruct.
3. In the app, open Preferences › AI Model › **Choose GGUF File…**. The app remembers the file and loads
   it at launch.

## Developing

Without the Flatpak, with the distribution's GTK 4 and libadwaita 1.5 or later (`python3-gi
gir1.2-gtk-4.0 gir1.2-adw-1 libenchant-2-2` on Debian and Ubuntu):

```sh
python3 qdvc_articulate.py [documents]          # run from the checkout (not sandboxed: a banner says so)
tools/build-native.sh                           # optional: the AI engine, into build/native/
python3 -m unittest discover -s tests           # the tests (add xvfb-run -a for the window test)
```

`tests/test_engine.py` exercises the engine with a tiny random model: `python3 tools/make_test_model.py`.

## Where things are stored

- Documents: only where you save them. Unsaved changes are kept as drafts a moment after each change and
  on quit, in `~/.var/app/qdvc.articulate.gtk4app/.local/state/qdvc-articulate/` (with the open tabs).
- Preferences (goals, rules, the personal dictionary, the model's location, recent documents):
  `~/.var/app/qdvc.articulate.gtk4app/config/qdvc-articulate/config.yml`. From a checkout,
  `~/.config/qdvc-articulate/` and `~/.local/state/qdvc-articulate/`.
- AI results: in memory only.

## Keyboard shortcuts

All are listed in the app: main menu › Keyboard Shortcuts (Ctrl+?).

| Action | Shortcut |
|---|---|
| Check with AI, or stop it | Ctrl+Shift+K |
| Next / previous issue | F8 / Shift+F8 |
| Accept the first suggestion | Alt+Return |
| Ignore issue | Alt+Delete |
| Show or hide the issues | F9 |
| New document / open / import | Ctrl+N / Ctrl+O / Ctrl+Shift+I |
| Save / save as | Ctrl+S / Ctrl+Shift+S |
| Find | Ctrl+F |
| Close document / quit | Ctrl+W / Ctrl+Q |
| Preferences / keyboard shortcuts | Ctrl+, / Ctrl+? |
