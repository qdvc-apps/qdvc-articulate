import Foundation

/// Language models are poor at character offsets, so they quote the text instead.
/// The anchorer finds each quote in the chunk and turns it into a positioned `Issue`.
public enum IssueAnchorer {
    public static func anchor(_ suggestions: [LLMSuggestion], in chunk: TextChunk, settings: CheckSettings) -> [Issue] {
        let ns = NSString(string: chunk.text)
        let normalizedChunk = NSString(string: normalize(chunk.text))
        var cursor = 0
        var used = Set<TextSpan>()
        var issues: [Issue] = []

        for suggestion in suggestions {
            let original = suggestion.original
            guard !original.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  suggestion.replacement != original else { continue }
            if DialectLexicon.introducesDispreferredSpelling(suggestion.replacement, for: settings.dialect)
                && !DialectLexicon.introducesDispreferredSpelling(original, for: settings.dialect) {
                continue
            }
            guard let local = locate(original, in: ns, normalized: normalizedChunk, from: cursor, avoiding: used) else { continue }
            used.insert(local)
            cursor = local.location

            let actual = ns.substring(with: local.nsRange)
            let category = IssueCategory(looseName: suggestion.category) ?? .grammar
            let explanation = suggestion.explanation.trimmingCharacters(in: .whitespacesAndNewlines)
            issues.append(Issue(
                span: local.offset(by: chunk.span.location),
                original: actual,
                suggestions: [suggestion.replacement],
                category: category,
                message: explanation.isEmpty ? "Suggested by the AI model." : explanation,
                ruleID: "ai.\(category.rawValue)",
                source: .ai
            ))
        }
        return issues
    }

    static func locate(_ needle: String, in haystack: NSString, normalized: NSString, from cursor: Int, avoiding used: Set<TextSpan>) -> TextSpan? {
        let attempts: [(NSString, String, NSString.CompareOptions)] = [
            (haystack, needle, []),
            (haystack, needle, [.caseInsensitive]),
            (normalized, normalize(needle), [.caseInsensitive]),
        ]
        for (source, query, options) in attempts {
            for start in [cursor, 0] {
                if let span = search(query, in: source, from: start, options: options, avoiding: used) {
                    return span
                }
            }
        }
        return nil
    }

    private static func search(_ query: String, in source: NSString, from start: Int, options: NSString.CompareOptions, avoiding used: Set<TextSpan>) -> TextSpan? {
        var location = max(0, min(start, source.length))
        while location < source.length {
            let range = source.range(of: query, options: options, range: NSRange(location: location, length: source.length - location))
            if range.location == NSNotFound { return nil }
            let span = TextSpan(range)
            if !used.contains(span) { return span }
            location = range.location + 1
        }
        return nil
    }

    /// Length-preserving normalisation (every replacement is one UTF-16 unit for one UTF-16 unit),
    /// so offsets found in the normalised text are valid in the original.
    static func normalize(_ s: String) -> String {
        var units = Array(s.utf16)
        for i in units.indices {
            switch units[i] {
            case 0x2018, 0x2019, 0x02BC: units[i] = 0x27   // ‘ ’ ʼ → '
            case 0x201C, 0x201D: units[i] = 0x22           // “ ” → "
            case 0x00A0, 0x2009, 0x202F: units[i] = 0x20   // non-breaking / thin spaces
            case 0x2013, 0x2014: units[i] = 0x2D           // – — → -
            default: break
            }
        }
        return String(decoding: units, as: UTF16.self)
    }
}
