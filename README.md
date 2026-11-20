# QDVC Articulate

A 100% offline writing checker: spelling, grammar, punctuation, wording, clarity and tone. Think Grammarly
or LanguageTool, but nothing ever leaves your computer, and the operating system itself keeps the app off
the network.

About twenty deterministic rules check as you type, beside a spelling checker. An in-depth review by a
local AI model (llama.cpp running a GGUF model you choose, Gemma 4 E4B recommended) runs on demand,
paragraph by paragraph, with grammar-constrained JSON output. Writing goals (variety of English,
formality, audience, domain) steer both.

Two native editions, one way of checking:

| Edition | Folder | Built with | Isolation | Install |
| --- | --- | --- | --- | --- |
| macOS 14 and later | [`macos/`](macos/README.md) | Swift, SwiftUI and AppKit | App Sandbox, no network entitlement | `macos/scripts/build-app.sh --install` |
| GNOME and other Linux desktops | [`gtk4/`](gtk4/README.md) | Python, GTK 4 and libadwaita, as a Flatpak | Flatpak without network or file permissions | `gtk4/scripts/build-app.sh --install` |

The editions share no code. What they share is the checking itself, documented in
[docs/CHECKING.md](docs/CHECKING.md): the rules with their IDs and patterns, the phrase lists, the spelling
lexicon, the prompt, the output grammar and the review pipeline, held to by tests that are ports of one
another. Both editions build llama.cpp from a copy you supply (never downloaded by the build), and both work
without it, minus the AI review.

## Repository layout

```
docs/CHECKING.md       how text is checked: the contract between the editions
sample-texts/          a sample with deliberate mistakes, and the same as .docx, .odt and .rtf
macos/                 the macOS edition: SwiftPM package, its own README and docs
gtk4/                  the GTK 4 / libadwaita edition: Python package, native llama.cpp bridge, Flatpak manifest, docs
ai-assistance-logs/    records of AI-assisted development sessions
```

A change to how text is checked is made in both editions together (see each edition's MAINTENANCE.md).
