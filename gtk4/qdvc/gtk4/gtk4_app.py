"""The Adw.Application: shared state (preferences, the AI engine, the spelling
checker), accelerators from ui_prefs.SHORTCUTS, CSS, the icon, and the app.*
actions (quit, preferences, shortcuts, about). One window, documents in tabs;
files given on the command line or by the file manager open as tabs."""

from __future__ import annotations

import sys

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .. import APP_ID, APP_NAME, PRGNAME, __version__
from .. import ui_prefs as U
from ..engine import ModelManager
from ..preferences import Preferences
from ..spelling import SpellChecker
from .gtk4_preferences import shortcuts_dialog
from .gtk4_widgets import install_css, run_in_thread
from .gtk4_window import MainWindow

GLib.set_prgname(PRGNAME)
GLib.set_application_name(APP_NAME)
FALLBACK_ICON = "accessories-text-editor"


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.window: MainWindow | None = None
        self.icon_name = APP_ID
        self.prefs = Preferences()
        self.spell = SpellChecker()
        self.models = ModelManager(self.prefs, run_in_thread)

    def do_startup(self):
        Adw.Application.do_startup(self)
        install_css()
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        if not theme.has_icon(APP_ID):
            self.icon_name = FALLBACK_ICON
        Gtk.Window.set_default_icon_name(self.icon_name)
        for name, fn in (("quit", self._quit), ("preferences", lambda: self._win().show_preferences()),
                         ("shortcuts", lambda: shortcuts_dialog(self._win())), ("about", self._about)):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a, _p, fn=fn: fn())
            self.add_action(a)
        for _section, _title, action, accels in U.SHORTCUTS:
            self.set_accels_for_action(action, accels)
        if self.prefs.llama.load_at_launch:
            self.models.load()

    def _win(self) -> MainWindow:
        if self.window is None:
            self.window = MainWindow(self)
            self.window.restore_session()
        return self.window

    def do_activate(self):
        self._win().present()

    def do_open(self, files, n_files, hint):
        win = self._win()
        for f in files:
            if f.get_path():
                win.open_path(f.get_path())
        win.present()

    def do_shutdown(self):
        self.models.engine.unload()
        self.spell.close()
        Adw.Application.do_shutdown(self)

    def _quit(self):
        if self.window is not None:
            self.window.close()
        self.quit()

    def _about(self):
        d = Adw.AboutDialog(application_name=APP_NAME, application_icon=self.icon_name, developer_name="QDVC",
                            version=__version__,
                            comments="A 100% offline writing checker: spelling, grammar, punctuation, wording, "
                                     "clarity and tone, with an optional local AI model (llama.cpp). Nothing ever "
                                     "leaves your computer: the Flatpak has no network access.")
        d.add_legal_section("llama.cpp", "Copyright © The ggml authors", Gtk.License.MIT_X11, None)
        d.present(self._win())


def main(argv: list[str] | None = None) -> int:
    argv = [a for a in (sys.argv if argv is None else argv) if a != "--gtk4"]
    return App().run(argv)
