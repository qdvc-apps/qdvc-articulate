"""Shared widgets and helpers: CSS, small widget builders, file and alert
dialogs, and the GLib-backed environment (timers, worker threads, posting to
the main loop) that qdvc.editor and qdvc.engine run on."""

from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .. import ui_prefs as U  # noqa: E402
from ..documents import IMPORT_SUFFIXES, TEXT_SUFFIXES  # noqa: E402

CSS = """
.statusbar { padding: 2px 10px; font-size: 0.9em; border-top: 1px solid alpha(currentColor, 0.12); }
.statusbar button { padding: 0 6px; min-height: 22px; }
.numeric { font-feature-settings: "tnum"; }
.dot { min-width: 8px; min-height: 8px; border-radius: 999px; }
.group-chip { padding: 2px 8px; border-radius: 999px; }
.group-chip:not(:checked) { opacity: 0.45; }
.source-pill { font-size: 0.75em; padding: 0 6px; border-radius: 999px; background: alpha(currentColor, 0.1); }
.issue-row { padding: 8px 10px; }
.issue-original { opacity: 0.7; }
.suggestion { padding: 2px 10px; min-height: 24px; color: white; }
textview.articulate-editor text { background: @view_bg_color; }
.tint-green { color: @success_color; }
.tint-orange { color: @warning_color; }
"""


def install_css() -> None:
    css = CSS + "".join(
        f".dot-{g.value} {{ background: {c}; }} .suggestion-{g.value} {{ background: {c}; }}"
        for g, c in U.GROUP_COLOURS.items())
    provider = Gtk.CssProvider()
    _load(provider, css)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _load(provider: Gtk.CssProvider, css: str) -> None:
    if hasattr(provider, "load_from_string"):
        provider.load_from_string(css)
    else:
        provider.load_from_data(css.encode(), -1)


def rgba(hexstr: str, alpha: float = 1.0) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hexstr)
    c.alpha = alpha
    return c


# --- small widgets ----------------------------------------------------------------------------

def label(text: str = "", *classes: str, xalign: float = 0.0, wrap: bool = False, ellipsize: bool = False,
          selectable: bool = False, markup: bool = False, **kw) -> Gtk.Label:
    lab = Gtk.Label(xalign=xalign, **kw)
    if markup:
        lab.set_markup(text)
    else:
        lab.set_text(text)
    for c in classes:
        if c:
            lab.add_css_class(c)
    if wrap:
        lab.set_wrap(True)
        lab.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize:
        lab.set_ellipsize(Pango.EllipsizeMode.END)
    if selectable:
        lab.set_selectable(True)
    return lab


def hbox(*children, spacing: int = 6, **kw) -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing, **kw)
    for c in children:
        if c is not None:
            b.append(c)
    return b


def vbox(*children, spacing: int = 6, **kw) -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, **kw)
    for c in children:
        if c is not None:
            b.append(c)
    return b


def clear(box: Gtk.Widget) -> None:
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def button(text: str, callback, *classes: str, icon_name: str | None = None, tooltip: str | None = None,
           **kw) -> Gtk.Button:
    if icon_name and not text:
        b = Gtk.Button(icon_name=icon_name, **kw)
    elif icon_name:
        b = Gtk.Button(child=Adw.ButtonContent(label=text, icon_name=icon_name), **kw)
    else:
        b = Gtk.Button(label=text, **kw)
    for c in classes:
        b.add_css_class(c)
    if tooltip:
        b.set_tooltip_text(tooltip)
    if callback is not None:
        b.connect("clicked", lambda *_: callback())
    return b


def dot(group) -> Gtk.Widget:
    d = Gtk.Box(valign=Gtk.Align.CENTER)
    d.add_css_class("dot")
    d.add_css_class(f"dot-{group.value}")
    return d


def tint(widget: Gtk.Widget, name: str | None) -> Gtk.Widget:
    for n in ("green", "orange"):
        widget.remove_css_class(f"tint-{n}")
    if name:
        widget.add_css_class(f"tint-{name}")
    return widget


def escape(text: str) -> str:
    """Row titles and subtitles in libadwaita are markup: escape any text that is not."""
    return GLib.markup_escape_text(text or "")


# --- dialogs --------------------------------------------------------------------------------------

def alert(parent: Gtk.Widget, heading: str, body: str = "",
          responses: list[tuple[str, str, str | None]] | None = None, on_response=None,
          default: str | None = None, close: str | None = None) -> Adw.AlertDialog:
    """responses: (id, label, appearance: None | 'suggested' | 'destructive')."""
    d = Adw.AlertDialog(heading=heading, body=body)
    responses = responses or [("ok", "OK", None)]
    for rid, text, appearance in responses:
        d.add_response(rid, text)
        if appearance == "suggested":
            d.set_response_appearance(rid, Adw.ResponseAppearance.SUGGESTED)
        elif appearance == "destructive":
            d.set_response_appearance(rid, Adw.ResponseAppearance.DESTRUCTIVE)
    d.set_default_response(default or responses[-1][0])
    d.set_close_response(close or responses[0][0])
    if on_response is not None:
        d.connect("response", lambda _d, rid: on_response(rid))
    d.present(parent)
    return d


def _filter(name: str, patterns: list[str]) -> Gtk.FileFilter:
    f = Gtk.FileFilter()
    f.set_name(name)
    for p in patterns:
        f.add_pattern(p)
        f.add_pattern(p.upper())
    return f


def _filters(*filters: Gtk.FileFilter) -> Gio.ListStore:
    store = Gio.ListStore.new(Gtk.FileFilter)
    for f in filters:
        store.append(f)
    return store


def text_filters() -> Gio.ListStore:
    return _filters(_filter("Text and Markdown", [f"*{s}" for s in TEXT_SUFFIXES]), _filter("All files", ["*"]))


def import_filters() -> Gio.ListStore:
    pats = [f"*{s}" for s in IMPORT_SUFFIXES + TEXT_SUFFIXES]
    return _filters(_filter("Word, OpenDocument, RTF and text", pats), _filter("All files", ["*"]))


def model_filters() -> Gio.ListStore:
    return _filters(_filter("GGUF models", ["*.gguf"]), _filter("All files", ["*"]))


def choose_files(parent: Gtk.Window, title: str, filters: Gio.ListStore, on_paths, multiple: bool = True) -> None:
    """The file chooser (the portal in the Flatpak, which grants access to what is chosen)."""
    d = Gtk.FileDialog(title=title, modal=True)
    d.set_filters(filters)

    def done(dlg, res):
        try:
            if multiple:
                files = dlg.open_multiple_finish(res)
                paths = [files.get_item(i).get_path() for i in range(files.get_n_items())]
            else:
                f = dlg.open_finish(res)
                paths = [f.get_path()] if f else []
        except GLib.Error:
            return  # cancelled
        paths = [p for p in paths if p]
        if paths:
            on_paths(paths)
    if multiple:
        d.open_multiple(parent, None, done)
    else:
        d.open(parent, None, done)


def choose_save_path(parent: Gtk.Window, title: str, suggested: str, on_path) -> None:
    d = Gtk.FileDialog(title=title, modal=True, initial_name=suggested)
    d.set_filters(text_filters())

    def done(dlg, res):
        try:
            f = dlg.save_finish(res)
        except GLib.Error:
            return
        if f is not None and f.get_path():
            on_path(f.get_path())
    d.save(parent, None, done)


# --- the environment of qdvc.editor and qdvc.engine ------------------------------------------------

class GLibEnvironment:
    class Handle:
        def __init__(self, delay: float, fn):
            self._fn = fn
            self.id = GLib.timeout_add(max(0, int(delay * 1000)), self._fire)

        def _fire(self):
            self.id = 0
            self._fn()
            return False

        def cancel(self):
            if self.id:
                GLib.source_remove(self.id)
                self.id = 0

    def schedule(self, delay: float, fn):
        return GLibEnvironment.Handle(delay, fn)

    @staticmethod
    def run_in_thread(work, done) -> None:
        run_in_thread(work, done)

    @staticmethod
    def post(fn) -> None:
        GLib.idle_add(lambda: (fn(), False)[1])


def run_in_thread(work, done) -> None:
    """Runs work() on a thread and done(result) on the main loop."""
    def target():
        result = work()
        GLib.idle_add(lambda: (done(result), False)[1])
    threading.Thread(target=target, name="articulate-worker", daemon=True).start()
