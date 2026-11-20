# QDVC Articulate for GNOME — Design Notes

How text is checked is the macOS edition's ([../../docs/CHECKING.md](../../docs/CHECKING.md)). This note
covers how the window is laid out for GNOME, following the GNOME HIG, and where it differs from macOS.

## Window

- **Documents in tabs** (`Adw.TabView` with an `Adw.TabBar` that hides with a single tab), as in GNOME Text
  Editor, where macOS opens a window per document. Ctrl+N opens a tab; Ctrl+PageUp/PageDown and Ctrl+Tab
  move between them; a modified tab's title starts with a dot.
- **Header bar:** Open as a split button (its arrow lists recent documents) and New Document at the start;
  at the end the writing goals (the menu button shows the variety of English; its submenus are radio items
  for English, Formality, Audience and Domain, as the macOS Goals menu), Check with AI (which becomes Stop
  while a review runs), the inspector toggle and the main menu.
- **Inspector:** an `Adw.OverlaySplitView` with the issues at its end, toggled by F9 and the header button,
  as the side panel of Files and Builder. At its head, one toggle per group (Correctness red, Clarity blue,
  Engagement green, Delivery purple) with its count, to hide or show the group. Each issue shows its
  category, source, message, the original struck through and its suggestions as buttons in the group's
  colour (five for the focused issue, two for the others), with Ignore and Add to Dictionary.
- **Status bar** along the foot: words and reading time (click for all the statistics), readability, the
  AI engine's state (loading, progress with Stop, suggestions found, errors with the message as tooltip),
  the issue count and a shield (green when the sandbox isolates the app; click for Privacy). GNOME apps
  rarely have one, but these figures are the macOS edition's and are glanced at constantly.
- **Banner** (`Adw.Banner`) when the app is not running as the Flatpak, as the macOS edition's orange
  banner for an unsandboxed build.
- **Preferences** as an `Adw.PreferencesDialog` with the macOS edition's five tabs (General, Rules, AI
  Model, Dictionary, Privacy), applied as you change them. **Dialogs**: `Adw.AlertDialog` (Save Changes?),
  `Gtk.FileDialog` (the file chooser portal in the Flatpak), toasts for imports and AI set-up.

## Editor

- A `Gtk.TextView` with generous margins and paragraph spacing; font size and a monospaced font in
  Preferences. Undo is GTK's own; opening and restoring a document are not undoable steps.
- **Underlines** are text tags: a squiggle for errors and warnings, a thin line for suggestions and hints
  (macOS draws thick and dotted lines), in the group's colour; the focused issue gets a tinted background.
  Tags never touch the text or its undo history.
- **Right-click** adds the issue's message and suggestions (with Ignore and Add to Dictionary) above GTK's
  own Cut, Copy and Paste. GTK's menu has no Share, Services or Writing Tools to remove, unlike macOS.
- **Find** (Ctrl+F) is a search bar above the text; Return and Ctrl+G go to the next match, Shift+Return and
  Ctrl+Shift+G to the previous one.
- Files dropped on the window open as tabs; Word, OpenDocument and RTF files are imported.

## Documents and drafts

macOS documents autosave, with versions. Here, as in Text Editor, unsaved changes are kept as drafts and
the tabs come back at the next launch, so quitting never asks; closing a modified tab asks whether to save.
Files are saved as UTF-8 with their own line endings (CRLF files stay CRLF). Import creates an untitled
document named after the source file, as macOS creates a new document.

## Shortcuts

Ctrl for ⌘. Where the macOS keys would clash with GTK's text view or the desktop, GNOME keys are used:

| macOS | GNOME | Why |
| --- | --- | --- |
| ⌘. (stop the AI check) | Ctrl+Shift+K again | Ctrl+. opens the emoji chooser in GTK text views |
| ⌥⌘↓ / ⌥⌘↑ (next and previous issue) | F8 / Shift+F8 | The usual “next problem” keys; Ctrl+Alt+arrows switch workspaces |
| ⌥⌘↩ (accept) | Alt+Return | No clash in the text view |
| ⌥⌘⌫ (ignore) | Alt+Delete | Ctrl+Alt+Backspace can end the X session |
| (a toolbar button) show or hide the issues | F9 | The QDVC GTK convention for side panels |

## Colours and icons

Group colours are the GNOME palette's red, blue, green and purple (the macOS system colours). Icons are
standard Adwaita symbolic icons, none from the legacy set. The app icon is the macOS design (a green tick
bubble, Meadow palette) on a page of text, in GNOME's flat style.
