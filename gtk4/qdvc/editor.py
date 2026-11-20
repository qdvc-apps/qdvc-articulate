"""Per-document checking: a port of the macOS edition's EditorController,
without the toolkit. It runs the quick checks (rules, statistics, spelling)
after a pause in typing, runs the AI review on demand, keeps every issue in
step with edits, merges the sources, and tracks the focused issue.

The front-end supplies an environment (`schedule`, `run_in_thread`, `post`)
and a view (`replace_range`, `reveal`), and listens: listeners get
"issues", "stats", "ai" or "focus". Everything here runs on the main loop
except the work handed to `run_in_thread`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ai import Cancelled, CancelToken
from .llm import LlamaError
from .model import Issue, IssueCategory, IssueGroup, TextSpan, substring
from .rules import RuleEngine
from .text import ExclusionZones, IssueAdjuster, IssueMerger, TextStatistics

QUICK_DELAY = 0.35
AUTO_AI_DELAY = 3.0


@dataclass(frozen=True)
class AIState:
    kind: str = "idle"        # idle, running, finished, failed
    done: int = 0
    total: int = 0
    found: int = 0
    message: str = ""

    @property
    def running(self) -> bool:
        return self.kind == "running"


class Environment:
    """Synchronous stand-ins (the tests); the window passes GLib-backed ones."""

    class _Handle:
        def cancel(self):
            pass

    def schedule(self, delay: float, fn):
        fn()
        return Environment._Handle()

    def run_in_thread(self, work, done) -> None:
        done(work())

    def post(self, fn) -> None:
        fn()


class EditorState:
    def __init__(self, prefs, models, spell, env: Environment | None = None, view=None):
        self.prefs = prefs
        self.models = models
        self.spell = spell
        self.env = env or Environment()
        self.view = view
        self.text = ""
        self.issues: list[Issue] = []
        self.stats = TextStatistics()
        self.ai_state = AIState()
        self.focused_id: str | None = None
        self.hidden_groups: set[IssueGroup] = set()
        self.ignored: set[str] = set()
        self._generation = 0
        self._rule_issues: list[Issue] = []
        self._spell_issues: list[Issue] = []
        self._ai_issues: list[Issue] = []
        self._edits_during_ai: list[tuple[TextSpan, int]] = []
        self._quick = None
        self._auto_ai = None
        self._cancel: CancelToken | None = None
        self._listeners: list = []
        self._closed = False

    # --- listeners ---------------------------------------------------------------------------

    def connect(self, fn) -> None:
        self._listeners.append(fn)

    def _emit(self, what: str) -> None:
        if not self._closed:
            for fn in list(self._listeners):
                fn(what)

    def close(self) -> None:
        self.cancel_ai()
        for h in (self._quick, self._auto_ai):
            if h:
                h.cancel()
        self._closed = True
        self._listeners.clear()

    # --- views of the issues ----------------------------------------------------------------

    @property
    def visible_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.category.group not in self.hidden_groups]

    @property
    def focused_issue(self) -> Issue | None:
        return next((i for i in self.issues if i.id == self.focused_id), None)

    def count(self, group: IssueGroup) -> int:
        return sum(1 for i in self.issues if i.category.group is group)

    def issue_at(self, index: int) -> Issue | None:
        """The innermost visible issue at a character index (inclusive of the end, for clicks just after a word)."""
        found = [i for i in self.visible_issues if i.span.location <= index <= i.span.upper_bound]
        return min(found, key=lambda i: i.span.length) if found else None

    def set_group_hidden(self, group: IssueGroup, hidden: bool) -> None:
        (self.hidden_groups.add if hidden else self.hidden_groups.discard)(group)
        self._emit("issues")

    # --- loading and editing -------------------------------------------------------------------

    def load(self, text: str) -> None:
        """A new text (opening a file, reverting): everything is checked again."""
        self.text = text
        self._generation += 1
        self._rule_issues, self._spell_issues, self._ai_issues = [], [], []
        self.cancel_ai()
        self.refresh()
        self.schedule_quick_check(0)

    def will_edit(self, start: int, old_length: int, new_length: int) -> None:
        """Before an edit: shift or drop the issues it affects."""
        span = TextSpan(start, old_length)
        self._rule_issues = IssueAdjuster.adjust(self._rule_issues, span, new_length)
        self._spell_issues = IssueAdjuster.adjust(self._spell_issues, span, new_length)
        self._ai_issues = IssueAdjuster.adjust(self._ai_issues, span, new_length)
        if self.ai_state.running:
            self._edits_during_ai.append((span, new_length))

    def text_changed(self, text: str) -> None:
        self.text = text
        self._generation += 1
        self.refresh()
        self.schedule_quick_check(QUICK_DELAY)
        self.schedule_auto_ai()

    def settings_changed(self) -> None:
        """Preferences changed (variety of English, goals, rules, dictionary): check again."""
        self.refresh()
        self.schedule_quick_check(0)

    # --- quick checks -------------------------------------------------------------------------

    def schedule_quick_check(self, delay: float) -> None:
        if self._quick:
            self._quick.cancel()
        self._quick = self.env.schedule(delay, self.run_quick_check)

    def run_quick_check(self) -> None:
        self._quick = None
        snapshot, generation = self.text, self._generation
        check, use_spelling, spell = self.prefs.check, self.prefs.spelling, self.spell

        def work():
            rules = RuleEngine(check).check(snapshot)
            stats = TextStatistics.compute(snapshot)
            spelling = spell.check(snapshot, check.dialect) if (use_spelling and spell is not None) else []
            return rules, stats, spelling

        def done(result):
            if generation != self._generation or self._closed:
                return  # the text changed meanwhile; a newer check is queued
            self._rule_issues, self.stats, self._spell_issues = result
            self._emit("stats")
            self.refresh()
        self.env.run_in_thread(work, done)

    # --- the AI review ---------------------------------------------------------------------------

    def run_ai_check(self) -> None:
        if not self.models.is_ready:
            self._set_ai(AIState("failed", message=self.models.not_ready_message))
            return
        self.cancel_ai(quiet=True)
        snapshot, check = self.text, self.prefs.check
        cancel = CancelToken()
        self._cancel = cancel
        self._edits_during_ai = []
        stream = self.models.review(snapshot, check, cancel)
        if stream is None:
            self._set_ai(AIState("failed", message=self.models.not_ready_message))
            return
        self._set_ai(AIState("running"))
        found = [0]

        def progress(p):
            if cancel.cancelled or self._closed:
                return
            region = self._map_region(p.chunk_span)
            mapped = [m for m in (self._map_issue(i) for i in p.issues) if m is not None]
            self._ai_issues = [i for i in self._ai_issues if not i.span.intersects(region)] + mapped
            found[0] += len(mapped)
            self._set_ai(AIState("running", p.completed, p.total))
            self.refresh()

        def finish(state: AIState):
            if self._cancel is not cancel or self._closed:
                return
            self._cancel = None
            edited = bool(self._edits_during_ai)
            self._edits_during_ai = []
            self._set_ai(state)
            if state.kind == "finished" and self.prefs.auto_ai and edited:
                self.schedule_auto_ai()

        def work():
            try:
                for p in stream:
                    self.env.post(lambda p=p: progress(p))
                state = AIState("finished", found=-1)
            except Cancelled:
                state = AIState("idle")
            except LlamaError as e:
                state = AIState("failed", message=str(e))
            except Exception as e:  # an engine failure must never take the window down
                state = AIState("failed", message=f"The AI review failed: {e}")
            return state

        def done(state: AIState):
            if state.kind == "finished":
                state = AIState("finished", found=found[0])
            finish(state)
        self.env.run_in_thread(work, done)

    def cancel_ai(self, quiet: bool = False) -> None:
        if self._cancel is not None:
            self._cancel.cancel()
            self._cancel = None
        if self.ai_state.running and not quiet:
            self._set_ai(AIState("idle"))

    def schedule_auto_ai(self) -> None:
        if self._auto_ai:
            self._auto_ai.cancel()
            self._auto_ai = None
        if not (self.prefs.auto_ai and self.models.is_ready):
            return

        def fire():
            self._auto_ai = None
            if not self.ai_state.running:
                self.run_ai_check()
        self._auto_ai = self.env.schedule(AUTO_AI_DELAY, fire)

    def _set_ai(self, state: AIState) -> None:
        self.ai_state = state
        self._emit("ai")

    def _map_issue(self, issue: Issue) -> Issue | None:
        current = [issue]
        for span, length in self._edits_during_ai:
            current = IssueAdjuster.adjust(current, span, length)
        return current[0] if current else None

    def _map_region(self, span: TextSpan) -> TextSpan:
        for edit, length in self._edits_during_ai:
            span = IssueAdjuster.transform_region(span, edit, length)
        return span

    # --- actions -------------------------------------------------------------------------------

    def apply(self, issue: Issue, suggestion: str) -> None:
        if substring(self.text, issue.span) != issue.original:
            self.refresh()
            return
        if self.view is not None:
            self.view.replace_range(issue.span.location, issue.span.upper_bound, suggestion)

    def apply_focused(self) -> None:
        issue = self.focused_issue
        if issue is None or not issue.suggestions:
            return
        self.apply(issue, issue.suggestions[0])
        self.select_next()

    def ignore(self, issue: Issue) -> None:
        self.ignored.add(issue.fingerprint)
        self.refresh()

    def ignore_focused(self) -> None:
        issue = self.focused_issue
        if issue is not None:
            self.ignore(issue)
            self.select_next()

    def add_to_dictionary(self, issue: Issue) -> None:
        self.prefs.add_to_dictionary(issue.original)  # Preferences notifies every tab

    def clear_ignored(self) -> None:
        self.ignored.clear()
        self.refresh()

    def focus(self, issue: Issue, reveal: bool = True) -> None:
        self.focused_id = issue.id
        if reveal and self.view is not None:
            self.view.reveal(issue.span.location, issue.span.upper_bound)
        self._emit("focus")

    def selection_changed(self, start: int, end: int) -> None:
        candidate = self.issue_at(start)
        if candidate is not None and candidate.id != self.focused_id and \
                (start == end or (candidate.span.location, candidate.span.upper_bound) == (start, end)):
            self.focused_id = candidate.id
            self._emit("focus")

    def select_next(self, cursor: int = -1) -> None:
        items = self.visible_issues
        if not items:
            return
        focused = self.focused_issue
        position = focused.span.location if focused else cursor
        self.focus(next((i for i in items if i.span.location > position), items[0]))

    def select_previous(self, cursor: int = 1 << 62) -> None:
        items = self.visible_issues
        if not items:
            return
        focused = self.focused_issue
        position = focused.span.location if focused else cursor
        self.focus(next((i for i in reversed(items) if i.span.location < position), items[-1]))

    # --- merging ---------------------------------------------------------------------------------

    def refresh(self) -> None:
        zones = ExclusionZones.compute(self.text)
        self.issues = IssueMerger.merge([self._spell_issues, self._rule_issues, self._ai_issues], self.text,
                                        self.ignored, self.prefs.check, zones)
        if self.focused_id and not any(i.id == self.focused_id for i in self.issues):
            self.focused_id = None
        self._emit("issues")


def is_spelling(issue: Issue) -> bool:
    return issue.category is IssueCategory.SPELLING

