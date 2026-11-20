import AppKit
import ArticulateCore

/// Spelling and grammar from macOS's built-in, on-device checker (AppleSpell).
///
/// AppleSpell runs as a local system service. It is optional (Settings → General) for users who
/// prefer that nothing outside this app's own sandboxed process sees their text.
@MainActor
enum SystemSpellChecker {
    private static let documentTag = NSSpellChecker.uniqueSpellDocumentTag()

    static func check(_ text: String, dialect: Dialect, spelling: Bool, grammar: Bool) -> [Issue] {
        guard spelling || grammar, !text.isEmpty else { return [] }
        let checker = NSSpellChecker.shared
        checker.automaticallyIdentifiesLanguages = false
        if !checker.setLanguage(dialect.appleSpellLanguage) {
            _ = checker.setLanguage("en")
        }

        var types: NSTextCheckingTypes = 0
        if spelling { types |= NSTextCheckingResult.CheckingType.spelling.rawValue }
        if grammar { types |= NSTextCheckingResult.CheckingType.grammar.rawValue }

        let ns = text as NSString
        let results = checker.check(
            text,
            range: NSRange(location: 0, length: ns.length),
            types: types,
            options: nil,
            inSpellDocumentWithTag: documentTag,
            orthography: nil,
            wordCount: nil
        )

        var issues: [Issue] = []
        for result in results {
            switch result.resultType {
            case .spelling:
                let word = ns.substring(with: result.range)
                let guesses = checker.guesses(
                    forWordRange: result.range,
                    in: text,
                    language: dialect.appleSpellLanguage,
                    inSpellDocumentWithTag: documentTag
                ) ?? []
                issues.append(Issue(
                    span: TextSpan(result.range),
                    original: word,
                    suggestions: Array(guesses.prefix(5)),
                    category: .spelling,
                    severity: .error,
                    message: guesses.isEmpty ? "Possible spelling mistake." : "Possible spelling mistake. Did you mean “\(guesses[0])”?",
                    ruleID: "system.spelling",
                    source: .spellChecker
                ))
            case .grammar:
                for detail in result.grammarDetails ?? [] {
                    guard let value = detail[NSGrammarRange] as? NSValue else { continue }
                    let local = value.rangeValue
                    let range = NSRange(location: result.range.location + local.location, length: local.length)
                    guard range.length > 0, range.location + range.length <= ns.length else { continue }
                    let description = detail[NSGrammarUserDescription] as? String ?? "Possible grammar problem."
                    let corrections = detail[NSGrammarCorrections] as? [String] ?? []
                    issues.append(Issue(
                        span: TextSpan(range),
                        original: ns.substring(with: range),
                        suggestions: Array(corrections.prefix(5)),
                        category: .grammar,
                        severity: .warning,
                        message: description,
                        ruleID: "system.grammar",
                        source: .spellChecker
                    ))
                }
            default:
                break
            }
        }
        return issues
    }
}
