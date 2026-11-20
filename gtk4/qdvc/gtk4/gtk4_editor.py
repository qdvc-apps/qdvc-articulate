"""One tab: the text view with issue underlines, its context menu of
suggestions and its find bar, driving a qdvc.editor.EditorState (the port
of the macOS edition's EditorController and EditorTextView).

Offsets: Gtk.TextIter offsets count characters, as the core's spans do, so
no conversion is needed at this boundary.
"""

from __future__ import annotations

from gi.repository import Gio, GLib, GObject, Gtk, Pango

from .. import ui_prefs as U
from ..editor import EditorState
from ..model import IssueCategory, IssueGroup, IssueSeverity
from ..session import Document
from .gtk4_widgets import GLibEnvironment, rgba

MAX_MENU_SUGGESTIONS = 6


class EditorPage(Gtk.Box):
    """A tab's content. `changed` fires when the title or modified state may have changed."""

    __gsignals__ = {"changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, prefs, models, spell, document: Document | None = None, text: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.prefs = prefs
        self.document = document or Document()
        self.state = EditorState(prefs, models, spell, GLibEnvironment(), view=self)
        self._loading = False
        self._menu_issue = None

        # Find bar.
        self.search_entry = Gtk.SearchEntry(placeholder_text="Find in document", hexpand=True)
        self.search_bar = Gtk.SearchBar(child=self.search_entry, show_close_button=True)
        self.search_bar.connect_entry(self.search_entry)
        self.search_entry.connect("activate", lambda *_: self.find(forward=True))
        self.search_entry.connect("next-match", lambda *_: self.find(forward=True))
        self.search_entry.connect("previous-match", lambda *_: self.find(forward=False))
        self.search_entry.connect("search-changed", lambda *_: self.find(forward=True, from_start=True))
        self.search_entry.connect("stop-search", lambda *_: self.close_find())
        self.append(self.search_bar)

        # The text view: plain text, our own checking only.
        self.buffer = Gtk.TextBuffer()
        self.view = Gtk.TextView(buffer=self.buffer, wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=28,
                                 right_margin=28, top_margin=22, bottom_margin=22, vexpand=True, hexpand=True)
        self.view.add_css_class("articulate-editor")
        self.view.set_input_hints(Gtk.InputHints.NO_SPELLCHECK)
        scroller = Gtk.ScrolledWindow(child=self.view, vexpand=True, hexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroller)

        self._make_tags()
        self._install_menu_actions()
        click = Gtk.GestureClick(button=3)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_right_click)
        self.view.add_controller(click)

        self.buffer.connect("insert-text", self._on_insert)
        self.buffer.connect("delete-range", self._on_delete)
        self.buffer.connect("changed", self._on_changed)
        self.buffer.connect("notify::cursor-position", self._on_cursor)
        self.state.connect(self._on_state)
        self.apply_editor_preferences()
        self.load_text(text)

    # --- text in and out ---------------------------------------------------------------------

    @property
    def text(self) -> str:
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, True)

    @property
    def modified(self) -> bool:
        return self.document.is_modified(self.state.text)

    @property
    def title(self) -> str:
        return self.document.title

    @property
    def cursor(self) -> int:
        return self.buffer.get_property("cursor-position")

    def load_text(self, text: str, cursor: int = 0) -> None:
        """Replaces the whole text without an undo step (opening, restoring)."""
        self._loading = True
        self.buffer.begin_irreversible_action()
        self.buffer.set_text(text)
        self.buffer.end_irreversible_action()
        self._loading = False
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(min(max(cursor, 0), len(text))))
        self.state.load(text)
        self.emit("changed")

    def apply_editor_preferences(self) -> None:
        self.view.set_monospace(self.prefs.monospace)
        size = self.prefs.editor_font_size
        self.view.set_pixels_below_lines(round(size * 0.45))
        self.view.set_pixels_inside_wrap(round(size * 0.2))

    # --- edits ---------------------------------------------------------------------------------

    def _on_insert(self, _buffer, location, text, _length):
        if not self._loading:
            self.state.will_edit(location.get_offset(), 0, len(text))

    def _on_delete(self, _buffer, start, end):
        if not self._loading:
            self.state.will_edit(start.get_offset(), end.get_offset() - start.get_offset(), 0)

    def _on_changed(self, _buffer):
        if self._loading:
            return
        self.state.text_changed(self.text)
        self.emit("changed")

    def _on_cursor(self, *_):
        _, start, end = self._selection()
        self.state.selection_changed(start, end)

    def _selection(self) -> tuple[bool, int, int]:
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            return True, bounds[0].get_offset(), bounds[1].get_offset()
        c = self.cursor
        return False, c, c

    # The view protocol of EditorState.

    def replace_range(self, start: int, end: int, text: str) -> None:
        self.buffer.begin_user_action()
        a, b = self.buffer.get_iter_at_offset(start), self.buffer.get_iter_at_offset(end)
        self.buffer.delete(a, b)
        a = self.buffer.get_iter_at_offset(start)
        self.buffer.insert(a, text)
        self.buffer.end_user_action()
        self.buffer.place_cursor(self.buffer.get_iter_at_offset(start + len(text)))

    def reveal(self, start: int, end: int) -> None:
        self.buffer.select_range(self.buffer.get_iter_at_offset(start), self.buffer.get_iter_at_offset(end))
        self.view.grab_focus()
        GLib.idle_add(lambda: (self.view.scroll_to_mark(self.buffer.get_insert(), 0.2, False, 0.0, 0.0), False)[1])

    # --- underlines ------------------------------------------------------------------------------

    def _make_tags(self) -> None:
        self._tags = {}
        for group in IssueGroup:
            colour = rgba(U.GROUP_COLOURS[group])
            self._tags[(group, True)] = self.buffer.create_tag(
                f"issue-{group.value}-strong", underline=Pango.Underline.ERROR, underline_rgba=colour)
            self._tags[(group, False)] = self.buffer.create_tag(
                f"issue-{group.value}-weak", underline=Pango.Underline.SINGLE, underline_rgba=colour)
        # Created last, so it draws above the underlines.
        self._focus_tags = {g: self.buffer.create_tag(f"focus-{g.value}",
                                                      background_rgba=rgba(U.GROUP_COLOURS[g], 0.18))
                            for g in IssueGroup}

    def apply_underlines(self) -> None:
        start, end = self.buffer.get_bounds()
        for tag in list(self._tags.values()) + list(self._focus_tags.values()):
            self.buffer.remove_tag(tag, start, end)
        length = self.buffer.get_char_count()
        for issue in self.state.visible_issues:
            if issue.span.upper_bound > length:
                continue
            a = self.buffer.get_iter_at_offset(issue.span.location)
            b = self.buffer.get_iter_at_offset(issue.span.upper_bound)
            group = issue.category.group
            self.buffer.apply_tag(self._tags[(group, issue.severity >= IssueSeverity.WARNING)], a, b)
            if issue.id == self.state.focused_id:
                self.buffer.apply_tag(self._focus_tags[group], a, b)

    def _on_state(self, what: str) -> None:
        if what in ("issues", "focus"):
            self.apply_underlines()
            self._update_menu(self.state.issue_at(self.cursor))

    # --- the context menu ------------------------------------------------------------------------

    def _install_menu_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        apply = Gio.SimpleAction.new("apply", GLib.VariantType.new("i"))
        apply.connect("activate", self._menu_apply)
        group.add_action(apply)
        for name, fn in (("ignore", self._menu_ignore), ("add-word", self._menu_add_word)):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a, _p, fn=fn: fn())
            group.add_action(a)
        self.view.insert_action_group("editor", group)

    def _on_right_click(self, _gesture, _n, x, y) -> None:
        bx, by = self.view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
        found = self.view.get_iter_at_location(bx, by)
        it = found[1] if isinstance(found, tuple) else found
        self._update_menu(self.state.issue_at(it.get_offset()) if it is not None else None)

    def _update_menu(self, issue) -> None:
        """Suggestions for the issue under the pointer or the cursor, above the view's own Cut/Copy/Paste."""
        if issue is self._menu_issue:
            return
        self._menu_issue = issue
        if issue is None:
            self.view.set_extra_menu(None)
            return
        menu = Gio.Menu()
        head = Gio.Menu()
        head.append(_menu_label(issue.message), None)  # no action: shown as a heading
        menu.append_section(None, head)
        choices = Gio.Menu()
        for i, s in enumerate(issue.suggestions[:MAX_MENU_SUGGESTIONS]):
            text = f"Remove “{issue.original.strip()}”" if s == "" else s.replace("\n", "↵")
            item = Gio.MenuItem.new(_menu_label(text), None)
            item.set_action_and_target_value("editor.apply", GLib.Variant.new_int32(i))
            choices.append_item(item)
        choices.append("Ignore", "editor.ignore")
        if issue.category is IssueCategory.SPELLING:
            choices.append(_menu_label(f"Add “{issue.original}” to Dictionary"), "editor.add-word")
        menu.append_section(None, choices)
        self.view.set_extra_menu(menu)

    def _menu_apply(self, _action, param) -> None:
        issue = self._menu_issue
        if issue is not None and 0 <= param.get_int32() < len(issue.suggestions):
            self.state.apply(issue, issue.suggestions[param.get_int32()])

    def _menu_ignore(self) -> None:
        if self._menu_issue is not None:
            self.state.ignore(self._menu_issue)

    def _menu_add_word(self) -> None:
        if self._menu_issue is not None:
            self.state.add_to_dictionary(self._menu_issue)

    # --- find --------------------------------------------------------------------------------------

    def open_find(self) -> None:
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            selected = self.buffer.get_text(bounds[0], bounds[1], True)
            if "\n" not in selected:
                self.search_entry.set_text(selected)
        self.search_bar.set_search_mode(True)
        self.search_entry.grab_focus()

    def close_find(self) -> None:
        self.search_bar.set_search_mode(False)
        self.view.grab_focus()

    def find(self, forward: bool = True, from_start: bool = False) -> bool:
        needle = self.search_entry.get_text()
        if not needle:
            return False
        flags = Gtk.TextSearchFlags.CASE_INSENSITIVE | Gtk.TextSearchFlags.TEXT_ONLY
        bounds = self.buffer.get_selection_bounds()
        if from_start:
            origin = bounds[0] if bounds else self.buffer.get_iter_at_offset(self.cursor)
        elif forward:
            origin = bounds[1] if bounds else self.buffer.get_iter_at_offset(self.cursor)
        else:
            origin = bounds[0] if bounds else self.buffer.get_iter_at_offset(self.cursor)
        search = origin.forward_search if forward else origin.backward_search
        found = search(needle, flags, None)
        if found is None:  # wrap around
            start, end = self.buffer.get_bounds()
            found = (start.forward_search if forward else end.backward_search)(needle, flags, None)
        if found is None:
            self.search_entry.add_css_class("error")
            return False
        self.search_entry.remove_css_class("error")
        self.buffer.select_range(found[0], found[1])
        self.view.scroll_to_mark(self.buffer.get_insert(), 0.2, False, 0.0, 0.0)
        return True

    # --- closing ---------------------------------------------------------------------------------------

    def shutdown(self) -> None:
        self.state.close()


def _menu_label(text: str) -> str:
    """Menu labels treat "_" as a mnemonic marker: double it to show it."""
    return text.replace("_", "__")
