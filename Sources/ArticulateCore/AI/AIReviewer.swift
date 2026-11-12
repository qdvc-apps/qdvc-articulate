import Foundation

/// Anything that can turn a prompt into text. Implemented by the llama.cpp engine; tests use a mock.
public protocol TextGenerating: Sendable {
    /// - Parameters:
    ///   - prefix: stable part of the prompt (may be served from a KV cache)
    ///   - body: per-request part of the prompt
    ///   - grammar: optional GBNF grammar constraining the output
    func generate(prefix: String, body: String, grammar: String?, maxTokens: Int) async throws -> String
}

public struct AIReviewOptions: Sendable {
    public var format: PromptFormat
    public var maxOutputTokens: Int
    public var maxChunkLength: Int
    public var modelIdentifier: String
    public var useGrammar: Bool

    public init(format: PromptFormat, maxOutputTokens: Int = 1024, maxChunkLength: Int = 1200, modelIdentifier: String, useGrammar: Bool = true) {
        self.format = format
        self.maxOutputTokens = maxOutputTokens
        self.maxChunkLength = maxChunkLength
        self.modelIdentifier = modelIdentifier
        self.useGrammar = useGrammar
    }
}

public struct ReviewProgress: Sendable {
    public let completed: Int
    public let total: Int
    /// The region of the snapshot that was just reviewed (in snapshot coordinates).
    public let chunkSpan: TextSpan
    /// Issues found in that region (in snapshot coordinates).
    public let issues: [Issue]
    public let fromCache: Bool
}

/// In-memory cache of model output per chunk. Never written to disk.
public actor ReviewCache {
    private var storage: [String: [LLMSuggestion]] = [:]
    private let limit: Int

    public init(limit: Int = 4000) {
        self.limit = limit
    }

    public func value(for key: String) -> [LLMSuggestion]? {
        storage[key]
    }

    public func store(_ value: [LLMSuggestion], for key: String) {
        if storage.count >= limit { storage.removeAll(keepingCapacity: true) }
        storage[key] = value
    }

    public func removeAll() {
        storage.removeAll()
    }
}

public struct AIReviewer: Sendable {
    public let generator: TextGenerating
    public let cache: ReviewCache

    public init(generator: TextGenerating, cache: ReviewCache) {
        self.generator = generator
        self.cache = cache
    }

    /// Reviews `text` chunk by chunk, yielding results as each chunk completes.
    public func review(text: String, settings: CheckSettings, options: AIReviewOptions) -> AsyncThrowingStream<ReviewProgress, Error> {
        let generator = self.generator
        let cache = self.cache
        return AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let zones = ExclusionZones.compute(in: text)
                    let chunks = TextChunker.chunks(in: text, maxLength: options.maxChunkLength, excluding: zones)
                    let builder = PromptBuilder(settings: settings)
                    let keyPrefix = "\(options.modelIdentifier)|\(options.format.rawValue)|\(settings.aiCacheKey)|"

                    for (index, chunk) in chunks.enumerated() {
                        try Task.checkCancellation()
                        let key = keyPrefix + chunk.text
                        var fromCache = true
                        let suggestions: [LLMSuggestion]
                        if let cached = await cache.value(for: key) {
                            suggestions = cached
                        } else {
                            fromCache = false
                            let prompt = builder.render(chunk: chunk.text, format: options.format)
                            let raw = try await generator.generate(
                                prefix: prompt.prefix,
                                body: prompt.body,
                                grammar: options.useGrammar ? JSONGrammar.issues : nil,
                                maxTokens: options.maxOutputTokens
                            )
                            suggestions = LLMResponseParser.parse(raw)
                            await cache.store(suggestions, for: key)
                        }
                        let issues = IssueAnchorer.anchor(suggestions, in: chunk, settings: settings)
                            .filter { !ExclusionZones.isExcluded($0.span, zones: zones) }
                        continuation.yield(ReviewProgress(
                            completed: index + 1,
                            total: chunks.count,
                            chunkSpan: chunk.span,
                            issues: issues,
                            fromCache: fromCache
                        ))
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
