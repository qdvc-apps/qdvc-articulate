import AppKit
import Combine
import ArticulateCore

/// Per-window brain: runs checks, keeps issues in sync with edits, drives underlines.
@MainActor
final class EditorController: ObservableObject {
    enum AIState: Equatable {
        case idle
        case running(done: Int, total: Int)
        case finished(found: Int)
        case failed(String)
    }

    @Published private(set) var issues: [Issue] = []
    @Published private(set) var stats: TextStatistics = .empty
    @Published private(set) var aiState: AIState = .idle
    @Published var focusedIssueID: UUID?
    @Published var hiddenGroups: Set<IssueGroup> = [] {
        didSet { applyUnderlines() }
    }
    @Published var importRequested = false

    weak var textView: ArticulateTextView?

    private(set) var text = ""
    private var generation = 0
    private var ruleIssues: [Issue] = []
    private var systemIssues: [Issue] = []
    private var aiIssues: [Issue] = []
    private var ignored: Set<String> = []
    private var quickTask: Task<Void, Never>?
    private var aiTask: Task<Void, Never>?
    private var autoAITask: Task<Void, Never>?
    /// Edits made while an AI review is running, used to map its results onto the current text.
    private var editsDuringAI: [(span: TextSpan, replacementLength: Int)] = []
    private var cancellables = Set<AnyCancellable>()
    private var isAttached = false

    private var settings: SettingsStore { SettingsStore.shared }
    private var models: ModelManager { ModelManager.shared }

    var visibleIssues: [Issue] {
        issues.filter { !hiddenGroups.contains($0.category.group) }
    }

    var focusedIssue: Issue? {
        guard let id = focusedIssueID else { return nil }
        return issues.first { $0.id == id }
    }

    func count(in group: IssueGroup) -> Int {
        issues.reduce(0) { $0 + ($1.category.group == group ? 1 : 0) }
    }

    // MARK: Lifecycle

    func attach() {
        guard !isAttached else { return }
        isAttached = true
        settings.objectWillChange
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .sink { [weak self] _ in
                guard let self else { return }
                Task { await self.runQuickCheck() }
            }
            .store(in: &cancellables)
    }

    /// Called once when the text view is created.
    func load(text: String) {
        self.text = text
        generation += 1
        scheduleQuickCheck(delay: 0)
    }

    // MARK: Editing

    func willEdit(range: NSRange, replacementLength: Int) {
        let span = TextSpan(range)
        ruleIssues = IssueAdjuster.adjust(ruleIssues, editedSpan: span, replacementLength: replacementLength)
        systemIssues = IssueAdjuster.adjust(systemIssues, editedSpan: span, replacementLength: replacementLength)
        aiIssues = IssueAdjuster.adjust(aiIssues, editedSpan: span, replacementLength: replacementLength)
        if case .running = aiState {
            editsDuringAI.append((span, replacementLength))
        }
    }

    func textDidChange(_ newText: String) {
        text = newText
        generation += 1
        refresh()
        scheduleQuickCheck(delay: 350_000_000)
        scheduleAutoAI()
    }

    /// The document changed underneath the editor (e.g. File ▸ Revert).
    func textReplacedExternally(_ newText: String) {
        text = newText
        generation += 1
        ruleIssues = []
        systemIssues = []
        aiIssues = []
        refresh()
        scheduleQuickCheck(delay: 0)
    }

    func selectionChanged(_ range: NSRange) {
        let candidate = issue(at: range.location)
        if candidate?.id != focusedIssueID, let candidate, range.length == 0 || candidate.span.nsRange == range {
            focusedIssueID = candidate.id
            applyUnderlines()
        }
    }

    // MARK: Quick checks (rules + macOS spelling)

    private func scheduleQuickCheck(delay: UInt64) {
        quickTask?.cancel()
        quickTask = Task { [weak self] in
            if delay > 0 { try? await Task.sleep(nanoseconds: delay) }
            guard !Task.isCancelled else { return }
            await self?.runQuickCheck()
        }
    }

    func runQuickCheck() async {
        let snapshot = text
        let snapshotGeneration = generation
        let check = settings.check
        let (rules, statistics) = await Task.detached(priority: .userInitiated) {
            (RuleEngine(settings: check).check(snapshot), TextStatistics.compute(snapshot))
        }.value
        guard snapshotGeneration == generation else { return } // text changed meanwhile; a newer check is queued

        ruleIssues = rules
        stats = statistics
        systemIssues = SystemSpellChecker.check(
            snapshot,
            dialect: check.dialect,
            spelling: settings.useSystemSpelling,
            grammar: settings.useSystemGrammar
        )
        refresh()
    }

    // MARK: AI check

    func runAICheck() {
        guard models.isReady else {
            aiState = .failed(models.notReadyMessage)
            return
        }
        aiTask?.cancel()
        let snapshot = text
        let check = settings.check
        editsDuringAI = []
        aiState = .running(done: 0, total: 0)

        aiTask = Task { [weak self] in
            guard let self else { return }
            await self.models.prepareForReview()
            guard let stream = self.models.review(text: snapshot, settings: check) else {
                self.aiState = .failed(self.models.notReadyMessage)
                return
            }
            var found = 0
            do {
                for try await progress in stream {
                    let region = self.mapRegion(progress.chunkSpan)
                    let mapped = progress.issues.compactMap { self.mapIssue($0) }
                    self.aiIssues.removeAll { $0.span.intersects(region) }
                    self.aiIssues.append(contentsOf: mapped)
                    found += mapped.count
                    self.aiState = .running(done: progress.completed, total: progress.total)
                    self.refresh()
                }
                self.aiState = .finished(found: found)
                if self.settings.autoAICheck && !self.editsDuringAI.isEmpty {
                    self.scheduleAutoAI()
                }
            } catch is CancellationError {
                self.aiState = .idle
            } catch {
                self.aiState = Task.isCancelled ? .idle : .failed(error.localizedDescription)
            }
            self.editsDuringAI = []
        }
    }

    func cancelAICheck() {
        aiTask?.cancel()
        aiTask = nil
        if case .running = aiState { aiState = .idle }
    }

    private func scheduleAutoAI() {
        autoAITask?.cancel()
        guard settings.autoAICheck, models.isReady else { return }
        autoAITask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            guard !Task.isCancelled, let self else { return }
            if case .running = self.aiState { return }
            self.runAICheck()
        }
    }

    private func mapIssue(_ issue: Issue) -> Issue? {
        var current = [issue]
        for edit in editsDuringAI {
            current = IssueAdjuster.adjust(current, editedSpan: edit.span, replacementLength: edit.replacementLength)
        }
        return current.first
    }

    private func mapRegion(_ span: TextSpan) -> TextSpan {
        var region = span
        for edit in editsDuringAI {
            region = IssueAdjuster.transformRegion(region, editedSpan: edit.span, replacementLength: edit.replacementLength)
        }
        return region
    }

    // MARK: Actions

    func apply(_ issue: Issue, suggestion: String) {
        guard let textView else { return }
        guard text.substring(in: issue.span) == issue.original else {
            refresh()
            return
        }
        let range = issue.span.nsRange
        if textView.shouldChangeText(in: range, replacementString: suggestion) {
            textView.textStorage?.replaceCharacters(in: range, with: suggestion)
            textView.didChangeText()
            let caret = NSRange(location: range.location + (suggestion as NSString).length, length: 0)
            textView.setSelectedRange(caret)
        }
    }

    func applyFocusedSuggestion() {
        guard let issue = focusedIssue, let first = issue.suggestions.first else { return }
        apply(issue, suggestion: first)
        selectNextIssue()
    }

    func ignore(_ issue: Issue) {
        ignored.insert(issue.fingerprint)
        refresh()
    }

    func ignoreFocusedIssue() {
        guard let issue = focusedIssue else { return }
        ignore(issue)
        selectNextIssue()
    }

    func addToDictionary(_ issue: Issue) {
        settings.addToDictionary(issue.original)
        refresh()
    }

    func clearIgnored() {
        ignored.removeAll()
        refresh()
    }

    func focus(_ issue: Issue) {
        focusedIssueID = issue.id
        guard let textView else { return }
        let range = issue.span.nsRange
        textView.window?.makeFirstResponder(textView)
        textView.setSelectedRange(range)
        textView.scrollRangeToVisible(range)
        textView.showFindIndicator(for: range)
        applyUnderlines()
    }

    func selectNextIssue() {
        let list = visibleIssues
        guard !list.isEmpty else { return }
        let position = focusedIssue?.span.location ?? (textView?.selectedRange().location ?? -1)
        focus(list.first { $0.span.location > position } ?? list[0])
    }

    func selectPreviousIssue() {
        let list = visibleIssues
        guard !list.isEmpty else { return }
        let position = focusedIssue?.span.location ?? (textView?.selectedRange().location ?? Int.max)
        focus(list.last { $0.span.location < position } ?? list[list.count - 1])
    }

    /// The innermost visible issue at a character index (inclusive of the end, for clicks just after a word).
    func issue(at index: Int) -> Issue? {
        visibleIssues
            .filter { index >= $0.span.location && index <= $0.span.upperBound }
            .min { $0.span.length < $1.span.length }
    }

    // MARK: Rendering

    private func refresh() {
        let zones = ExclusionZones.compute(in: text)
        issues = IssueMerger.merge(
            [systemIssues, ruleIssues, aiIssues],
            text: text,
            ignored: ignored,
            settings: settings.check,
            zones: zones
        )
        if let id = focusedIssueID, !issues.contains(where: { $0.id == id }) {
            focusedIssueID = nil
        }
        applyUnderlines()
    }

    func applyUnderlines() {
        guard let textView, let layoutManager = textView.layoutManager else { return }
        let length = (textView.string as NSString).length
        let full = NSRange(location: 0, length: length)
        layoutManager.removeTemporaryAttribute(.underlineStyle, forCharacterRange: full)
        layoutManager.removeTemporaryAttribute(.underlineColor, forCharacterRange: full)
        layoutManager.removeTemporaryAttribute(.backgroundColor, forCharacterRange: full)

        for issue in visibleIssues where issue.span.upperBound <= length {
            let color = IssueStyle.nsColor(for: issue.category.group)
            let style: NSUnderlineStyle = issue.severity >= .warning ? [.thick] : [.single, .patternDot]
            var attributes: [NSAttributedString.Key: Any] = [
                .underlineStyle: style.rawValue,
                .underlineColor: color,
            ]
            if issue.id == focusedIssueID {
                attributes[.backgroundColor] = color.withAlphaComponent(0.18)
            }
            layoutManager.addTemporaryAttributes(attributes, forCharacterRange: issue.span.nsRange)
        }
    }
}
