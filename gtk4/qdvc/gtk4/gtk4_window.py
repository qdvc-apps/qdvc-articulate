"""The main window: documents in tabs (Adw.TabView), the issue inspector
beside them (F9), the status bar, the isolation banner, every win.* action,
and opening, importing, saving, drafts and the restored session."""

from __future__ import annotations

import os

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from .. import APP_NAME, isolation
from .. import ui_prefs as U
from ..documents import DocumentError, IMPORT_SUFFIXES, import_document
from ..model import Audience, Dialect, Formality, WritingDomain
from ..session import Document, SessionStore
from .gtk4_editor import EditorPage
from .gtk4_issues import IssueList
from .gtk4_preferences import PreferencesDialog
from .gtk4_statusbar import StatusBar
from .gtk4_widgets import _load, alert, choose_files, choose_save_path, import_filters, text_filters

DRAFT_DELAY_MS = 2000
GOALS = (("dialect", "English", Dialect), ("formality", "Formality", Formality),
         ("audience", "Audience", Audience), ("domain", "Domain", WritingDomain))


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=APP_NAME)
        self.app = app
        self.prefs, self.models, self.spell = app.prefs, app.models, app.spell
        self.store = SessionStore()
        self.isolation = isolation.report()
        self._draft_timers: dict[int, int] = {}
        self._refresh_id = 0
        w = self.prefs.window
        self.set_default_size(w["width"], w["height"])
        if w["maximized"]:
            self.maximize()

        self.font_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.font_css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._apply_font()
        self._build()
        self._install_actions()
        self.prefs.connect(self._on_prefs)
        self.models.connect(lambda _s: self._update_chrome())
        self.connect("close-request", self._on_close_request)

    # --- layout ---------------------------------------------------------------------------------

    def _build(self) -> None:
        self.tabs = Adw.TabView()
        self.tabs.connect("close-page", self._on_close_page)
        self.tabs.connect("notify::selected-page", lambda *_: self._on_tab_switched())
        tab_bar = Adw.TabBar(view=self.tabs, autohide=True)

        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=APP_NAME)
        header.set_title_widget(self.title)
        self.recent_menu = Gio.Menu()
        open_button = Adw.SplitButton(label="Open", menu_model=self.recent_menu, action_name="win.open",
                                      tooltip_text="Open a document (Ctrl+O)", dropdown_tooltip="Recent documents")
        header.pack_start(open_button)
        header.pack_start(Gtk.Button(icon_name="tab-new-symbolic", action_name="win.new-tab",
                                     tooltip_text="New document (Ctrl+N)"))
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=self._main_menu(),
                                       primary=True, tooltip_text="Main menu"))
        self.inspector_button = Gtk.ToggleButton(icon_name="sidebar-show-right-symbolic",
                                                 tooltip_text="Show or hide the issues (F9)")
        header.pack_end(self.inspector_button)
        self.ai_button = Gtk.Button(label="Check with AI", action_name="win.ai-check")
        self.ai_button.add_css_class("suggested-action")
        header.pack_end(self.ai_button)
        self.goals_button = Gtk.MenuButton(menu_model=self._goals_menu(),
                                           tooltip_text="Variety of English and writing goals")
        header.pack_end(self.goals_button)

        self.banner = Adw.Banner(title="Network isolation is not enforced: this copy is not running as the Flatpak.",
                                 button_label="Details", revealed=not self.isolation.is_isolated)
        self.banner.connect("button-clicked", lambda *_: self.show_preferences("privacy"))

        self.issue_list = IssueList()
        self.split = Adw.OverlaySplitView(content=self.tabs, sidebar=self.issue_list,
                                          sidebar_position=Gtk.PackType.END, min_sidebar_width=280,
                                          max_sidebar_width=520, show_sidebar=self.prefs.window["inspector"])
        self.split.bind_property("show-sidebar", self.inspector_button, "active",
                                 GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.split.connect("notify::show-sidebar",
                           lambda *_: self.prefs.set_window(inspector=self.split.get_show_sidebar()))

        self.statusbar = StatusBar(on_stop=lambda: self._page() and self._page().state.cancel_ai(),
                                   on_choose_model=lambda: self.show_preferences("model"),
                                   on_privacy=lambda: self.show_preferences("privacy"))

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.add_top_bar(tab_bar)
        view.add_top_bar(self.banner)
        view.set_content(self.split)
        view.add_bottom_bar(self.statusbar)
        self.toasts = Adw.ToastOverlay(child=view)
        self.set_content(self.toasts)

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)
        self._fill_recent()

    def _main_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        for section in (
            [("New Document", "win.new-tab"), ("Open…", "win.open"), ("Import Word, RTF or ODT…", "win.import")],
            [("Save", "win.save"), ("Save As…", "win.save-as")],
            [("Find…", "win.find"), ("Restore Ignored Issues", "win.restore-ignored")],
            [("Preferences", "app.preferences"), ("Keyboard Shortcuts", "app.shortcuts"),
             ("About QDVC Articulate", "app.about")],
        ):
            s = Gio.Menu()
            for title, action in section:
                s.append(title, action)
            menu.append_section(None, s)
        return menu

    def _goals_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        for name, title, enum in GOALS:
            sub = Gio.Menu()
            for value in enum:
                item = Gio.MenuItem.new(value.display_name, None)
                item.set_action_and_target_value(f"win.{name}", GLib.Variant.new_string(value.value))
                sub.append_item(item)
            menu.append_submenu(title, sub)
        more = Gio.Menu()
        more.append("Rules and Goals…", "app.preferences")
        menu.append_section(None, more)
        return menu

    def _fill_recent(self) -> None:
        self.recent_menu.remove_all()
        items = Gio.Menu()
        for path in self.prefs.recent_files:
            item = Gio.MenuItem.new(os.path.basename(path).replace("_", "__"), None)
            item.set_action_and_target_value("win.open-recent", GLib.Variant.new_string(path))
            items.append_item(item)
        if not self.prefs.recent_files:
            items.append("No recent documents", "win.none")
        self.recent_menu.append_section(None, items)
        if self.prefs.recent_files:
            clear = Gio.Menu()
            clear.append("Clear Recent Documents", "win.clear-recent")
            self.recent_menu.append_section(None, clear)

    # --- actions --------------------------------------------------------------------------------

    def _install_actions(self) -> None:
        simple = {
            "new-tab": lambda: self.new_tab(), "open": self.open_dialog, "import": self.import_dialog,
            "save": lambda: self.save(), "save-as": lambda: self.save_as(), "close-tab": self.close_tab,
            "find": lambda: self._with_page(lambda p: p.open_find()), "ai-check": self.toggle_ai,
            "next-issue": lambda: self._with_page(lambda p: p.state.select_next(p.cursor)),
            "previous-issue": lambda: self._with_page(lambda p: p.state.select_previous(p.cursor)),
            "accept-suggestion": lambda: self._with_page(lambda p: p.state.apply_focused()),
            "ignore-issue": lambda: self._with_page(lambda p: p.state.ignore_focused()),
            "restore-ignored": lambda: self._with_page(lambda p: p.state.clear_ignored()),
            "toggle-inspector": lambda: self.split.set_show_sidebar(not self.split.get_show_sidebar()),
            "clear-recent": self._clear_recent,
        }
        for name, fn in simple.items():
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda _a, _p, fn=fn: fn())
            self.add_action(a)
        recent = Gio.SimpleAction.new("open-recent", GLib.VariantType.new("s"))
        recent.connect("activate", lambda _a, p: self.open_path(p.get_string()))
        self.add_action(recent)
        self.goal_actions = {}
        for name, _title, enum in GOALS:
            a = Gio.SimpleAction.new_stateful(name, GLib.VariantType.new("s"),
                                              GLib.Variant.new_string(self._goal_value(name)))
            a.connect("change-state", lambda act, value, name=name, enum=enum: self._set_goal(name, enum, value))
            self.add_action(a)
            self.goal_actions[name] = a
        self._update_goals()

    def _goal_value(self, name: str) -> str:
        c = self.prefs.check
        return {"dialect": c.dialect, "formality": c.goals.formality, "audience": c.goals.audience,
                "domain": c.goals.domain}[name].value

    def _set_goal(self, name: str, enum, value: GLib.Variant) -> None:
        v = enum(value.get_string())
        if name == "dialect":
            self.prefs.set_dialect(v)
        else:
            self.prefs.set_goals(**{name: v})

    def _update_goals(self) -> None:
        for name, action in self.goal_actions.items():
            action.set_state(GLib.Variant.new_string(self._goal_value(name)))
        self.goals_button.set_label(self.prefs.check.dialect.display_name)

    def _with_page(self, fn) -> None:
        page = self._page()
        if page is not None:
            fn(page)

    # --- tabs -------------------------------------------------------------------------------------

    def _page(self) -> EditorPage | None:
        tab = self.tabs.get_selected_page()
        return tab.get_child() if tab is not None else None

    def pages(self) -> list[EditorPage]:
        return [self.tabs.get_nth_page(i).get_child() for i in range(self.tabs.get_n_pages())]

    def new_tab(self, document: Document | None = None, text: str = "", cursor: int = 0,
                select: bool = True) -> EditorPage:
        page = EditorPage(self.prefs, self.models, self.spell, document, text)
        if cursor:
            page.buffer.place_cursor(page.buffer.get_iter_at_offset(min(cursor, len(text))))
        tab = self.tabs.append(page)
        page.connect("changed", lambda p: self._on_page_changed(p))
        page.state.connect(lambda what, p=page: self._on_state(p, what))
        self._update_tab(page)
        if select:
            self.tabs.set_selected_page(tab)
            page.view.grab_focus()
        return page

    def _tab_of(self, page: EditorPage):
        """The tab of a page, or None once it is closed."""
        for i in range(self.tabs.get_n_pages()):
            tab = self.tabs.get_nth_page(i)
            if tab.get_child() is page:
                return tab
        return None

    def _update_tab(self, page: EditorPage) -> None:
        tab = self._tab_of(page)
        if tab is None:
            return
        tab.set_title(("• " if page.modified else "") + page.title)
        tab.set_tooltip(GLib.markup_escape_text(page.document.path or page.title))
        if page is self._page():
            self.title.set_title(("• " if page.modified else "") + page.title)
            self.title.set_subtitle(U.display_path(page.document.path))

    def _on_page_changed(self, page: EditorPage) -> None:
        self._update_tab(page)
        key = id(page)
        if key in self._draft_timers:
            GLib.source_remove(self._draft_timers.pop(key))

        def write():
            self._draft_timers.pop(key, None)
            if self._tab_of(page) is not None:
                self.store.write_draft(page.document, page.state.text)
            return False
        self._draft_timers[key] = GLib.timeout_add(DRAFT_DELAY_MS, write)

    def _on_tab_switched(self) -> None:
        page = self._page()
        self.issue_list.bind(page.state if page else None)
        if page is not None:
            self._update_tab(page)
        self._update_chrome()

    def _on_state(self, page: EditorPage, what: str) -> None:
        if page is not self._page():
            return
        if what == "focus":
            self.issue_list.sync_focus()
        elif what == "issues":
            self._schedule_list_refresh()
        if what in ("issues", "stats", "ai"):
            self._update_chrome()
        if what == "ai" and not page.state.issues:
            self._schedule_list_refresh()

    def _schedule_list_refresh(self) -> None:
        """Rebuilding the list on every keystroke would be wasteful: coalesce."""
        if self._refresh_id:
            return

        def run():
            self._refresh_id = 0
            self.issue_list.refresh()
            return False
        self._refresh_id = GLib.timeout_add(120, run)

    def _update_chrome(self) -> None:
        page = self._page()
        state = page.state if page else None
        self.statusbar.update(state, self.models, self.isolation.is_isolated)
        running = bool(state and state.ai_state.running)
        self.ai_button.set_label("Stop" if running else "Check with AI")
        (self.ai_button.remove_css_class if running else self.ai_button.add_css_class)("suggested-action")
        self.ai_button.set_tooltip_text("Stop the AI review (Ctrl+Shift+K)" if running else
                                        ("Review the document with the local AI model (Ctrl+Shift+K)"
                                         if self.models.is_ready else self.models.not_ready_message))
        if state is not None and state.ai_state.kind == "failed" and state.ai_state.message:
            pass  # shown in the status bar's tooltip and by the toast in toggle_ai

    # --- opening, importing, saving -----------------------------------------------------------------

    def open_dialog(self) -> None:
        choose_files(self, "Open", text_filters(), lambda paths: [self.open_path(p) for p in paths])

    def import_dialog(self) -> None:
        choose_files(self, "Import Word, RTF or ODT", import_filters(),
                     lambda paths: [self.import_path(p) for p in paths])

    def open_path(self, path: str) -> None:
        for page in self.pages():
            if page.document.path and os.path.realpath(page.document.path) == os.path.realpath(path):
                self.tabs.set_selected_page(self._tab_of(page))
                return
        if path.lower().endswith(IMPORT_SUFFIXES):
            self.import_path(path)
            return
        try:
            document, text = Document.open(path)
        except OSError as e:
            self.prefs.remove_recent(path)
            alert(self, "Could Not Open the Document", f"{os.path.basename(path)}: {e.strerror or e}")
            return
        current = self._page()
        if current is not None and not current.document.path and not current.modified and not current.state.text:
            current.document = document
            current.load_text(text)
            self._update_tab(current)
        else:
            self.new_tab(document, text)
        self.prefs.add_recent(path)

    def import_path(self, path: str) -> None:
        try:
            text = import_document(path)
        except DocumentError as e:
            alert(self, "Import Failed", str(e))
            return
        stem = os.path.splitext(os.path.basename(path))[0]
        self.new_tab(Document(name=f"{stem}.txt"), text)
        self.toast(f"Imported {os.path.basename(path)} as a new document")

    def save(self, page: EditorPage | None = None, then=None) -> None:
        page = page or self._page()
        if page is None:
            return
        if not page.document.path:
            self.save_as(page, then)
            return
        self._write(page, page.document.path, then)

    def save_as(self, page: EditorPage | None = None, then=None) -> None:
        page = page or self._page()
        if page is not None:
            choose_save_path(self, "Save As", page.document.suggested_name, lambda p: self._write(page, p, then))

    def _write(self, page: EditorPage, path: str, then=None) -> None:
        try:
            page.document.save(page.state.text, path)
        except OSError as e:
            alert(self, "Could Not Save the Document", f"{os.path.basename(path)}: {e.strerror or e}")
            return
        page.document.name = None
        self.store.discard_draft(page.document)
        self.prefs.add_recent(path)
        self._update_tab(page)
        if then is not None:
            then()

    def _on_drop(self, _target, value, _x, _y) -> bool:
        files = value.get_files() if hasattr(value, "get_files") else []
        for f in files:
            if f.get_path():
                self.open_path(f.get_path())
        return True

    def _clear_recent(self) -> None:
        for p in list(self.prefs.recent_files):
            self.prefs.remove_recent(p)

    # --- closing -----------------------------------------------------------------------------------

    def close_tab(self) -> None:
        tab = self.tabs.get_selected_page()
        if tab is not None:
            self.tabs.close_page(tab)

    def _on_close_page(self, view, tab) -> bool:
        page: EditorPage = tab.get_child()
        if not page.modified or (not page.document.path and not page.state.text.strip()):
            self._finish_close(tab, page)
            return True

        def respond(rid: str) -> None:
            if rid == "save":
                # Keep the tab for now; once saved (and so unmodified), closing it again closes it at once.
                view.close_page_finish(tab, False)
                self.save(page, then=lambda: self.tabs.close_page(tab) if self._tab_of(page) else None)
            elif rid == "discard":
                self.store.discard_draft(page.document)
                self._finish_close(tab, page)
            else:
                view.close_page_finish(tab, False)
        alert(self, "Save Changes?", f"“{page.title}” has unsaved changes. Changes which are not saved will be "
                                     "permanently lost.",
              [("cancel", "Cancel", None), ("discard", "Discard", "destructive"), ("save", "Save", "suggested")],
              respond, default="save", close="cancel")
        return True

    def _finish_close(self, tab, page: EditorPage) -> None:
        if self._tab_of(page) is None:
            return
        page.shutdown()
        self.store.discard_draft(page.document)
        self.tabs.close_page_finish(tab, True)
        if self.tabs.get_n_pages() == 0:
            self.new_tab()

    def save_session(self) -> None:
        tabs = [(p.document, p.state.text, p.cursor) for p in self.pages()]
        selected = self.tabs.get_selected_page()
        self.store.save(tabs, self.tabs.get_page_position(selected) if selected else 0)

    def restore_session(self) -> None:
        restored, active = self.store.load()
        for r in restored:
            self.new_tab(r.document, r.text, r.cursor, select=False)
        if self.tabs.get_n_pages() == 0:
            self.new_tab()
        else:
            self.tabs.set_selected_page(self.tabs.get_nth_page(min(active, self.tabs.get_n_pages() - 1)))
        self._on_tab_switched()

    def _on_close_request(self, *_):
        for source in self._draft_timers.values():
            GLib.source_remove(source)
        self._draft_timers.clear()
        self.save_session()
        if not self.is_maximized():
            self.prefs.set_window(width=self.get_width(), height=self.get_height(), maximized=False)
        else:
            self.prefs.set_window(maximized=True)
        for page in self.pages():
            page.shutdown()
        return False

    # --- the AI review and preferences ----------------------------------------------------------------

    def toggle_ai(self) -> None:
        page = self._page()
        if page is None:
            return
        if page.state.ai_state.running:
            page.state.cancel_ai()
        elif not self.models.is_ready:
            toast = Adw.Toast(title=GLib.markup_escape_text(self.models.not_ready_message), timeout=6)
            if self.models.available:
                toast.set_button_label("Set Up")
                toast.connect("button-clicked", lambda *_: self.show_preferences("model"))
            self.toasts.add_toast(toast)
        else:
            page.state.run_ai_check()

    def show_preferences(self, page: str | None = None) -> None:
        PreferencesDialog(self, page).present(self)

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text)))

    def _apply_font(self) -> None:
        _load(self.font_css, f"textview.articulate-editor {{ font-size: {self.prefs.editor_font_size}pt; }}")

    def _on_prefs(self, what: str) -> None:
        if what in ("check", "checking"):
            self._update_goals()
            for page in self.pages():
                page.state.settings_changed()
        elif what == "editor":
            self._apply_font()
            for page in self.pages():
                page.apply_editor_preferences()
        elif what == "recent":
            self._fill_recent()

