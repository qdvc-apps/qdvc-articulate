"""Preferences (an Adw.PreferencesDialog, applied as you change it) with the
macOS edition's five tabs: General, Rules, AI Model, Dictionary and Privacy;
and the Keyboard Shortcuts list."""

from __future__ import annotations

import os

from gi.repository import Adw, Gtk

from .. import isolation, llm
from .. import ui_prefs as U
from ..ai import PromptFormat
from ..engine import ModelState
from ..model import Audience, Dialect, Formality, IssueGroup, WritingDomain
from ..preferences import CHUNK_LENGTHS, CONTEXT_LENGTHS, OUTPUT_TOKENS
from ..rules import RULE_INFOS
from .gtk4_widgets import button, choose_files, clear, escape, label, model_filters, tint

RECOMMENDED = ("Any instruction-tuned GGUF works. Good choices for proofreading:\n"
               "• Gemma 4 E4B Instruct, Q4_K_M (about 5 GB): the best balance of quality and speed\n"
               "• Gemma 4 E2B Instruct, Q4_K_M: faster, for computers with 8 GB of memory\n"
               "• Qwen3 4B or 8B Instruct, Q4_K_M: strong grammar, ChatML format\n"
               "Download the file yourself, on any device, and copy it here. QDVC Articulate never downloads "
               "anything. The engine runs on the CPU.")


def combo(title: str, items: list[str], selected: int, on_change, subtitle: str = "") -> Adw.ComboRow:
    row = Adw.ComboRow(title=title, model=Gtk.StringList.new(items), subtitle=subtitle)
    row.set_selected(max(0, selected))
    row.connect("notify::selected", lambda r, _p: on_change(r.get_selected()))
    return row


def switch(title: str, active: bool, on_change, subtitle: str = "") -> Adw.SwitchRow:
    row = Adw.SwitchRow(title=title, subtitle=subtitle, active=active)
    row.connect("notify::active", lambda r, _p: on_change(r.get_active()))
    return row


def spin(title: str, value: float, lo: float, hi: float, step: float, on_change, digits: int = 0,
         subtitle: str = "") -> Adw.SpinRow:
    row = Adw.SpinRow.new_with_range(lo, hi, step)
    row.set_title(title)
    row.set_subtitle(subtitle)
    row.set_digits(digits)
    row.set_value(value)
    row.connect("notify::value", lambda r, _p: on_change(r.get_value()))
    return row


def info_row(title: str, value: str) -> Adw.ActionRow:
    row = Adw.ActionRow(title=escape(title))
    row.add_suffix(label(value, "dim-label", wrap=True, xalign=1.0, selectable=True))
    return row


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, window, page: str | None = None):
        super().__init__(title="Preferences", search_enabled=True)
        self.window = window
        self.prefs = window.prefs
        self.models = window.models
        self.add(self._general())
        self.add(self._rules())
        self.add(self._model())
        self.add(self._dictionary())
        self.add(self._privacy())
        self._model_listener = lambda _s: self._fill_model_status()
        self.models.connect(self._model_listener)
        self.connect("closed", lambda *_: self.models.disconnect(self._model_listener))
        if page:
            self.set_visible_page_name(page)

    # --- General -----------------------------------------------------------------------------

    def _general(self) -> Adw.PreferencesPage:
        p, c = self.prefs, self.prefs.check
        page = Adw.PreferencesPage(title="General", icon_name="preferences-system-symbolic", name="general")
        goals = Adw.PreferencesGroup(title="Language and Goals")
        dialects, formalities = list(Dialect), list(Formality)
        audiences, domains = list(Audience), list(WritingDomain)
        goals.add(combo("English", [d.display_name for d in dialects], dialects.index(c.dialect),
                        lambda i: p.set_dialect(dialects[i])))
        goals.add(combo("Formality", [f.display_name for f in formalities], formalities.index(c.goals.formality),
                        lambda i: p.set_goals(formality=formalities[i])))
        goals.add(combo("Audience", [a.display_name for a in audiences], audiences.index(c.goals.audience),
                        lambda i: p.set_goals(audience=audiences[i])))
        goals.add(combo("Domain", [d.display_name for d in domains], domains.index(c.goals.domain),
                        lambda i: p.set_goals(domain=domains[i])))
        goals.add(spin("Flag Sentences Longer Than", c.long_sentence_word_limit, 15, 80, 5,
                       lambda v: p.set_check(_with(p.check, long_sentence_word_limit=int(v))), subtitle="Words"))
        page.add(goals)

        checking = Adw.PreferencesGroup(
            title="Checking",
            description="Spelling uses Enchant with the Hunspell dictionaries of the GNOME runtime, inside the "
                        "app's own process. The rules and the AI review run there too.")
        spell = self.window.spell
        tag = spell.tag_for(c.dialect) if spell.available else None
        detail = (f"Dictionary: {tag}" if tag else
                  "No dictionary for this variety of English is installed" if spell.available else
                  "Enchant is not available")
        checking.add(switch("Spelling", p.spelling, lambda v: p.set_option("spelling", v), subtitle=detail))
        checking.add(switch("Run the AI Review After a Pause in Typing", p.auto_ai,
                            lambda v: p.set_option("auto_ai", v)))
        page.add(checking)

        editor = Adw.PreferencesGroup(title="Editor")
        editor.add(spin("Font Size", p.editor_font_size, 8, 32, 1, lambda v: p.set_option("editor_font_size", int(v)),
                        subtitle="Points"))
        editor.add(switch("Monospaced Font", p.monospace, lambda v: p.set_option("monospace", v)))
        page.add(editor)
        return page

    # --- Rules ---------------------------------------------------------------------------------

    def _rules(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Rules", icon_name="view-list-symbolic", name="rules")
        self._rule_rows = []
        for group in IssueGroup:
            infos = [i for i in RULE_INFOS if i.category.group is group]
            if not infos:
                continue
            g = Adw.PreferencesGroup(title=group.display_name)
            for info in infos:
                row = switch(escape(info.name), self.prefs.check.is_enabled(info),
                             lambda v, info=info: self.prefs.set_rule(info, v), subtitle=escape(info.summary))
                self._rule_rows.append((info, row))
                g.add(row)
            page.add(g)
        reset = Adw.PreferencesGroup()
        reset.add(_button_row("Restore Defaults", self._reset_rules))
        page.add(reset)
        return page

    def _reset_rules(self) -> None:
        self.prefs.reset_rules()
        for info, row in self._rule_rows:
            row.set_active(info.default_enabled)

    # --- AI model --------------------------------------------------------------------------------

    def _model(self) -> Adw.PreferencesPage:
        p, l = self.prefs, self.prefs.llama  # noqa: E741
        page = Adw.PreferencesPage(title="AI Model", icon_name="applications-science-symbolic", name="model")
        self.model_group = Adw.PreferencesGroup(title="Model")
        self.model_rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.model_rows.add_css_class("boxed-list")
        self.model_group.add(self.model_rows)
        self.model_buttons = Gtk.Box(spacing=6, margin_top=12, homogeneous=False)
        self.model_group.add(self.model_buttons)
        page.add(self.model_group)
        self._fill_model_status()

        loading = Adw.PreferencesGroup(title="Loading", description="Changes here take effect after Reload.")
        ctx = CONTEXT_LENGTHS
        loading.add(combo("Context Length", [f"{n} tokens" for n in ctx],
                          ctx.index(l.context_length) if l.context_length in ctx else 2,
                          lambda i: p.set_llama(context_length=ctx[i])))
        loading.add(spin("CPU Threads", l.threads, 0, 64, 1, lambda v: p.set_llama(threads=int(v)),
                         subtitle="0 is automatic: the number of processors less two"))
        loading.add(switch("Load the Model When the App Starts", l.load_at_launch,
                           lambda v: p.set_llama(load_at_launch=v)))
        page.add(loading)

        review = Adw.PreferencesGroup(title="Review")
        formats = list(PromptFormat)
        review.add(combo("Prompt Format", [f.display_name for f in formats], formats.index(l.prompt_format),
                         lambda i: p.set_llama(prompt_format=formats[i])))
        review.add(combo("Maximum Output per Paragraph", [f"{n} tokens" for n in OUTPUT_TOKENS],
                         OUTPUT_TOKENS.index(l.max_output_tokens) if l.max_output_tokens in OUTPUT_TOKENS else 2,
                         lambda i: p.set_llama(max_output_tokens=OUTPUT_TOKENS[i])))
        review.add(combo("Paragraph Chunk Size", [f"{n} characters" for n in CHUNK_LENGTHS],
                         CHUNK_LENGTHS.index(l.chunk_length) if l.chunk_length in CHUNK_LENGTHS else 2,
                         lambda i: p.set_llama(chunk_length=CHUNK_LENGTHS[i])))
        review.add(spin("Temperature", l.temperature, 0.0, 1.0, 0.05, lambda v: p.set_llama(temperature=round(v, 2)),
                        digits=2, subtitle="0 always gives the most likely answer"))
        review.add(switch("Reuse the Instructions Between Paragraphs", l.reuse_prompt_cache,
                          lambda v: p.set_llama(reuse_prompt_cache=v), subtitle="Faster: they are processed once"))
        review.add(_button_row("Clear Cached AI Results", self._clear_cache))
        page.add(review)

        rec = Adw.PreferencesGroup(title="Recommended Models")
        rec.add(label(RECOMMENDED, "dim-label", wrap=True))
        page.add(rec)
        return page

    def _fill_model_status(self) -> None:
        clear(self.model_rows)
        clear(self.model_buttons)
        m, status = self.models, self.models.status
        s = status.state
        if s is ModelState.NOT_COMPILED_IN:
            title, tint_name = m.not_ready_message, "orange"
        elif s is ModelState.NO_MODEL:
            title, tint_name = "No model selected", None
        elif s is ModelState.LOADING:
            title, tint_name = f"Loading {status.detail}…", None
        elif s is ModelState.READY:
            title, tint_name = "Ready", "green"
        else:
            title, tint_name = status.detail, "orange"
        state_row = Adw.ActionRow(title="Status")
        state_row.add_suffix(tint(label(title, wrap=True, xalign=1.0), tint_name))
        self.model_rows.append(state_row)
        if self.prefs.model_path:
            self.model_rows.append(info_row("File", os.path.basename(self.prefs.model_path)))
        info = m.info
        if info is not None:
            self.model_rows.append(info_row("Model", info.description))
            self.model_rows.append(info_row("Size", U.file_size(info.size_bytes)))
            self.model_rows.append(info_row("Parameters", f"{info.parameter_count / 1e9:.2f} billion"))
            self.model_rows.append(info_row("Context", f"{info.context_length} tokens (trained: "
                                                       f"{info.trained_context_length})"))
            if m.resolved_format is not None:
                self.model_rows.append(info_row("Prompt Format", m.resolved_format.display_name))
        if m.available:
            self.model_rows.append(info_row("Engine", llm.system_info().split("|")[0].strip() or "llama.cpp (CPU)"))
        choose = button("Choose GGUF File…", self._choose, "suggested-action")
        choose.set_sensitive(m.available)
        reload_ = button("Reload", m.load)
        reload_.set_sensitive(m.available and bool(self.prefs.model_path))
        unload = button("Unload", m.unload)
        unload.set_sensitive(m.is_ready)
        forget = button("Forget Model", m.forget, "destructive-action")
        forget.set_sensitive(bool(self.prefs.model_path))
        for b in (choose, reload_, unload, Gtk.Box(hexpand=True), forget):
            self.model_buttons.append(b)

    def _choose(self) -> None:
        choose_files(self.window, "Choose a GGUF Model", model_filters(),
                     lambda paths: self.models.set_model(paths[0]), multiple=False)

    def _clear_cache(self) -> None:
        self.models.clear_cache()
        self.add_toast(Adw.Toast(title="Cached AI results cleared"))

    # --- Dictionary -----------------------------------------------------------------------------------

    def _dictionary(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Dictionary", icon_name="accessories-dictionary-symbolic",
                                   name="dictionary")
        add = Adw.PreferencesGroup(description="Words in your personal dictionary are never flagged as misspelled.")
        entry = Adw.EntryRow(title="Add a Word", show_apply_button=True)
        entry.connect("apply", lambda e: (self.prefs.add_to_dictionary(e.get_text()), e.set_text(""),
                                          self._fill_words()))
        add.add(entry)
        page.add(add)
        self.words_group = Adw.PreferencesGroup(title="Words")
        self.words_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.words_list.add_css_class("boxed-list")
        self.words_group.add(self.words_list)
        page.add(self.words_group)
        self._fill_words()
        return page

    def _fill_words(self) -> None:
        clear(self.words_list)
        words = self.prefs.check.personal_dictionary
        if not words:
            self.words_list.append(Adw.ActionRow(title="No words yet", sensitive=False))
        for w in words:
            row = Adw.ActionRow(title=escape(w))
            row.add_suffix(button("", lambda w=w: (self.prefs.remove_from_dictionary(w), self._fill_words()),
                                  "flat", icon_name="user-trash-symbolic", tooltip="Remove",
                                  valign=Gtk.Align.CENTER))
            self.words_list.append(row)

    # --- Privacy ----------------------------------------------------------------------------------------

    def _privacy(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(title="Privacy", icon_name="security-high-symbolic", name="privacy")
        self.iso_group = Adw.PreferencesGroup(title="Network Isolation")
        self.iso_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.iso_list.add_css_class("boxed-list")
        self.iso_group.add(self.iso_list)
        check = button("Check Again", self._fill_isolation, margin_top=12, halign=Gtk.Align.START)
        self.iso_group.add(check)
        page.add(self.iso_group)
        self._fill_isolation()
        about = Adw.PreferencesGroup(title="What This Means")
        about.add(label(
            "QDVC Articulate is packaged as a Flatpak without network permission, so it runs in a network "
            "namespace of its own that contains only the loopback interface: there is no route off the computer, "
            "for the app or for any library inside it, llama.cpp included. You can confirm it in Flatseal "
            "(Network off) or with: flatpak info --show-permissions qdvc.articulate.gtk4app.\n\n"
            "It has no access to your files either, beyond those you choose: documents and the AI model are opened "
            "through the system file chooser, which grants access to each file you pick.\n\n"
            "Other privacy measures: no analytics, no crash reporters, no update checks, no cloud sync. The AI "
            "model is a file you choose. Spelling runs inside the app. AI results are cached in memory only; "
            "drafts of unsaved documents stay in the app's own folder.", "dim-label", wrap=True))
        page.add(about)
        return page

    def _fill_isolation(self) -> None:
        clear(self.iso_list)
        r = isolation.report()

        def row(title: str, ok: bool, ok_text: str, bad_text: str) -> None:
            item = Adw.ActionRow(title=title)
            suffix = Gtk.Box(spacing=6)
            suffix.append(tint(Gtk.Image(icon_name="security-high-symbolic" if ok else "dialog-warning-symbolic"),
                               "green" if ok else "orange"))
            suffix.append(label(ok_text if ok else bad_text))
            item.add_suffix(suffix)
            self.iso_list.append(item)
        row("Flatpak Sandbox", r.sandboxed, "On", "Off (run from a checkout)")
        row("Network Permission", r.sandboxed and not r.network_permission, "Absent",
            "Present" if r.network_permission else "Not restricted")
        row("Network Interfaces", r.only_loopback, f"Loopback only ({r.interfaces_text})", r.interfaces_text)
        files = [f for f in r.filesystems if not f.startswith("xdg-run/")]
        row("File Access", r.sandboxed and not files, "Only files you choose",
            ", ".join(files) if files else "Not restricted")


def _with(check, **kw):
    from dataclasses import replace
    return replace(check, **kw)


def _button_row(title: str, callback) -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, activatable=True)
    row.connect("activated", lambda *_: callback())
    return row


def shortcuts_dialog(parent) -> None:
    """Keyboard shortcuts, from ui_prefs.SHORTCUTS."""
    d = Adw.Dialog(title="Keyboard Shortcuts", content_width=480, content_height=620)
    page = Adw.PreferencesPage()
    groups: dict[str, Adw.PreferencesGroup] = {}
    for section, title, _action, accels in U.SHORTCUTS:
        if section not in groups:
            groups[section] = Adw.PreferencesGroup(title=section)
            page.add(groups[section])
        row = Adw.ActionRow(title=escape(title[:1].upper() + title[1:]))
        ok, key, mods = Gtk.accelerator_parse(accels[0])
        row.add_suffix(label(Gtk.accelerator_get_label(key, mods) if ok else accels[0], "dim-label"))
        groups[section].add(row)
    view = Adw.ToolbarView(content=page)
    view.add_top_bar(Adw.HeaderBar())
    d.set_child(view)
    d.present(parent)
