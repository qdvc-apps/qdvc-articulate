import Foundation

/// One entry of a phrase-based rule: a pattern plus replacement templates.
/// Replacement templates may reference capture groups as `$1`…`$3`. An empty replacement means "delete".
struct PhraseEntry: Sendable {
    let pattern: String
    let replacements: [String]
    let message: String
    let category: IssueCategory?
    let severity: IssueSeverity?
    let caseInsensitive: Bool

    /// A literal phrase. Spaces match any run of whitespace; apostrophes match ' and ’.
    static func phrase(
        _ phrase: String,
        _ replacements: [String],
        _ message: String,
        category: IssueCategory? = nil,
        severity: IssueSeverity? = nil
    ) -> PhraseEntry {
        PhraseEntry(
            pattern: literalPattern(phrase),
            replacements: replacements,
            message: message,
            category: category,
            severity: severity,
            caseInsensitive: true
        )
    }

    static func regex(
        _ pattern: String,
        _ replacements: [String],
        _ message: String,
        category: IssueCategory? = nil,
        severity: IssueSeverity? = nil,
        caseInsensitive: Bool = true
    ) -> PhraseEntry {
        PhraseEntry(
            pattern: pattern,
            replacements: replacements,
            message: message,
            category: category,
            severity: severity,
            caseInsensitive: caseInsensitive
        )
    }

    static func literalPattern(_ phrase: String) -> String {
        let words = phrase.split(separator: " ").map { word -> String in
            NSRegularExpression.escapedPattern(for: String(word))
                .replacingOccurrences(of: "'", with: "['’]")
        }
        var pattern = words.joined(separator: #"\s+"#)
        if let first = phrase.first, first.isLetter || first.isNumber { pattern = #"\b"# + pattern }
        if let last = phrase.last, last.isLetter || last.isNumber { pattern += #"\b"# }
        return pattern
    }
}

struct PhraseListRule: Rule {
    struct Compiled: @unchecked Sendable {
        let regex: NSRegularExpression
        let entry: PhraseEntry
    }

    let info: RuleInfo
    let compiled: [Compiled]

    init(info: RuleInfo, entries: [PhraseEntry]) {
        self.info = info
        self.compiled = entries.map { Compiled(regex: RX.make($0.pattern, caseInsensitive: $0.caseInsensitive), entry: $0) }
    }

    func check(_ context: RuleContext) -> [Issue] {
        var issues: [Issue] = []
        for item in compiled {
            for match in item.regex.matches(in: context.text, range: context.fullRange) {
                if let issue = makeIssue(for: match, entry: item.entry, in: context) {
                    issues.append(issue)
                }
            }
        }
        return issues
    }

    private func makeIssue(for match: NSTextCheckingResult, entry: PhraseEntry, in context: RuleContext) -> Issue? {
        var range = match.range
        let original = context.substring(range)
        var replacements = entry.replacements.map { template -> String in
            CaseStyle.match(Self.expand(template, match: match, context: context), to: original)
        }

        // Deleting a phrase should also delete one adjacent run of spaces.
        if replacements.contains("") {
            var end = range.location + range.length
            while let u = context.character(at: end), u == 0x20 || u == 0x09 { end += 1 }
            if end > range.location + range.length {
                let trailing = context.substring(NSRange(location: range.location + range.length, length: end - range.location - range.length))
                range = NSRange(location: range.location, length: end - range.location)
                replacements = replacements.map { $0.isEmpty ? "" : $0 + trailing }
            } else {
                var start = range.location
                while let u = context.character(at: start - 1), u == 0x20 || u == 0x09 { start -= 1 }
                if start < range.location {
                    let leading = context.substring(NSRange(location: start, length: range.location - start))
                    range = NSRange(location: start, length: range.location + range.length - start)
                    replacements = replacements.map { $0.isEmpty ? "" : leading + $0 }
                }
            }
        }

        let fullOriginal = context.substring(range)
        let filtered = replacements.filter { $0 != fullOriginal }
        if !entry.replacements.isEmpty && filtered.isEmpty { return nil }

        return Issue(
            span: TextSpan(range),
            original: fullOriginal,
            suggestions: filtered,
            category: entry.category ?? info.category,
            severity: entry.severity,
            message: entry.message,
            ruleID: info.id,
            source: .rules
        )
    }

    static func expand(_ template: String, match: NSTextCheckingResult, context: RuleContext) -> String {
        guard template.contains("$") else { return template }
        var result = template
        for group in stride(from: min(match.numberOfRanges - 1, 3), through: 1, by: -1) {
            let r = match.range(at: group)
            let value = r.location == NSNotFound ? "" : context.substring(r)
            result = result.replacingOccurrences(of: "$\(group)", with: value)
        }
        return result
    }
}
