import Foundation

public struct TextChunk: Hashable, Sendable {
    public let span: TextSpan
    public let text: String

    public init(span: TextSpan, text: String) {
        self.span = span
        self.text = text
    }
}

/// Splits a document into paragraph-based chunks for the language model.
///
/// Chunk boundaries depend only on local content, so editing one paragraph only invalidates the
/// cached result for that paragraph — re-checking a long document after a small edit is fast.
public enum TextChunker {
    /// Paragraphs shorter than this (headings, greetings) are merged with the following paragraph.
    public static let shortParagraphLength = 80

    public static func chunks(in text: String, maxLength: Int, excluding zones: [TextSpan] = []) -> [TextChunk] {
        let ns = NSString(string: text)
        let paragraphs = paragraphSpans(ns).filter { span in
            !zones.contains { $0.contains(span) }
        }

        // Merge short paragraphs forward.
        var groups: [TextSpan] = []
        var pending: TextSpan?
        for paragraph in paragraphs {
            if let p = pending {
                let merged = TextSpan(location: p.location, length: paragraph.upperBound - p.location)
                if paragraph.length < shortParagraphLength && merged.length < maxLength {
                    pending = merged
                } else {
                    groups.append(merged)
                    pending = nil
                }
            } else if paragraph.length < shortParagraphLength {
                pending = paragraph
            } else {
                groups.append(paragraph)
            }
        }
        if let p = pending { groups.append(p) }

        var result: [TextChunk] = []
        for group in groups {
            if group.length <= maxLength {
                append(group, ns: ns, to: &result)
            } else {
                splitBySentences(group, ns: ns, maxLength: maxLength, into: &result)
            }
        }
        return result
    }

    /// Paragraphs are separated by blank lines; leading/trailing whitespace is trimmed.
    static func paragraphSpans(_ ns: NSString) -> [TextSpan] {
        var spans: [TextSpan] = []
        let length = ns.length
        var start = 0
        var i = 0
        while i < length {
            if ns.character(at: i) == 0x0A {
                // Look ahead for a blank line (only whitespace until the next newline).
                var j = i + 1
                while j < length, ns.character(at: j) != 0x0A, UnitClass.isWhitespace(ns.character(at: j)) { j += 1 }
                if j < length && ns.character(at: j) == 0x0A {
                    if let span = trimmed(TextSpan(location: start, length: i - start), ns) { spans.append(span) }
                    // Skip all consecutive blank lines.
                    var k = j
                    while k < length, UnitClass.isWhitespace(ns.character(at: k)) { k += 1 }
                    start = k
                    i = k
                    continue
                }
            }
            i += 1
        }
        if let span = trimmed(TextSpan(location: start, length: length - start), ns) { spans.append(span) }
        return spans.filter { span in
            ns.substring(with: span.nsRange).contains(where: { $0.isLetter })
        }
    }

    private static func trimmed(_ span: TextSpan, _ ns: NSString) -> TextSpan? {
        guard span.length > 0 else { return nil }
        var s = span.location
        var e = span.upperBound
        while s < e, UnitClass.isWhitespace(ns.character(at: s)) { s += 1 }
        while e > s, UnitClass.isWhitespace(ns.character(at: e - 1)) { e -= 1 }
        return e > s ? TextSpan(location: s, length: e - s) : nil
    }

    private static func append(_ span: TextSpan, ns: NSString, to result: inout [TextChunk]) {
        result.append(TextChunk(span: span, text: ns.substring(with: span.nsRange)))
    }

    private static func splitBySentences(_ group: TextSpan, ns: NSString, maxLength: Int, into result: inout [TextChunk]) {
        let groupText = ns.substring(with: group.nsRange)
        let sentences = SentenceSplitter.sentences(in: groupText).map { $0.offset(by: group.location) }
        var start: Int?
        var end = group.location
        for sentence in sentences {
            if let s = start, sentence.upperBound - s > maxLength {
                append(TextSpan(location: s, length: end - s), ns: ns, to: &result)
                start = nil
            }
            if start == nil { start = sentence.location }
            end = sentence.upperBound
        }
        if let s = start, end > s {
            append(TextSpan(location: s, length: end - s), ns: ns, to: &result)
        }
    }
}
