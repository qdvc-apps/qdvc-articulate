import Foundation

public enum IssueAdjuster {
    /// Shifts issues after an edit. Issues that overlap or touch the edited range are dropped
    /// (the next check will re-evaluate that text), so underlines never sit on stale text.
    public static func adjust(_ issues: [Issue], editedSpan edit: TextSpan, replacementLength: Int) -> [Issue] {
        let delta = replacementLength - edit.length
        return issues.compactMap { issue in
            if issue.span.upperBound < edit.location {
                return issue
            }
            if issue.span.location > edit.upperBound {
                var shifted = issue
                shifted.span = issue.span.offset(by: delta)
                return shifted
            }
            return nil
        }
    }

    /// Transforms a span through an edit, growing/shrinking it if the edit happened inside it.
    /// Used for "this region was re-checked" bookkeeping, where dropping would be wrong.
    public static func transformRegion(_ span: TextSpan, editedSpan edit: TextSpan, replacementLength: Int) -> TextSpan {
        let delta = replacementLength - edit.length
        if span.upperBound <= edit.location { return span }
        if span.location >= edit.upperBound { return span.offset(by: delta) }
        let newStart = min(span.location, edit.location)
        let newEnd = max(span.upperBound + delta, edit.location + replacementLength)
        return TextSpan(location: newStart, length: max(0, newEnd - newStart))
    }
}

public enum IssueMerger {
    /// Validates, filters, de-duplicates and sorts issues from all sources.
    ///
    /// - Issues whose text no longer matches `original` are dropped (stale).
    /// - Ignored fingerprints, personal-dictionary words and excluded zones are removed.
    /// - Issues on the same span in the same group are merged (suggestions are combined).
    public static func merge(
        _ sources: [[Issue]],
        text: String,
        ignored: Set<String>,
        settings: CheckSettings,
        zones: [TextSpan]
    ) -> [Issue] {
        let dictionary = Set(settings.personalDictionary.map { $0.lowercased() })
        var indexByKey: [String: Int] = [:]
        var result: [Issue] = []

        for issue in sources.joined() {
            guard issue.span.length > 0, text.substring(in: issue.span) == issue.original else { continue }
            if ignored.contains(issue.fingerprint) { continue }
            if issue.category == .spelling && dictionary.contains(issue.original.lowercased()) { continue }
            if ExclusionZones.isExcluded(issue.span, zones: zones) { continue }

            let key = "\(issue.span.location):\(issue.span.length):\(issue.category.group.rawValue)"
            if let index = indexByKey[key] {
                var existing = result[index]
                for suggestion in issue.suggestions where !existing.suggestions.contains(suggestion) {
                    existing.suggestions.append(suggestion)
                }
                if issue.severity > existing.severity { existing.severity = issue.severity }
                result[index] = existing
                continue
            }
            indexByKey[key] = result.count
            result.append(issue)
        }

        return result.sorted { ($0.span.location, $0.span.length) < ($1.span.location, $1.span.length) }
    }
}
