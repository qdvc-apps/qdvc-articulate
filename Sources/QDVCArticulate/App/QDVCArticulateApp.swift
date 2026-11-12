import SwiftUI
import AppKit
import ArticulateCore

@main
struct QDVCArticulateApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var settings = SettingsStore.shared
    @StateObject private var models = ModelManager.shared

    var body: some Scene {
        DocumentGroup(newDocument: TextDocument()) { file in
            EditorWindow(document: file.$document)
                .environmentObject(settings)
                .environmentObject(models)
        }
        .commands {
            ArticulateCommands()
        }

        Settings {
            SettingsView()
                .environmentObject(settings)
                .environmentObject(models)
        }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        if SettingsStore.shared.llama.loadAtLaunch {
            ModelManager.shared.load()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        ModelManager.shared.unload()
    }
}

// MARK: - Menu commands

struct EditorControllerKey: FocusedValueKey {
    typealias Value = EditorController
}

extension FocusedValues {
    var editorController: EditorController? {
        get { self[EditorControllerKey.self] }
        set { self[EditorControllerKey.self] = newValue }
    }
}

struct ArticulateCommands: Commands {
    @FocusedValue(\.editorController) private var controller

    var body: some Commands {
        CommandGroup(after: .importExport) {
            Button("Import Word, RTF or ODT…") {
                controller?.importRequested = true
            }
            .keyboardShortcut("i", modifiers: [.command, .shift])
            .disabled(controller == nil)
        }

        CommandMenu("Check") {
            Button("Check with AI") {
                controller?.runAICheck()
            }
            .keyboardShortcut("k", modifiers: [.command, .shift])
            .disabled(controller == nil)

            Button("Stop AI Check") {
                controller?.cancelAICheck()
            }
            .keyboardShortcut(".", modifiers: [.command])
            .disabled(controller == nil)

            Divider()

            Button("Next Issue") {
                controller?.selectNextIssue()
            }
            .keyboardShortcut(.downArrow, modifiers: [.command, .option])
            .disabled(controller == nil)

            Button("Previous Issue") {
                controller?.selectPreviousIssue()
            }
            .keyboardShortcut(.upArrow, modifiers: [.command, .option])
            .disabled(controller == nil)

            Button("Accept Suggestion") {
                controller?.applyFocusedSuggestion()
            }
            .keyboardShortcut(.return, modifiers: [.command, .option])
            .disabled(controller == nil)

            Button("Ignore Issue") {
                controller?.ignoreFocusedIssue()
            }
            .keyboardShortcut(.delete, modifiers: [.command, .option])
            .disabled(controller == nil)

            Divider()

            Button("Restore Ignored Issues") {
                controller?.clearIgnored()
            }
            .disabled(controller == nil)
        }
    }
}
