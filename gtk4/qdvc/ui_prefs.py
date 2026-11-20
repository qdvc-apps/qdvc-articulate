"""Toolkit-independent UI tables: keyboard shortcuts (registered by the app
and listed in Keyboard Shortcuts), issue colours, and small formatting."""

from __future__ import annotations

from .model import IssueGroup

#: (section, title, action, accelerators). The macOS edition's ⌘ is Ctrl; see docs/DESIGN.md.
SHORTCUTS: list[tuple[str, str, str, list[str]]] = [
    ("Documents", "New document", "win.new-tab", ["<Control>n"]),
    ("Documents", "Open", "win.open", ["<Control>o"]),
    ("Documents", "Import Word, RTF or ODT", "win.import", ["<Control><Shift>i"]),
    ("Documents", "Save", "win.save", ["<Control>s"]),
    ("Documents", "Save as", "win.save-as", ["<Control><Shift>s"]),
    ("Documents", "Close document", "win.close-tab", ["<Control>w"]),
    ("Documents", "Find", "win.find", ["<Control>f"]),
    ("Checking", "Check with AI, or stop the AI check", "win.ai-check", ["<Control><Shift>k"]),
    ("Checking", "Next issue", "win.next-issue", ["F8"]),
    ("Checking", "Previous issue", "win.previous-issue", ["<Shift>F8"]),
    ("Checking", "Accept the first suggestion", "win.accept-suggestion", ["<Alt>Return"]),
    ("Checking", "Ignore issue", "win.ignore-issue", ["<Alt>Delete"]),
    ("Checking", "Show or hide the issues", "win.toggle-inspector", ["F9"]),
    ("Application", "Preferences", "app.preferences", ["<Control>comma"]),
    ("Application", "Keyboard shortcuts", "app.shortcuts", ["<Control>question"]),
    ("Application", "Quit", "app.quit", ["<Control>q"]),
]

#: Underline and dot colours per issue group (GNOME palette; the macOS edition's red, blue, green, purple).
GROUP_COLOURS: dict[IssueGroup, str] = {
    IssueGroup.CORRECTNESS: "#e01b24",
    IssueGroup.CLARITY: "#3584e4",
    IssueGroup.ENGAGEMENT: "#26a269",
    IssueGroup.DELIVERY: "#9141ac",
}


def plural(n: int, word: str, words: str | None = None) -> str:
    return f"{n} {word if n == 1 else (words or word + 's')}"


def display_path(path: str | None) -> str:
    """A folder for a window subtitle: ~ for the home folder; nothing for document-portal paths."""
    import os
    if not path:
        return ""
    folder = os.path.dirname(path)
    if folder.startswith("/run/user/") or folder.startswith("/run/flatpak/doc"):
        return ""
    home = os.path.expanduser("~")
    return "~" + folder[len(home):] if folder == home or folder.startswith(home + os.sep) else folder


def file_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1000.0
    return ""
