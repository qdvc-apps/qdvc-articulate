import Foundation

/// One raw suggestion as returned by the language model (before it is located in the text).
public struct LLMSuggestion: Codable, Hashable, Sendable {
    public var original: String
    public var replacement: String
    public var category: String
    public var explanation: String

    public init(original: String, replacement: String, category: String, explanation: String) {
        self.original = original
        self.replacement = replacement
        self.category = category
        self.explanation = explanation
    }

    private enum CodingKeys: String, CodingKey {
        case original, replacement, category, explanation
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        original = try c.decode(String.self, forKey: .original)
        replacement = (try? c.decodeIfPresent(String.self, forKey: .replacement)) ?? ""
        category = (try? c.decodeIfPresent(String.self, forKey: .category)) ?? "grammar"
        explanation = (try? c.decodeIfPresent(String.self, forKey: .explanation)) ?? ""
    }
}

public enum LLMResponseParser {
    private struct Envelope: Decodable {
        let issues: [LLMSuggestion]
    }

    /// Parses model output. Tolerates leading chatter, Markdown fences and output that was cut off
    /// by the token limit (keeps every complete issue object).
    public static func parse(_ raw: String) -> [LLMSuggestion] {
        guard let start = raw.firstIndex(where: { $0 == "{" || $0 == "[" }) else { return [] }
        let text = String(raw[start...])

        if text.first == "[" {
            if let array = decodeArray(text) { return array }
        }
        if let full = decodeEnvelope(text) { return full }

        // Repair truncated output: cut after the last complete object and close the array/object.
        var searchEnd = text.endIndex
        var attempts = 0
        while attempts < 64, let close = text[..<searchEnd].lastIndex(of: "}") {
            let head = String(text[...close])
            if let repaired = decodeEnvelope(head + "]}") { return repaired }
            if let repaired = decodeEnvelope(head) { return repaired }
            if head.first == "[", let repaired = decodeArray(head + "]") { return repaired }
            searchEnd = close
            attempts += 1
        }
        return []
    }

    private static func decodeEnvelope(_ s: String) -> [LLMSuggestion]? {
        try? JSONDecoder().decode(Envelope.self, from: Data(s.utf8)).issues
    }

    private static func decodeArray(_ s: String) -> [LLMSuggestion]? {
        try? JSONDecoder().decode([LLMSuggestion].self, from: Data(s.utf8))
    }
}
