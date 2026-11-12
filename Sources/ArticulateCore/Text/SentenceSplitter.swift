import Foundation

/// Lightweight, portable sentence segmentation (no NaturalLanguage framework, so it also runs on Linux).
public enum SentenceSplitter {
    /// Sentence-ending punctuation followed by whitespace and a likely sentence start, or a line break.
    private static let boundary = RX.make(#"[.!?…]+["'”’)\]]*(?=\s+["'“‘(\[]?[\p{Lu}\p{N}])|\n+"#)

    static let abbreviations: Set<String> = [
        "e.g", "i.e", "etc", "vs", "cf", "approx", "incl", "excl", "a.m", "p.m", "mr", "mrs", "ms", "dr",
        "prof", "st", "no", "nos", "vol", "fig", "figs", "al", "ca", "est", "dept", "jr", "sr", "inc", "ltd",
        "co", "corp", "min", "max", "sec", "hr", "hrs", "mins", "pp", "p", "ed", "eds", "viz", "resp", "ibid",
        "op", "cit", "misc", "govt", "univ", "gen", "col", "lt", "sgt", "capt", "rev", "hon", "u.s", "u.k",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "mt", "ft",
    ]

    /// Returns trimmed sentence spans (UTF-16) in document order.
    public static func sentences(in text: String) -> [TextSpan] {
        let ns = NSString(string: text)
        var spans: [TextSpan] = []
        var start = 0
        for match in boundary.matches(in: text, range: NSRange(location: 0, length: ns.length)) {
            let firstUnit = ns.character(at: match.range.location)
            if firstUnit != 0x0A && endsWithAbbreviation(ns, before: match.range.location) {
                continue
            }
            let end = match.range.location + match.range.length
            append(TextSpan(location: start, length: end - start), from: ns, to: &spans)
            start = end
        }
        append(TextSpan(location: start, length: ns.length - start), from: ns, to: &spans)
        return spans
    }

    /// The word immediately before `index` (letters and inner dots), lowercased, without trailing dots.
    static func wordBefore(_ ns: NSString, index: Int) -> String {
        var i = index - 1
        while i >= 0 {
            let u = ns.character(at: i)
            if UnitClass.isLetter(u) || u == 0x2E { i -= 1 } else { break }
        }
        let start = i + 1
        guard start < index else { return "" }
        var word = ns.substring(with: NSRange(location: start, length: index - start)).lowercased()
        while word.hasSuffix(".") { word.removeLast() }
        while word.hasPrefix(".") { word.removeFirst() }
        return word
    }

    static func endsWithAbbreviation(_ ns: NSString, before index: Int) -> Bool {
        guard ns.character(at: index) == 0x2E else { return false } // only "." can follow an abbreviation
        let word = wordBefore(ns, index: index)
        if word.isEmpty { return false }
        if abbreviations.contains(word) { return true }
        // Single capital letter = an initial ("J. Smith").
        if word.count == 1, index > 0, let scalar = Unicode.Scalar(ns.character(at: index - 1)),
           scalar.properties.isUppercase {
            return true
        }
        return false
    }

    private static func append(_ span: TextSpan, from ns: NSString, to spans: inout [TextSpan]) {
        var s = span.location
        var e = span.upperBound
        while s < e, UnitClass.isWhitespace(ns.character(at: s)) { s += 1 }
        while e > s, UnitClass.isWhitespace(ns.character(at: e - 1)) { e -= 1 }
        if e > s { spans.append(TextSpan(location: s, length: e - s)) }
    }
}
