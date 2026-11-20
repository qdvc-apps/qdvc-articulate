import SwiftUI
import ArticulateCore

struct StatusBar: View {
    @ObservedObject var controller: EditorController
    @EnvironmentObject private var models: ModelManager
    let isolated: Bool
    @State private var showStatistics = false

    var body: some View {
        HStack(spacing: 14) {
            Button {
                showStatistics.toggle()
            } label: {
                Text("\(controller.stats.words) words · \(Self.duration(controller.stats.readingTimeSeconds)) read")
                    .monospacedDigit()
            }
            .buttonStyle(.plain)
            .help("Show document statistics")
            .popover(isPresented: $showStatistics, arrowEdge: .top) {
                StatisticsView(stats: controller.stats)
            }

            if let score = controller.stats.fleschReadingEase {
                Text("Readability \(Int(score.rounded())) · \(controller.stats.readabilityLabel)")
                    .help("Flesch Reading Ease: higher is easier. 60–70 is plain English.")
            }

            Spacer(minLength: 8)

            AIStatusView(controller: controller)

            Text(controller.issues.isEmpty ? "No issues" : "\(controller.issues.count) issue\(controller.issues.count == 1 ? "" : "s")")
                .monospacedDigit()

            Image(systemName: isolated ? "lock.shield.fill" : "exclamationmark.shield.fill")
                .foregroundStyle(isolated ? Color.green : Color.orange)
                .help(isolated
                      ? "Offline: macOS blocks all network access for this app (App Sandbox, no network entitlement)."
                      : "Network isolation is NOT enforced for this build. See Settings → Privacy.")
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding(.horizontal, 12)
        .padding(.vertical, 5)
        .background(.bar)
    }

    static func duration(_ seconds: Int) -> String {
        if seconds < 60 { return "\(max(seconds, 0)) s" }
        let minutes = Int((Double(seconds) / 60).rounded())
        return "\(minutes) min"
    }
}

private struct AIStatusView: View {
    @ObservedObject var controller: EditorController
    @EnvironmentObject private var models: ModelManager

    var body: some View {
        HStack(spacing: 6) {
            switch models.state {
            case .notCompiledIn:
                Label("AI unavailable", systemImage: "sparkles")
                    .help(models.notReadyMessage)
            case .noModel:
                SettingsLink {
                    Label("Choose an AI model…", systemImage: "sparkles")
                }
                .buttonStyle(.plain)
            case .loading(let name):
                ProgressView().controlSize(.mini)
                Text("Loading \(name)…")
            case .failed(let message):
                Label("AI model error", systemImage: "exclamationmark.triangle")
                    .foregroundStyle(.orange)
                    .help(message)
            case .ready(let info):
                readyView(info.fileName)
            }
        }
    }

    @ViewBuilder
    private func readyView(_ name: String) -> some View {
        switch controller.aiState {
        case .running(let done, let total):
            if total > 0 {
                ProgressView(value: Double(done), total: Double(total))
                    .frame(width: 70)
                    .controlSize(.mini)
                Text("AI \(done)/\(total)").monospacedDigit()
            } else {
                ProgressView().controlSize(.mini)
                Text("AI starting…")
            }
            Button {
                controller.cancelAICheck()
            } label: {
                Image(systemName: "stop.circle")
            }
            .buttonStyle(.plain)
            .help("Stop the AI review (⌘.)")
        case .finished(let found):
            Label("AI: \(found) suggestion\(found == 1 ? "" : "s")", systemImage: "sparkles")
                .help("Model: \(name)")
        case .failed(let message):
            Label("AI error", systemImage: "exclamationmark.triangle")
                .foregroundStyle(.orange)
                .help(message)
        case .idle:
            Label("AI ready", systemImage: "sparkles")
                .help("Model: \(name). Press ⇧⌘K to review the document.")
        }
    }
}

struct StatisticsView: View {
    let stats: TextStatistics

    var body: some View {
        Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 6) {
            row("Words", "\(stats.words)")
            row("Characters", "\(stats.characters)")
            row("Characters (no spaces)", "\(stats.charactersExcludingSpaces)")
            row("Sentences", "\(stats.sentences)")
            row("Paragraphs", "\(stats.paragraphs)")
            Divider().gridCellColumns(2)
            row("Average sentence", String(format: "%.1f words", stats.averageWordsPerSentence))
            row("Longest sentence", "\(stats.longestSentenceWords) words")
            row("Unique words", "\(stats.uniqueWords) (\(Int((stats.lexicalDiversity * 100).rounded()))%)")
            Divider().gridCellColumns(2)
            row("Reading time", StatusBar.duration(stats.readingTimeSeconds))
            row("Speaking time", StatusBar.duration(stats.speakingTimeSeconds))
            if let ease = stats.fleschReadingEase, let grade = stats.fleschKincaidGrade {
                Divider().gridCellColumns(2)
                row("Flesch Reading Ease", String(format: "%.0f (%@)", ease, stats.readabilityLabel))
                row("Flesch–Kincaid grade", String(format: "%.1f", grade))
            }
        }
        .font(.callout)
        .padding(16)
        .frame(minWidth: 280)
    }

    private func row(_ label: String, _ value: String) -> GridRow<some View> {
        GridRow {
            Text(label).foregroundStyle(.secondary)
            Text(value).monospacedDigit()
        }
    }
}
