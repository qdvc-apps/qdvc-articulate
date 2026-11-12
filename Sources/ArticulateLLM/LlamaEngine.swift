import Foundation
import ArticulateCore
#if QDVC_LLAMA
import llama
#endif

public struct LlamaConfig: Sendable, Equatable {
    public var contextLength: Int = 8192
    /// Layers to offload to the GPU (Metal). 99 = all, 0 = CPU only.
    public var gpuLayers: Int = 99
    /// 0 = automatic.
    public var threads: Int = 0
    public var batchSize: Int = 1024

    public init(contextLength: Int = 8192, gpuLayers: Int = 99, threads: Int = 0, batchSize: Int = 1024) {
        self.contextLength = contextLength
        self.gpuLayers = gpuLayers
        self.threads = threads
        self.batchSize = batchSize
    }
}

public struct ModelInfo: Sendable, Equatable {
    public var fileName: String
    public var description: String
    public var architecture: String?
    public var chatTemplate: String?
    public var sizeBytes: UInt64
    public var parameterCount: UInt64
    public var trainedContextLength: Int
    public var contextLength: Int

    /// Stable identifier used to key the review cache.
    public var identifier: String { "\(fileName)#\(sizeBytes)" }
}

public enum LlamaError: LocalizedError {
    case notCompiledIn
    case noModelLoaded
    case loadFailed(String)
    case contextFailed
    case tokenizeFailed
    case grammarFailed
    case decodeFailed(Int32)
    case promptTooLong(tokens: Int, limit: Int)

    public var errorDescription: String? {
        switch self {
        case .notCompiledIn:
            return "This build does not include llama.cpp. Put llama.xcframework into Vendor/ and run scripts/build-app.sh again (see README)."
        case .noModelLoaded:
            return "No model is loaded."
        case .loadFailed(let file):
            return "Could not load “\(file)”. Make sure it is a GGUF model supported by your llama.cpp version."
        case .contextFailed:
            return "Could not create an inference context. Try a smaller context length in Settings → AI Model."
        case .tokenizeFailed:
            return "Tokenisation failed."
        case .grammarFailed:
            return "The output grammar could not be initialised."
        case .decodeFailed(let code):
            return "The model failed while processing text (llama_decode returned \(code))."
        case .promptTooLong(let tokens, let limit):
            return "A paragraph is too long for the context window (\(tokens) tokens, limit \(limit)). Increase the context length or reduce the chunk size."
        }
    }
}

/// Thread-safe wrapper around one llama.cpp model + context.
///
/// Privacy: llama.cpp is used purely as a local library. The app never calls any llama.cpp
/// download or server functionality, and the App Sandbox denies the process all network access.
public actor LlamaEngine: TextGenerating {
    public static var isAvailable: Bool {
        #if QDVC_LLAMA
        return true
        #else
        return false
        #endif
    }

    public private(set) var modelInfo: ModelInfo?

    private var temperature: Float = 0
    private var reusePrefix = true

    public init() {}

    /// Sampling options that can change without reloading the model.
    public func configure(temperature: Double, reusePromptCache: Bool) {
        self.temperature = Float(max(0, temperature))
        self.reusePrefix = reusePromptCache
    }

    #if QDVC_LLAMA

    private var model: OpaquePointer?
    private var context: OpaquePointer?
    private var vocab: OpaquePointer?
    private var batchSize = 512
    /// Tokens of the prompt prefix currently held in the KV cache (sequence 0).
    private var cachedPrefix: [llama_token] = []

    private static let backendInitialised: Bool = {
        llama_log_set({ _, _, _ in }, nil) // keep llama.cpp quiet
        llama_backend_init()
        return true
    }()

    public func load(path: String, config: LlamaConfig) throws -> ModelInfo {
        _ = Self.backendInitialised
        unload()

        var modelParams = llama_model_default_params()
        modelParams.n_gpu_layers = Int32(config.gpuLayers)
        modelParams.use_mmap = true

        let fileName = (path as NSString).lastPathComponent
        guard let loadedModel = llama_model_load_from_file(path, modelParams) else {
            throw LlamaError.loadFailed(fileName)
        }

        var contextParams = llama_context_default_params()
        let threads = config.threads > 0 ? config.threads : max(1, ProcessInfo.processInfo.activeProcessorCount - 2)
        contextParams.n_ctx = UInt32(config.contextLength)
        contextParams.n_batch = UInt32(config.batchSize)
        contextParams.n_ubatch = UInt32(min(config.batchSize, 512))
        contextParams.n_threads = Int32(threads)
        contextParams.n_threads_batch = Int32(threads)
        // Keep the full sliding-window cache so the reusable prompt prefix stays valid (Gemma etc.).
        contextParams.swa_full = true

        guard let loadedContext = llama_init_from_model(loadedModel, contextParams) else {
            llama_model_free(loadedModel)
            throw LlamaError.contextFailed
        }

        model = loadedModel
        context = loadedContext
        vocab = llama_model_get_vocab(loadedModel)
        batchSize = config.batchSize
        cachedPrefix = []

        let info = ModelInfo(
            fileName: fileName,
            description: metadata { buffer, size in llama_model_desc(loadedModel, buffer, size) } ?? fileName,
            architecture: metadata { buffer, size in llama_model_meta_val_str(loadedModel, "general.architecture", buffer, size) },
            chatTemplate: llama_model_chat_template(loadedModel, nil).map { String(cString: $0) },
            sizeBytes: llama_model_size(loadedModel),
            parameterCount: llama_model_n_params(loadedModel),
            trainedContextLength: Int(llama_model_n_ctx_train(loadedModel)),
            contextLength: Int(llama_n_ctx(loadedContext))
        )
        modelInfo = info
        return info
    }

    public func unload() {
        if let context { llama_free(context) }
        if let model { llama_model_free(model) }
        context = nil
        model = nil
        vocab = nil
        cachedPrefix = []
        modelInfo = nil
    }

    public func generate(prefix: String, body: String, grammar: String?, maxTokens: Int) async throws -> String {
        guard let context, let vocab else { throw LlamaError.noModelLoaded }

        let prefixTokens = try tokenize(prefix, addSpecial: true)
        let bodyTokens = try tokenize(body, addSpecial: false)
        let limit = Int(llama_n_ctx(context))
        let needed = prefixTokens.count + bodyTokens.count + maxTokens
        guard needed <= limit else {
            throw LlamaError.promptTooLong(tokens: prefixTokens.count + bodyTokens.count, limit: limit - maxTokens)
        }

        // Reuse the KV cache for the (identical) instruction prefix when possible.
        let memory = llama_get_memory(context)
        var reused = false
        if reusePrefix, !cachedPrefix.isEmpty, cachedPrefix == prefixTokens {
            reused = llama_memory_seq_rm(memory, 0, Int32(prefixTokens.count), -1)
        }
        if !reused {
            llama_memory_clear(memory, true)
            cachedPrefix = []
            try decode(prefixTokens)
            cachedPrefix = prefixTokens
        }
        do {
            try decode(bodyTokens)
        } catch {
            cachedPrefix = []
            throw error
        }

        // Sampler chain: grammar constraint first, then greedy or temperature sampling.
        let chain = llama_sampler_chain_init(llama_sampler_chain_default_params())
        defer { llama_sampler_free(chain) }
        if let grammar {
            guard let grammarSampler = llama_sampler_init_grammar(vocab, grammar, "root") else {
                throw LlamaError.grammarFailed
            }
            llama_sampler_chain_add(chain, grammarSampler)
        }
        if temperature <= 0.001 {
            llama_sampler_chain_add(chain, llama_sampler_init_greedy())
        } else {
            llama_sampler_chain_add(chain, llama_sampler_init_top_k(40))
            llama_sampler_chain_add(chain, llama_sampler_init_top_p(0.95, 1))
            llama_sampler_chain_add(chain, llama_sampler_init_temp(temperature))
            llama_sampler_chain_add(chain, llama_sampler_init_dist(UInt32.random(in: 0...UInt32.max)))
        }

        var output: [UInt8] = []
        var generated = 0
        while generated < maxTokens {
            if Task.isCancelled {
                cachedPrefix = []
                throw CancellationError()
            }
            let token = llama_sampler_sample(chain, context, -1)
            if llama_vocab_is_eog(vocab, token) { break }
            output.append(contentsOf: piece(token))
            var next = token
            let rc = withUnsafeMutablePointer(to: &next) { pointer in
                llama_decode(context, llama_batch_get_one(pointer, 1))
            }
            if rc != 0 {
                cachedPrefix = []
                throw LlamaError.decodeFailed(rc)
            }
            generated += 1
            // Note: deliberately no `await` inside this method. With no suspension points the actor
            // cannot interleave two generations on the same llama.cpp context.
        }
        return String(decoding: output, as: UTF8.self)
    }

    // MARK: Helpers

    private func tokenize(_ text: String, addSpecial: Bool) throws -> [llama_token] {
        guard let vocab else { throw LlamaError.noModelLoaded }
        let byteCount = Int32(text.utf8.count)
        var tokens = [llama_token](repeating: 0, count: Int(byteCount) + 16)
        var count = llama_tokenize(vocab, text, byteCount, &tokens, Int32(tokens.count), addSpecial, true)
        if count < 0 {
            tokens = [llama_token](repeating: 0, count: Int(-count))
            count = llama_tokenize(vocab, text, byteCount, &tokens, Int32(tokens.count), addSpecial, true)
        }
        guard count >= 0 else { throw LlamaError.tokenizeFailed }
        return Array(tokens.prefix(Int(count)))
    }

    private func decode(_ tokens: [llama_token]) throws {
        guard let context else { throw LlamaError.noModelLoaded }
        var buffer = tokens
        var start = 0
        while start < buffer.count {
            let count = min(batchSize, buffer.count - start)
            let offset = start
            let rc = buffer.withUnsafeMutableBufferPointer { pointer -> Int32 in
                llama_decode(context, llama_batch_get_one(pointer.baseAddress! + offset, Int32(count)))
            }
            if rc != 0 { throw LlamaError.decodeFailed(rc) }
            start += count
        }
    }

    private func piece(_ token: llama_token) -> [UInt8] {
        guard let vocab else { return [] }
        var buffer = [CChar](repeating: 0, count: 64)
        var n = llama_token_to_piece(vocab, token, &buffer, Int32(buffer.count), 0, false)
        if n < 0 {
            buffer = [CChar](repeating: 0, count: Int(-n))
            n = llama_token_to_piece(vocab, token, &buffer, Int32(buffer.count), 0, false)
        }
        guard n > 0 else { return [] }
        return buffer.prefix(Int(n)).map { UInt8(bitPattern: $0) }
    }

    /// Reads a C string from a llama.cpp "fill this buffer" style function.
    private func metadata(_ read: (UnsafeMutablePointer<CChar>, Int) -> Int32) -> String? {
        var buffer = [CChar](repeating: 0, count: 512)
        var n = buffer.withUnsafeMutableBufferPointer { read($0.baseAddress!, $0.count) }
        if n < 0 { return nil }
        if Int(n) >= buffer.count {
            buffer = [CChar](repeating: 0, count: Int(n) + 1)
            n = buffer.withUnsafeMutableBufferPointer { read($0.baseAddress!, $0.count) }
            if n < 0 { return nil }
        }
        return String(cString: buffer)
    }

    #else

    // Stub used when Package.swift did not find Vendor/llama.xcframework (QDVC_LLAMA undefined),
    // and on platforms without llama.cpp yet.

    public func load(path: String, config: LlamaConfig) throws -> ModelInfo {
        throw LlamaError.notCompiledIn
    }

    public func unload() {
        modelInfo = nil
    }

    public func generate(prefix: String, body: String, grammar: String?, maxTokens: Int) async throws -> String {
        throw LlamaError.notCompiledIn
    }

    #endif
}
