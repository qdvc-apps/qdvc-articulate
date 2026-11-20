#!/usr/bin/env python3
"""QDVC Articulate (GTK 4 / libadwaita edition): entry point.

Checks Python, GTK 4 and libadwaita ≥ 1.5 before loading the front-end.
Documents may be given: qdvc-articulate notes.md report.docx
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if sys.version_info < (3, 10):
        print("QDVC Articulate needs Python 3.10 or later.", file=sys.stderr)
        return 1
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw
    except (ImportError, ValueError) as e:
        print(f"QDVC Articulate needs GTK 4 and libadwaita for Python (PyGObject): {e}", file=sys.stderr)
        return 1
    if (Adw.get_major_version(), Adw.get_minor_version()) < (1, 5):
        print("QDVC Articulate needs libadwaita 1.5 or later.", file=sys.stderr)
        return 1
    from qdvc.gtk4.gtk4_app import main as run
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
