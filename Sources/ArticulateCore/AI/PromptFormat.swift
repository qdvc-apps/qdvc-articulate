import Foundation

/// A prompt split into a stable prefix (system instructions — identical for every chunk, so its
/// KV cache can be reused) and a per-chunk body.
public struct RenderedPrompt: Hashable, Sendable {
    public let prefix: String
    public let body: String
}

/// Chat formats for common instruction-tuned GGUF families. We render prompts ourselves rather than
/// relying on llama.cpp's legacy template list, which doesn't cover newer families like Gemma 4.
/// BOS is added by the tokenizer, so it never appears here.
public enum PromptFormat: String, CaseIterable, Codable, Sendable, Identifiable {
    case automatic
    case gemma4
    case gemma
    case chatml
    case llama3
    case mistral
    case phi3
    case plain

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .automatic: return "Automatic"
        case .gemma4: return "Gemma 4"
        case .gemma: return "Gemma 2 / 3 / 3n"
        case .chatml: return "ChatML (Qwen, SmolLM, many others)"
        case .llama3: return "Llama 3"
        case .mistral: return "Mistral [INST]"
        case .phi3: return "Phi-3 / Phi-3.5"
        case .plain: return "Plain completion"
        }
    }

    /// Picks a format from the GGUF's embedded chat template and architecture name.
    public static func detect(chatTemplate: String?, architecture: String?) -> PromptFormat {
        if let t = chatTemplate {
            if t.contains("<|turn>") { return .gemma4 }
            if t.contains("<start_of_turn>") { return .gemma }
            if t.contains("<|start_header_id|>") { return .llama3 }
            if t.contains("<|im_start|>") { return .chatml }
            if t.contains("<|user|>") && t.contains("<|end|>") { return .phi3 }
            if t.contains("[INST]") { return .mistral }
        }
        let arch = (architecture ?? "").lowercased()
        if arch.hasPrefix("gemma4") { return .gemma4 }
        if arch.hasPrefix("gemma") { return .gemma }
        if arch.hasPrefix("llama") { return .llama3 }
        if arch.hasPrefix("qwen") || arch.hasPrefix("smollm") { return .chatml }
        if arch.hasPrefix("phi3") { return .phi3 }
        if arch.hasPrefix("mistral") { return .mistral }
        return .chatml
    }

    public func resolved(chatTemplate: String?, architecture: String?) -> PromptFormat {
        self == .automatic ? Self.detect(chatTemplate: chatTemplate, architecture: architecture) : self
    }

    /// - Parameters:
    ///   - system: instructions (stable across chunks)
    ///   - userLead: text that starts the user turn (stable, e.g. "TEXT:\n")
    ///   - userText: the passage to check
    public func render(system: String, userLead: String, userText: String) -> RenderedPrompt {
        switch self {
        case .gemma4:
            return RenderedPrompt(
                prefix: "<|turn>system\n\(system)<turn|>\n<|turn>user\n\(userLead)",
                body: "\(userText)<turn|>\n<|turn>model\n")
        case .gemma:
            // Gemma 2/3 have no system role: instructions go at the top of the first user turn.
            return RenderedPrompt(
                prefix: "<start_of_turn>user\n\(system)\n\n\(userLead)",
                body: "\(userText)<end_of_turn>\n<start_of_turn>model\n")
        case .chatml, .automatic:
            return RenderedPrompt(
                prefix: "<|im_start|>system\n\(system)<|im_end|>\n<|im_start|>user\n\(userLead)",
                body: "\(userText)<|im_end|>\n<|im_start|>assistant\n")
        case .llama3:
            return RenderedPrompt(
                prefix: "<|start_header_id|>system<|end_header_id|>\n\n\(system)<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n\(userLead)",
                body: "\(userText)<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n")
        case .mistral:
            return RenderedPrompt(
                prefix: "[INST] \(system)\n\n\(userLead)",
                body: "\(userText) [/INST]")
        case .phi3:
            return RenderedPrompt(
                prefix: "<|system|>\n\(system)<|end|>\n<|user|>\n\(userLead)",
                body: "\(userText)<|end|>\n<|assistant|>\n")
        case .plain:
            return RenderedPrompt(
                prefix: "\(system)\n\n\(userLead)",
                body: "\(userText)\n\nOUTPUT:\n")
        }
    }
}
