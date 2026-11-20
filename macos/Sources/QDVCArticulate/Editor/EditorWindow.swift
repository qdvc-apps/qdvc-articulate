import SwiftUI
import ArticulateCore

struct EditorWindow: View {
    @Binding var document: TextDocument
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var models: ModelManager
    @StateObject private var controller = EditorController()
    @State private var showInspector = true
    @State private var isolation = IsolationChecker.staticReport()
    @State private var importError: String?
    @Environment(\.newDocument) private var newDocument

    var body: some View {
        VStack(spacing: 0) {
            if !isolation.isIsolated {
                IsolationBanner()
            }
            EditorTextView(
                text: $document.text,
                controller: controller,
                fontSize: settings.editorFontSize,
                monospaced: settings.useMonospacedFont
            )
            Divider()
            StatusBar(controller: controller, isolated: isolation.isIsolated)
        }
        .frame(minWidth: 520, minHeight: 360)
        .inspector(isPresented: $showInspector) {
            IssueListView(controller: controller)
                .inspectorColumnWidth(min: 280, ideal: 340, max: 520)
        }
        .toolbar {
            ToolbarItemGroup(placement: .primaryAction) {
                GoalsMenu()

                if case .running = controller.aiState {
                    Button {
                        controller.cancelAICheck()
                    } label: {
                        Label("Stop", systemImage: "stop.circle")
                    }
                    .help("Stop the AI review (⌘.)")
                } else {
                    Button {
                        controller.runAICheck()
                    } label: {
                        Label("Check with AI", systemImage: "sparkles")
                    }
                    .help(models.isReady ? "Review the document with the local AI model (⇧⌘K)" : models.notReadyMessage)
                }

                Button {
                    showInspector.toggle()
                } label: {
                    Label("Issues", systemImage: "sidebar.right")
                }
                .help("Show or hide the issue list")
            }
        }
        .fileImporter(
            isPresented: $controller.importRequested,
            allowedContentTypes: DocumentImporter.importableTypes
        ) { result in
            handleImport(result)
        }
        .alert("Import failed", isPresented: Binding(get: { importError != nil }, set: { if !$0 { importError = nil } })) {
            Button("OK", role: .cancel) { importError = nil }
        } message: {
            Text(importError ?? "")
        }
        .focusedSceneValue(\.editorController, controller)
        .onAppear {
            controller.attach()
        }
    }

    private func handleImport(_ result: Result<URL, Error>) {
        switch result {
        case .success(let url):
            let didAccess = url.startAccessingSecurityScopedResource()
            defer { if didAccess { url.stopAccessingSecurityScopedResource() } }
            do {
                let text = try DocumentImporter.importText(from: url)
                newDocument(TextDocument(text: text))
            } catch {
                importError = error.localizedDescription
            }
        case .failure(let error):
            importError = error.localizedDescription
        }
    }
}

/// Toolbar menu for dialect and writing goals.
private struct GoalsMenu: View {
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        Menu {
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
        } label: {
            Label("Goals", systemImage: "target")
        }
        .help("Variety of English and writing goals")
    }
}

/// Shown when the build is not sandboxed (e.g. launched with `swift run`).
private struct IsolationBanner: View {
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.shield.fill")
            Text("Network isolation is not enforced for this build. Use scripts/build-app.sh for the sandboxed app.")
            Spacer()
            SettingsLink { Text("Details") }
        }
        .font(.callout)
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.orange.opacity(0.18))
    }
}
