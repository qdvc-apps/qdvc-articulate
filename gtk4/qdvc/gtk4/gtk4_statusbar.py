"""The status bar along the foot of the window: words and reading time (with
the full statistics in a popover), readability, the AI engine's state, the
issue count and the isolation shield (the port of the macOS StatusBar)."""

from __future__ import annotations

from gi.repository import Gtk

from .. import ui_prefs as U
from ..engine import ModelState
from ..text import format_duration
from .gtk4_widgets import button, hbox, label, tint


class StatusBar(Gtk.Box):
    def __init__(self, on_stop, on_choose_model, on_privacy):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.add_css_class("statusbar")
        self.words = label("", "numeric")
        self.stats_grid = Gtk.Grid(column_spacing=18, row_spacing=6, margin_top=12, margin_bottom=12,
                                   margin_start=14, margin_end=14)
        self.stats_button = Gtk.MenuButton(child=self.words, popover=Gtk.Popover(child=self.stats_grid),
                                           tooltip_text="Show document statistics")
        self.stats_button.add_css_class("flat")
        self.readability = label("", "dim-label")
        self.readability.set_tooltip_text("Flesch Reading Ease: higher is easier. 60–70 is plain English.")

        self.spinner = Gtk.Spinner()
        self.progress = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=70)
        self.ai_label = label("", "numeric")
        self.ai_stop = button("", on_stop, "flat", icon_name="media-playback-stop-symbolic",
                              tooltip="Stop the AI review (Ctrl+Shift+K)")
        self.ai_choose = button("Choose an AI model…", on_choose_model, "flat")
        self.issues = label("", "numeric")
        self.shield = Gtk.Button(icon_name="security-high-symbolic")
        self.shield.add_css_class("flat")
        self.shield.connect("clicked", lambda *_: on_privacy())

        self.append(self.stats_button)
        self.append(self.readability)
        self.append(Gtk.Box(hexpand=True))
        self.append(hbox(self.spinner, self.progress, self.ai_label, self.ai_stop, self.ai_choose, spacing=6))
        self.append(self.issues)
        self.append(self.shield)

    def update(self, state, models, isolated: bool) -> None:
        stats = state.stats if state else None
        if stats is None:
            self.words.set_text("")
            self.readability.set_text("")
        else:
            self.words.set_text(f"{U.plural(stats.words, 'word')} · {format_duration(stats.reading_time_seconds)} read")
            score = stats.flesch_reading_ease
            self.readability.set_text(f"Readability {round(score)} · {stats.readability_label}"
                                      if score is not None else "")
            self._fill_statistics(stats)
        n = len(state.issues) if state else 0
        self.issues.set_text("No issues" if n == 0 else U.plural(n, "issue"))
        self.shield.set_icon_name("security-high-symbolic" if isolated else "dialog-warning-symbolic")
        tint(self.shield, "green" if isolated else "orange")
        self.shield.set_tooltip_text(
            "Offline: the Flatpak sandbox gives this app no network access at all." if isolated else
            "Network isolation is not enforced for this copy (it is not running as the Flatpak). Click for details.")
        self._update_ai(state, models)

    def _update_ai(self, state, models) -> None:
        for w in (self.spinner, self.progress, self.ai_stop, self.ai_choose):
            w.set_visible(False)
        self.spinner.stop()
        tint(self.ai_label, None)
        status = models.status
        s = status.state
        tooltip = models.not_ready_message
        if s is ModelState.NOT_COMPILED_IN:
            text = "AI unavailable"
        elif s is ModelState.NO_MODEL:
            text = ""
            self.ai_choose.set_visible(True)
        elif s is ModelState.LOADING:
            text = f"Loading {status.detail}…"
            self.spinner.set_visible(True)
            self.spinner.start()
        elif s is ModelState.FAILED:
            text = "AI model error"
            tint(self.ai_label, "orange")
        else:
            name = status.info.file_name if status.info else ""
            ai = state.ai_state if state else None
            tooltip = f"Model: {name}"
            if ai is not None and ai.running:
                if ai.total:
                    self.progress.set_fraction(ai.done / ai.total)
                    self.progress.set_visible(True)
                    text = f"AI {ai.done}/{ai.total}"
                else:
                    self.spinner.set_visible(True)
                    self.spinner.start()
                    text = "AI starting…"
                self.ai_stop.set_visible(True)
            elif ai is not None and ai.kind == "finished":
                text = f"AI: {U.plural(ai.found, 'suggestion')}"
            elif ai is not None and ai.kind == "failed":
                text = "AI error"
                tooltip = ai.message
                tint(self.ai_label, "orange")
            else:
                text = "AI ready"
                tooltip = f"Model: {name}. Press Ctrl+Shift+K to review the document."
        self.ai_label.set_text(text)
        self.ai_label.set_visible(bool(text))
        self.ai_label.set_tooltip_text(tooltip or None)

    def _fill_statistics(self, st) -> None:
        g = self.stats_grid
        while g.get_first_child() is not None:
            g.remove(g.get_first_child())
        rows = [
            ("Words", f"{st.words}"), ("Characters", f"{st.characters}"),
            ("Characters (no spaces)", f"{st.characters_excluding_spaces}"), ("Sentences", f"{st.sentences}"),
            ("Paragraphs", f"{st.paragraphs}"), None,
            ("Average sentence", f"{st.average_words_per_sentence:.1f} words"),
            ("Longest sentence", f"{st.longest_sentence_words} words"),
            ("Unique words", f"{st.unique_words} ({round(st.lexical_diversity * 100)}%)"), None,
            ("Reading time", format_duration(st.reading_time_seconds)),
            ("Speaking time", format_duration(st.speaking_time_seconds)),
        ]
        if st.flesch_reading_ease is not None and st.flesch_kincaid_grade is not None:
            rows += [None, ("Flesch Reading Ease", f"{st.flesch_reading_ease:.0f} ({st.readability_label})"),
                     ("Flesch–Kincaid grade", f"{st.flesch_kincaid_grade:.1f}")]
        for r, row in enumerate(rows):
            if row is None:
                g.attach(Gtk.Separator(margin_top=2, margin_bottom=2), 0, r, 2, 1)
                continue
            g.attach(label(row[0], "dim-label"), 0, r, 1, 1)
            g.attach(label(row[1], "numeric"), 1, r, 1, 1)
