import SwiftUI
import UniformTypeIdentifiers
import ArticulateCore
import ArticulateLLM

struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettingsView()
                .tabItem { Label("General", systemImage: "gearshape") }
            RulesSettingsView()
                .tabItem { Label("Rules", systemImage: "list.bullet.rectangle") }
            ModelSettingsView()
                .tabItem { Label("AI Model", systemImage: "sparkles") }
            DictionarySettingsView()
                .tabItem { Label("Dictionary", systemImage: "character.book.closed") }
            PrivacySettingsView()
                .tabItem { Label("Privacy", systemImage: "lock.shield") }
        }
        .frame(width: 600, height: 540)
    }
}

// MARK: - General

private struct GeneralSettingsView: View {
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        Form {
            Section("Language and goals") {
                Picker("English", selection: $settings.check.dialect) {
                    ForEach(Dialect.allCases) { Text($0.displayName).tag($0) }
                }
                Picker("Formality", selection: $settings.check.goals.formality) {
                    ForEach(Formality.allCases) { Text($0.displayName).tag($0) }
                }
                Picker("Audience", selection: $settings.check.goals.audience) {
                    ForEach(Audience.allCases) { Text($0.displayName).tag($0) }
                }
                Picker("Domain", selection: $settings.check.goals.domain) {
                    ForEach(WritingDomain.allCases) { Text($0.displayName).tag($0) }
                }
                Stepper(value: $settings.check.longSentenceWordLimit, in: 15...80, step: 5) {
                    LabeledContent("Flag sentences longer than", value: "\(settings.check.longSentenceWordLimit) words")
                }
            }

            Section {
                Toggle("macOS spelling checker", isOn: $settings.useSystemSpelling)
                Toggle("macOS grammar checker", isOn: $settings.useSystemGrammar)
                Toggle("Run the AI review automatically after a pause in typing", isOn: $settings.autoAICheck)
            } header: {
                Text("Checking")
            } footer: {
                Text("The macOS checkers run on this Mac (AppleSpell), outside the app’s own sandboxed process. Turn them off if you want only QDVC Articulate’s own code to see your text.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("Editor") {
                Slider(value: $settings.editorFontSize, in: 11...28, step: 1) {
                    Text("Font size")
                } minimumValueLabel: {
                    Text("A").font(.caption)
                } maximumValueLabel: {
                    Text("A").font(.title3)
                }
                Toggle("Monospaced font", isOn: $settings.useMonospacedFont)
            }
        }
        .formStyle(.grouped)
    }
}

// MARK: - Rules

private struct RulesSettingsView: View {
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        Form {
            ForEach(IssueGroup.allCases) { group in
                let rules = RuleEngine.ruleInfos.filter { $0.category.group == group }
                if !rules.isEmpty {
                    Section(group.displayName) {
                        ForEach(rules) { rule in
                            Toggle(isOn: binding(for: rule)) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(rule.name)
                                    Text(rule.summary)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            Section {
                Button("Restore Defaults") { settings.resetRules() }
            }
        }
        .formStyle(.grouped)
    }

    private func binding(for rule: RuleInfo) -> Binding<Bool> {
        Binding(
            get: { settings.isRuleEnabled(rule) },
            set: { settings.setRule(rule, enabled: $0) }
        )
    }
}

// MARK: - AI model

private struct ModelSettingsView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var models: ModelManager
    @State private var choosingFile = false

    private static let ggufType = UTType(filenameExtension: "gguf") ?? .data

    var body: some View {
        Form {
            Section("Model") {
                statusRow
                if let name = settings.modelFileName {
                    LabeledContent("File", value: name)
                }
                if let info = models.info {
                    LabeledContent("Model", value: info.description)
                    LabeledContent("Size", value: ByteCountFormatter.string(fromByteCount: Int64(info.sizeBytes), countStyle: .file))
                    LabeledContent("Parameters", value: String(format: "%.2f billion", Double(info.parameterCount) / 1e9))
                    LabeledContent("Context", value: "\(info.contextLength) tokens (trained: \(info.trainedContextLength))")
                    if let format = models.resolvedFormat {
                        LabeledContent("Prompt format", value: format.displayName)
                    }
                }
                HStack {
                    Button("Choose GGUF File…") { choosingFile = true }
                        .disabled(!LlamaEngine.isAvailable)
                    Button("Reload") { models.load() }
                        .disabled(settings.modelBookmark == nil || !LlamaEngine.isAvailable)
                    Button("Unload") { models.unload() }
                        .disabled(!models.isReady)
                    Spacer()
                    Button("Forget Model", role: .destructive) { models.forget() }
                        .disabled(settings.modelBookmark == nil)
                }
            }

            Section {
                Picker("Context length", selection: $settings.llama.contextLength) {
                    ForEach([2048, 4096, 8192, 16384, 32768], id: \.self) { Text("\($0) tokens").tag($0) }
                }
                Toggle("Use the GPU (Metal)", isOn: Binding(
                    get: { settings.llama.gpuLayers > 0 },
                    set: { settings.llama.gpuLayers = $0 ? 99 : 0 }
                ))
                Stepper(value: $settings.llama.threads, in: 0...32) {
                    LabeledContent("CPU threads", value: settings.llama.threads == 0 ? "Automatic" : "\(settings.llama.threads)")
                }
                Toggle("Load the model when the app starts", isOn: $settings.llama.loadAtLaunch)
            } header: {
                Text("Loading")
            } footer: {
                Text("Changes here take effect after Reload.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }

            Section("Review") {
                Picker("Prompt format", selection: $settings.llama.promptFormat) {
                    ForEach(PromptFormat.allCases) { Text($0.displayName).tag($0) }
                }
                Picker("Max. output per paragraph", selection: $settings.llama.maxOutputTokens) {
                    ForEach([512, 768, 1024, 1536, 2048], id: \.self) { Text("\($0) tokens").tag($0) }
                }
                Picker("Paragraph chunk size", selection: $settings.llama.chunkLength) {
                    ForEach([600, 900, 1200, 1800, 2400], id: \.self) { Text("\($0) characters").tag($0) }
                }
                LabeledContent("Temperature") {
                    HStack {
                        Slider(value: $settings.llama.temperature, in: 0...1, step: 0.05)
                        Text(String(format: "%.2f", settings.llama.temperature))
                            .monospacedDigit()
                            .frame(width: 36, alignment: .trailing)
                    }
                }
                Toggle("Reuse the instruction prompt between paragraphs (faster)", isOn: $settings.llama.reusePromptCache)
                Button("Clear Cached AI Results") { models.clearCache() }
            }

            Section("Recommended models") {
                Text("""
                Any instruction-tuned GGUF works. Good choices for proofreading on Apple Silicon:
                • Gemma 4 E4B Instruct, Q4_K_M (≈ 5 GB) — best balance of quality and speed
                • Gemma 4 E2B Instruct, Q4_K_M — faster, for 8 GB Macs
                • Qwen3 4B or 8B Instruct, Q4_K_M — strong grammar, ChatML format
                Download the file yourself on any device and copy it to this Mac. QDVC Articulate never downloads anything.
                """)
                .font(.callout)
                .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .fileImporter(isPresented: $choosingFile, allowedContentTypes: [Self.ggufType]) { result in
            if case .success(let url) = result {
                models.setModel(url: url)
            }
        }
    }

    @ViewBuilder
    private var statusRow: some View {
        switch models.state {
        case .notCompiledIn:
            Label("This build has no AI engine. Put llama.xcframework into Vendor/ and rebuild.", systemImage: "exclamationmark.triangle")
                .foregroundStyle(.orange)
        case .noModel:
            Label("No model selected", systemImage: "circle.dashed")
        case .loading(let name):
            HStack {
                ProgressView().controlSize(.small)
                Text("Loading \(name)…")
            }
        case .ready:
            Label("Ready", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .failed(let message):
            Label(message, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
        }
    }
}

// MARK: - Dictionary

private struct DictionarySettingsView: View {
    @EnvironmentObject private var settings: SettingsStore
    @State private var newWord = ""
    @State private var selection = Set<String>()

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Words in your personal dictionary are never flagged as misspelled.")
                .foregroundStyle(.secondary)
            List(settings.check.personalDictionary, id: \.self, selection: $selection) { word in
                Text(word)
            }
            .frame(minHeight: 300)
            HStack {
                TextField("Add a word", text: $newWord)
                    .onSubmit(add)
                Button("Add", action: add)
                    .disabled(newWord.trimmingCharacters(in: .whitespaces).isEmpty)
                Spacer()
                Button("Remove Selected") {
                    for word in selection { settings.removeFromDictionary(word) }
                    selection.removeAll()
                }
                .disabled(selection.isEmpty)
            }
        }
        .padding(20)
    }

    private func add() {
        settings.addToDictionary(newWord)
        newWord = ""
    }
}

// MARK: - Privacy

private struct PrivacySettingsView: View {
    @State private var report = IsolationChecker.staticReport()

    var body: some View {
        Form {
            Section("Network isolation") {
                row("App Sandbox", ok: report.sandboxed, okText: "On", badText: "Off")
                row("Outgoing network entitlement", ok: !report.networkClientEntitlement, okText: "Absent", badText: "Present")
                row("Incoming network entitlement", ok: !report.networkServerEntitlement, okText: "Absent", badText: "Present")
                if let probe = report.probe {
                    row("Live connection test", ok: probe.isBlocked, okText: "Blocked", badText: "Not blocked")
                    Text(probe.detail)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Button("Run Live Connection Test") {
                    report = IsolationChecker.fullReport()
                }
            }

            Section("What this means") {
                Text("""
                QDVC Articulate is built with the macOS App Sandbox and without any network entitlement, so the operating system itself refuses every network connection the app (or any library inside it, including llama.cpp) might attempt. The live test tries to connect to this Mac’s own loopback address (127.0.0.1); nothing can leave the device even if the test were allowed.

                Other privacy measures: no analytics, no crash reporters, no update checks, no cloud sync. The AI model is a file you choose. Writing Tools, Services and Share are disabled in the editor. AI results are cached in memory only.
                """)
                .font(.callout)
                .foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
    }

    private func row(_ title: String, ok: Bool, okText: String, badText: String) -> some View {
        LabeledContent(title) {
            Label(ok ? okText : badText, systemImage: ok ? "checkmark.shield.fill" : "xmark.shield.fill")
                .foregroundStyle(ok ? Color.green : Color.red)
        }
    }
}
