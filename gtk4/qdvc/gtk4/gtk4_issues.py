"""The inspector beside the text: every issue of the current tab, with filters
by group, suggestions to apply, Ignore and Add to Dictionary (the port of the
macOS edition's IssueListView)."""

from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import ui_prefs as U
from ..model import IssueCategory, IssueGroup
from ..textutil import excerpt
from .gtk4_widgets import button, clear, dot, escape, hbox, label, vbox

MAX_ROWS = 400


class IssueRow(Gtk.ListBoxRow):
    def __init__(self, issue, state, focused: bool):
        super().__init__()
        self.issue = issue
        self.state = state
        self.render(focused)

    def render(self, focused: bool) -> None:
        issue, state = self.issue, self.state
        group = issue.category.group
        body = vbox(spacing=6)
        body.add_css_class("issue-row")
        source = label(issue.source.display_name, "source-pill", "dim-label")
        body.append(hbox(dot(group), label(issue.category.display_name, "caption-heading", "dim-label", hexpand=True),
                         source, spacing=6))
        body.append(label(issue.message, wrap=True))
        if issue.suggestions:
            body.append(label(f"<s>{escape(excerpt(issue.original))}</s>", "issue-original", markup=True,
                              wrap=True, lines=2))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, column_spacing=4,
                               row_spacing=4, homogeneous=False)
            for s in issue.suggestions[:5 if focused else 2]:
                b = button("Remove" if s == "" else excerpt(s, 60), lambda s=s: state.apply(issue, s),
                           "suggestion", f"suggestion-{group.value}")
                flow.append(b)
            body.append(flow)
        else:
            body.append(label(f"<i>{escape(excerpt(issue.original))}</i>", "issue-original", markup=True,
                              wrap=True, lines=2))
        actions = hbox(button("Ignore", lambda: state.ignore(issue), "flat", "caption"), spacing=4)
        if issue.category is IssueCategory.SPELLING:
            actions.append(button("Add to Dictionary", lambda: state.add_to_dictionary(issue), "flat", "caption"))
        body.append(actions)
        self.set_child(body)


class IssueList(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, width_request=300)
        self.state = None
        self._rows: dict[str, IssueRow] = {}
        self._syncing = False

        self.chips = {}
        bar = hbox(spacing=6, margin_start=10, margin_end=10, margin_top=8, margin_bottom=8)
        for g in IssueGroup:
            count = label("0", "numeric")
            chip = Gtk.ToggleButton(child=hbox(dot(g), count, spacing=4), active=True)
            chip.add_css_class("flat")
            chip.add_css_class("group-chip")
            chip.connect("toggled", lambda b, g=g: self._toggle(g, b.get_active()))
            self.chips[g] = (chip, count)
            bar.append(chip)
        self.append(bar)
        self.append(Gtk.Separator())

        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.list.add_css_class("navigation-sidebar")
        self.list.connect("row-selected", self._selected)
        self.viewport = Gtk.Viewport(child=self.list)
        self.scroller = Gtk.ScrolledWindow(child=self.viewport, vexpand=True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.scroller, "list")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)

    def bind(self, state) -> None:
        self.state = state
        self.refresh()

    def _toggle(self, group, shown: bool) -> None:
        if self.state is not None and not self._syncing:
            self.state.set_group_hidden(group, not shown)

    def refresh(self) -> None:
        """Rebuilds the list (the issues changed)."""
        state = self.state
        self._syncing = True
        for g, (chip, count) in self.chips.items():
            n = state.count(g) if state else 0
            count.set_text(str(n))
            chip.set_active(state is None or g not in state.hidden_groups)
            chip.set_tooltip_text(f"{g.display_name}: {U.plural(n, 'issue')}, "
                                  + ("shown, click to hide" if chip.get_active() else "hidden, click to show"))
        self._syncing = False
        clear(self.list)
        self._rows = {}
        issues = state.visible_issues if state else []
        if not issues:
            self._show_empty()
            return
        self.stack.set_visible_child_name("list")
        for issue in issues[:MAX_ROWS]:
            row = IssueRow(issue, state, issue.id == state.focused_id)
            self._rows[issue.id] = row
            self.list.append(row)
        if len(issues) > MAX_ROWS:
            more = Gtk.ListBoxRow(selectable=False, activatable=False)
            more.set_child(label(f"And {len(issues) - MAX_ROWS} more: F8 moves through them all.", "dim-label",
                                 wrap=True, margin_top=8, margin_bottom=8, margin_start=10))
            self.list.append(more)
        self.sync_focus()

    def _show_empty(self) -> None:
        clear(self.empty)
        state = self.state
        hidden = bool(state and state.hidden_groups)
        kind = state.ai_state.kind if state else "idle"
        hint = {"finished": "The AI review found nothing more to improve.",
                "running": "The AI review is still running…"}.get(
            kind, "Quick checks run as you type. Press Ctrl+Shift+K for an in-depth AI review.")
        page = vbox(Gtk.Image(icon_name="object-select-symbolic", pixel_size=48, css_classes=["dim-label"]),
                    label("No issues in the visible categories" if hidden else "No issues found", "title-4",
                          xalign=0.5),
                    label(hint, "dim-label", wrap=True, xalign=0.5, justify=Gtk.Justification.CENTER),
                    spacing=10, valign=Gtk.Align.CENTER, vexpand=True, margin_start=24, margin_end=24)
        self.empty.append(page)
        self.stack.set_visible_child_name("empty")

    def sync_focus(self) -> None:
        """Selects and shows the focused issue's row, and gives it its full list of suggestions."""
        state = self.state
        if state is None:
            return
        self._syncing = True
        current = self.list.get_selected_row()
        row = self._rows.get(state.focused_id) if state.focused_id else None
        if current is not None and current is not row and isinstance(current, IssueRow):
            current.render(False)
        if row is None:
            self.list.unselect_all()
        elif row is not current:
            row.render(True)
            self.list.select_row(row)
            if hasattr(self.viewport, "scroll_to"):
                GLib.idle_add(lambda: (self.viewport.scroll_to(row, None), False)[1])
        self._syncing = False

    def _selected(self, _list, row) -> None:
        if self._syncing or row is None or self.state is None or not isinstance(row, IssueRow):
            return
        if row.issue.id != self.state.focused_id:
            self.state.focus(row.issue)
