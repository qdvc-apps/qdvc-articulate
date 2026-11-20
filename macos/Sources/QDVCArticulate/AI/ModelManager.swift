import Foundation
import ArticulateCore
import ArticulateLLM

/// Owns the single llama.cpp engine shared by all document windows.
@MainActor
final class ModelManager: ObservableObject {
    static let shared = ModelManager()

    enum State: Equatable {
        case notCompiledIn
        case noModel
        case loading(String)
        case ready(ModelInfo)
        case failed(String)
    }

    @Published private(set) var state: State

    let engine = LlamaEngine()
    let cache = ReviewCache()

    private var accessedURL: URL?
    private var loadTask: Task<Void, Never>?
    private var settings: SettingsStore { SettingsStore.shared }

    private init() {
        state = LlamaEngine.isAvailable ? .noModel : .notCompiledIn
    }

    var isReady: Bool {
        if case .ready = state { return true }
        return false
    }

    var info: ModelInfo? {
        if case .ready(let info) = state { return info }
        return nil
    }

    var resolvedFormat: PromptFormat? {
        guard let info else { return nil }
        return settings.llama.promptFormat.resolved(chatTemplate: info.chatTemplate, architecture: info.architecture)
    }

    var notReadyMessage: String {
        switch state {
        case .notCompiledIn:
            return "This build has no AI engine. Put llama.xcframework into Vendor/ and run scripts/build-app.sh again; it rebuilds from scratch when the framework has changed."
        case .noModel:
            return "No AI model selected. Choose a GGUF file in Settings → AI Model."
        case .loading:
            return "The AI model is still loading."
        case .failed(let message):
            return message
        case .ready:
            return ""
        }
    }

    // MARK: Selecting and loading

    /// Remembers a user-chosen GGUF via a security-scoped bookmark, then loads it.
    func setModel(url: URL) {
        let didAccess = url.startAccessingSecurityScopedResource()
        defer { if didAccess { url.stopAccessingSecurityScopedResource() } }
        do {
            let bookmark = try url.bookmarkData(
                options: [.withSecurityScope, .securityScopeAllowOnlyReadAccess],
                includingResourceValuesForKeys: nil,
                relativeTo: nil
            )
            settings.modelBookmark = bookmark
            settings.modelFileName = url.lastPathComponent
            load()
        } catch {
            state = .failed("Could not remember the model location: \(error.localizedDescription)")
        }
    }

    func load() {
        guard LlamaEngine.isAvailable else {
            state = .notCompiledIn
            return
        }
        guard let bookmark = settings.modelBookmark else {
            state = .noModel
            return
        }
        var isStale = false
        guard let url = try? URL(
            resolvingBookmarkData: bookmark,
            options: [.withSecurityScope],
            relativeTo: nil,
            bookmarkDataIsStale: &isStale
        ) else {
            state = .failed("The saved model file could not be found. Choose it again in Settings → AI Model.")
            return
        }

        releaseFileAccess()
        guard url.startAccessingSecurityScopedResource() else {
            state = .failed("macOS did not grant access to “\(url.lastPathComponent)”. Choose it again in Settings → AI Model.")
            return
        }
        accessedURL = url
        if isStale, let refreshed = try? url.bookmarkData(options: [.withSecurityScope, .securityScopeAllowOnlyReadAccess],
                                                          includingResourceValuesForKeys: nil, relativeTo: nil) {
            settings.modelBookmark = refreshed
        }

        let llama = settings.llama
        let config = LlamaConfig(
            contextLength: llama.contextLength,
            gpuLayers: llama.gpuLayers,
            threads: llama.threads,
            batchSize: 1024
        )
        let path = url.path
        state = .loading(url.lastPathComponent)
        loadTask?.cancel()
        loadTask = Task { [weak self] in
            guard let self else { return }
            do {
                let info = try await self.engine.load(path: path, config: config)
                await self.cache.removeAll()
                self.state = .ready(info)
            } catch {
                self.releaseFileAccess()
                self.state = .failed(error.localizedDescription)
            }
        }
    }

    func unload() {
        loadTask?.cancel()
        let engine = self.engine
        Task { await engine.unload() }
        releaseFileAccess()
        state = LlamaEngine.isAvailable ? .noModel : .notCompiledIn
    }

    /// Unloads the model and forgets the file.
    func forget() {
        unload()
        settings.modelBookmark = nil
        settings.modelFileName = nil
    }

    private func releaseFileAccess() {
        accessedURL?.stopAccessingSecurityScopedResource()
        accessedURL = nil
    }

    // MARK: Reviewing

    /// Applies sampling settings that don't need a reload.
    func prepareForReview() async {
        await engine.configure(temperature: settings.llama.temperature, reusePromptCache: settings.llama.reusePromptCache)
    }

    func review(text: String, settings check: CheckSettings) -> AsyncThrowingStream<ReviewProgress, Error>? {
        guard let info, let format = resolvedFormat else { return nil }
        let llama = settings.llama
        let options = AIReviewOptions(
            format: format,
            maxOutputTokens: llama.maxOutputTokens,
            maxChunkLength: llama.chunkLength,
            modelIdentifier: info.identifier
        )
        return AIReviewer(generator: engine, cache: cache).review(text: text, settings: check, options: options)
    }

    func clearCache() {
        let cache = self.cache
        Task { await cache.removeAll() }
    }
}
