import Foundation

enum BuiltInRules {
    static let all: [Rule] = [
        RepeatedWordRule(),
        ArticleRule(),
        PhraseListRule(
            info: RuleInfo(id: "common-errors", name: "Common mistakes",
                           summary: "“could of”, “more then”, “should have went”, mixed-up idioms and similar.",
                           category: .grammar),
            entries: PhraseData.commonErrors),
        SentenceCapitalizationRule(),
        LowercaseIRule(),
        ProperNounRule(),
        DialectSpellingRule(),
        MultipleSpacesRule(),
        SpaceBeforePunctuationRule(),
        MissingSpaceRule(),
        PhraseListRule(
            info: RuleInfo(id: "double-punctuation", name: "Repeated punctuation",
                           summary: "“..”, “,,”, “!!” and similar.", category: .punctuation),
            entries: PhraseData.doublePunctuation),
        UnbalancedPairsRule(),
        PhraseListRule(
            info: RuleInfo(id: "wordiness", name: "Wordy phrases",
                           summary: "“in order to” → “to”, “due to the fact that” → “because”.", category: .concision),
            entries: PhraseData.wordiness),
        PhraseListRule(
            info: RuleInfo(id: "redundancy", name: "Redundant phrases",
                           summary: "“end result”, “revert back”, “PIN number”.", category: .concision),
            entries: PhraseData.redundancy),
        PhraseListRule(
            info: RuleInfo(id: "intensifiers", name: "Weak intensifiers",
                           summary: "“very good” → “excellent”.", category: .wordChoice),
            entries: PhraseData.intensifiers),
        PhraseListRule(
            info: RuleInfo(id: "cliches", name: "Clichés",
                           summary: "“at the end of the day”, “think outside the box”.", category: .style),
            entries: PhraseData.cliches),
        PassiveVoiceRule(),
        LongSentenceRule(),
        FormalityRule(),
        PhraseListRule(
            info: RuleInfo(id: "fillers", name: "Filler words",
                           summary: "“basically”, “actually”, “literally”.", category: .concision, defaultEnabled: false),
            entries: PhraseData.fillers),
        PhraseListRule(
            info: RuleInfo(id: "inclusive-language", name: "Inclusive language",
                           summary: "“chairman” → “chair”, “manpower” → “workforce”.", category: .tone, defaultEnabled: false),
            entries: PhraseData.inclusive),
        PhraseListRule(
            info: RuleInfo(id: "smart-typography", name: "Typographic dashes and ellipses",
                           summary: "“--” → “—”, “...” → “…”.", category: .typography, defaultEnabled: false),
            entries: PhraseData.smartTypography),
    ]
}

// MARK: - Repeated words

struct RepeatedWordRule: Rule {
    let info = RuleInfo(id: "repeated-word", name: "Repeated words",
                        summary: "Accidental duplicates such as “the the”.", category: .grammar)

    private static let pattern = RX.make(#"\b(\p{L}+)(?:[ \t]+|[ \t]*\n[ \t]*)(\1)\b"#, caseInsensitive: true)
    private static let allowed: Set<String> = [
        "had", "that", "bye", "ha", "no", "so", "very", "really", "knock", "tut", "chop", "bang", "hush", "aye",
        "pom", "dum", "la", "na", "boo", "yeah", "well", "now", "there", "pretty", "far", "is",
    ]

    func check(_ context: RuleContext) -> [Issue] {
        Self.pattern.matches(in: context.text, range: context.fullRange).compactMap { match in
            let first = context.substring(match.range(at: 1))
            guard !Self.allowed.contains(first.lowercased()) else { return nil }
            return makeIssue(match.range, in: context, suggestions: [first], message: "Repeated word “\(first)”.")
        }
    }
}

// MARK: - a / an

struct ArticleRule: Rule {
    let info = RuleInfo(id: "a-an", name: "“a” vs “an”",
                        summary: "Uses the sound of the next word, including acronyms and numbers.", category: .grammar)

    private static let pattern = RX.make(#"\b(an?|An?)[ \t]+([\p{L}\p{N}][\p{L}\p{N}'’\-.]*)"#)

    private static let silentH = ["hour", "honest", "honor", "honour", "heir"]
    private static let consonantSoundPrefixes = [
        "unanim", "unary", "unesco", "use", "usu", "usag", "uti", "ute", "uto", "ura", "uri", "ure", "uro",
        "euro", "eu", "ewe", "ouija", "uk", "ubiq", "uvula", "u-",
    ]
    private static let wordLikeAcronyms: Set<String> = ["nasa", "nato", "nafta", "unesco", "unicef", "opec", "laser", "radar", "scuba", "lan", "wan", "pin", "gif", "asap"]
    private static let ambiguous: Set<String> = ["faq", "sql", "herb", "herbs", "herbal"]

    /// true = "an", false = "a", nil = unsure (don't flag).
    static func expectsAn(_ rawWord: String) -> Bool? {
        var word = rawWord
        while let last = word.last, !(last.isLetter || last.isNumber) { word.removeLast() }
        guard let first = word.first else { return nil }
        let lower = word.lowercased()
        if ambiguous.contains(lower) || lower.hasPrefix("herb") { return nil }

        if first.isNumber {
            let digits = word.prefix { $0.isNumber || $0 == "," }.filter { $0 != "," }
            if digits.hasPrefix("8") { return true }
            if digits == "11" || digits == "18" { return true }
            return false
        }

        let letters = word.filter { $0.isLetter }
        let isAcronym = letters.count >= 2 && letters.count <= 5
            && letters.allSatisfy({ $0.isUppercase }) && !wordLikeAcronyms.contains(letters.lowercased())
        let isSingleLetter = letters.count == 1 && (word.count == 1 || word.dropFirst().first == "-")
        if isAcronym || isSingleLetter {
            // Letter names that start with a vowel sound: A E F H I L M N O R S X.
            return "aefhilmnorsx".contains(String(first).lowercased())
        }

        if silentH.contains(where: { lower.hasPrefix($0) }) { return true }
        if lower == "one" || lower == "once" || lower.hasPrefix("one-") { return false }
        if consonantSoundPrefixes.contains(where: { lower.hasPrefix($0) }) { return false }
        if lower.hasPrefix("uni") {
            // "unicorn", "unit", "universal" (you-) vs "unimportant", "uninformed", "unidentified" (un-).
            let chars = Array(lower)
            if chars.count > 3, "mnd".contains(chars[3]) { return true }
            return false
        }
        return "aeiou".contains(String(first).lowercased())
    }

    func check(_ context: RuleContext) -> [Issue] {
        var issues: [Issue] = []
        for match in Self.pattern.matches(in: context.text, range: context.fullRange) {
            let articleRange = match.range(at: 1)
            let article = context.substring(articleRange)
            let next = context.substring(match.range(at: 2))
            guard let wantsAn = Self.expectsAn(next) else { continue }

            // A capitalised "A" mid-sentence is usually a label ("Plan A is …"), so only accept it at a sentence start.
            if article.first?.isUppercase == true && !isSentenceStart(articleRange.location, in: context) { continue }

            let isAn = article.count == 2
            guard wantsAn != isAn else { continue }
            let replacement = CaseStyle.match(wantsAn ? "an" : "a", to: article)
            let message = wantsAn
                ? "Use “an” before a vowel sound (“\(next)”)."
                : "Use “a” before a consonant sound (“\(next)”)."
            issues.append(makeIssue(articleRange, in: context, suggestions: [replacement], message: message))
        }
        return issues
    }

    private func isSentenceStart(_ index: Int, in context: RuleContext) -> Bool {
        var i = index - 1
        while let u = context.character(at: i), u == 0x20 || u == 0x09 { i -= 1 }
        guard let u = context.character(at: i) else { return true }
        return [0x2E, 0x21, 0x3F, 0x0A, 0x22, 0x201C, 0x28, 0x3A, 0x2D, 0x2A, 0x23].contains(u)
    }
}

// MARK: - Capitalisation

struct SentenceCapitalizationRule: Rule {
    let info = RuleInfo(id: "sentence-capitalization", name: "Sentence capitalisation",
                        summary: "A new sentence should start with a capital letter.", category: .grammar)

    private static let pattern = RX.make(#"(?<=[.!?])[ \t]+(\p{Ll}[\p{L}'’]*)"#)

    func check(_ context: RuleContext) -> [Issue] {
        var issues: [Issue] = []
        for match in Self.pattern.matches(in: context.text, range: context.fullRange) {
            let punctuationIndex = match.range.location - 1
            guard let punct = context.character(at: punctuationIndex) else { continue }
            // Ellipsis or "?!" sequences may continue a sentence.
            if let before = context.character(at: punctuationIndex - 1), before == 0x2E || before == 0x3F || before == 0x21 { continue }
            if punct == 0x2E {
                let word = SentenceSplitter.wordBefore(context.ns, index: punctuationIndex)
                if word.isEmpty || SentenceSplitter.abbreviations.contains(word) || word.count == 1 { continue }
                // Domain-like or numeric tokens ("example.com", "v1.2").
                if word.contains(".") { continue }
            }
            let wordRange = match.range(at: 1)
            let word = context.substring(wordRange)
            // Deliberate lower-case brand names: iPhone, macOS, eBay.
            if word.dropFirst().contains(where: { $0.isUppercase }) { continue }
            issues.append(makeIssue(wordRange, in: context, suggestions: [CaseStyle.capitalizeFirst(word)],
                                    message: "Start the sentence with a capital letter.",
                                    severity: .warning))
        }
        return issues
    }
}

struct LowercaseIRule: Rule {
    let info = RuleInfo(id: "lowercase-i", name: "Lower-case “i”",
                        summary: "The pronoun “I” is always capitalised.", category: .grammar)

    private static let pattern = RX.make(#"(?<![\p{L}\p{N}_.'’\-(\[])i(?![\p{L}\p{N}_.\-)\]])(?!\s*[=<>+*/\[\](){}])"#)

    func check(_ context: RuleContext) -> [Issue] {
        Self.pattern.matches(in: context.text, range: context.fullRange).map { match in
            makeIssue(match.range, in: context, suggestions: ["I"], message: "The pronoun “I” is always capitalised.")
        }
    }
}

struct ProperNounRule: Rule {
    let info = RuleInfo(id: "proper-nouns", name: "Days, months and languages",
                        summary: "“monday” → “Monday”, “english” → “English”.", category: .grammar)

    private static let pattern = RX.make(#"\b(?:"# + PhraseData.alwaysCapitalized.joined(separator: "|") + #")\b"#)

    func check(_ context: RuleContext) -> [Issue] {
        Self.pattern.matches(in: context.text, range: context.fullRange).map { match in
            let word = context.substring(match.range)
            return makeIssue(match.range, in: context, suggestions: [CaseStyle.capitalizeFirst(word)],
                             message: "“\(CaseStyle.capitalizeFirst(word))” is a proper noun and takes a capital letter.",
                             severity: .warning)
        }
    }
}

// MARK: - Dialect

struct DialectSpellingRule: Rule {
    let info = RuleInfo(id: "dialect-spelling", name: "Regional spelling",
                        summary: "Keeps spelling consistent with your chosen variety of English (colour/color, organise/organize).",
                        category: .spelling)

    private static let wordPattern = RX.make(#"\b\p{L}+\b"#)

    func check(_ context: RuleContext) -> [Issue] {
        let dialect = context.settings.dialect
        var issues: [Issue] = []
        for match in Self.wordPattern.matches(in: context.text, range: context.fullRange) {
            let word = context.substring(match.range)
            guard word.count >= 3, let preferred = DialectLexicon.preferredSpelling(of: word, for: dialect) else { continue }
            issues.append(makeIssue(match.range, in: context, suggestions: [preferred],
                                    message: "\(dialect.shortName) spelling is “\(preferred)”.",
                                    severity: .suggestion))
        }
        return issues
    }
}

// MARK: - Spacing

struct MultipleSpacesRule: Rule {
    let info = RuleInfo(id: "multiple-spaces", name: "Multiple spaces",
                        summary: "Two or more spaces between words.", category: .typography)

    private static let pattern = RX.make(#"(?<=\S) {2,}(?=\S)"#)

    func check(_ context: RuleContext) -> [Issue] {
        Self.pattern.matches(in: context.text, range: context.fullRange).map { match in
            makeIssue(match.range, in: context, suggestions: [" "], message: "Use a single space.")
        }
    }
}

struct SpaceBeforePunctuationRule: Rule {
    let info = RuleInfo(id: "space-before-punctuation", name: "Space before punctuation",
                        summary: "“word ,” → “word,”.", category: .punctuation)

    private static let pattern = RX.make(#"(?<=[\p{L}\p{N})\]"'”’])[ \t]+(?=[,;:!?](?:\s|$)|\.(?:\s|$))"#)

    func check(_ context: RuleContext) -> [Issue] {
        Self.pattern.matches(in: context.text, range: context.fullRange).map { match in
            makeIssue(match.range, in: context, suggestions: [""], message: "Remove the space before the punctuation mark.")
        }
    }
}

struct MissingSpaceRule: Rule {
    let info = RuleInfo(id: "missing-space", name: "Missing space after punctuation",
                        summary: "“word,word” → “word, word”.", category: .punctuation)

    private static let commaPattern = RX.make(#"(?<=\p{L}{2})([,;])(?=\p{L}{2})"#)
    private static let sentencePattern = RX.make(#"(?<=\p{Ll}{2})([.!?])(?=\p{Lu}\p{Ll})"#)

    func check(_ context: RuleContext) -> [Issue] {
        var issues: [Issue] = []
        for pattern in [Self.commaPattern, Self.sentencePattern] {
            for match in pattern.matches(in: context.text, range: context.fullRange) {
                let mark = context.substring(match.range)
                issues.append(makeIssue(match.range, in: context, suggestions: [mark + " "],
                                        message: "Add a space after “\(mark)”."))
            }
        }
        return issues
    }
}

// MARK: - Brackets and quotes

struct UnbalancedPairsRule: Rule {
    let info = RuleInfo(id: "unbalanced-pairs", name: "Unmatched brackets and quotes",
                        summary: "An opening “(” without a closing “)”, an odd number of quotation marks.",
                        category: .punctuation)

    func check(_ context: RuleContext) -> [Issue] {
        var issues: [Issue] = []
        let ns = context.ns
        var paragraphStart = 0
        let length = ns.length
        var index = 0
        while index <= length {
            if index == length || ns.character(at: index) == 0x0A {
                checkParagraph(from: paragraphStart, to: index, context: context, into: &issues)
                paragraphStart = index + 1
            }
            index += 1
        }
        return issues
    }

    private func checkParagraph(from start: Int, to end: Int, context: RuleContext, into issues: inout [Issue]) {
        guard end > start else { return }
        let ns = context.ns
        let openers: [unichar: unichar] = [0x28: 0x29, 0x5B: 0x5D, 0x7B: 0x7D] // ( [ {
        let closers: Set<unichar> = [0x29, 0x5D, 0x7D]
        var stack: [(unichar, Int)] = []
        var straightQuotes: [Int] = []
        var curlyOpen: [Int] = []
        var curlyCloseUnmatched: [Int] = []

        // List markers such as "1)" or "a)" at the start of a line are not brackets.
        var firstContent = start
        while firstContent < end, UnitClass.isWhitespace(ns.character(at: firstContent)) { firstContent += 1 }

        for i in start..<end {
            let u = ns.character(at: i)
            if openers[u] != nil {
                stack.append((u, i))
            } else if closers.contains(u) {
                if let last = stack.last, openers[last.0] == u {
                    stack.removeLast()
                } else if !(u == 0x29 && i - firstContent <= 3) {
                    issues.append(makeIssue(NSRange(location: i, length: 1), in: context, suggestions: [],
                                            message: "This closing bracket has no matching opening bracket."))
                }
            } else if u == 0x22 {
                straightQuotes.append(i)
            } else if u == 0x201C {
                curlyOpen.append(i)
            } else if u == 0x201D {
                if curlyOpen.isEmpty { curlyCloseUnmatched.append(i) } else { curlyOpen.removeLast() }
            }
        }
        for (_, position) in stack {
            issues.append(makeIssue(NSRange(location: position, length: 1), in: context, suggestions: [],
                                    message: "This bracket is never closed."))
        }
        if straightQuotes.count % 2 == 1, let last = straightQuotes.last {
            issues.append(makeIssue(NSRange(location: last, length: 1), in: context, suggestions: [],
                                    message: "Unmatched quotation mark."))
        }
        for position in curlyOpen + curlyCloseUnmatched {
            issues.append(makeIssue(NSRange(location: position, length: 1), in: context, suggestions: [],
                                    message: "Unmatched quotation mark."))
        }
    }
}

// MARK: - Style

struct PassiveVoiceRule: Rule {
    let info = RuleInfo(id: "passive-voice", name: "Passive voice",
                        summary: "“The report was written by …”. Not wrong, but often weaker.", category: .style)

    private static let pattern: NSRegularExpression = {
        let irregular = PhraseData.irregularParticiples.joined(separator: "|")
        let adverbs = "not|never|also|often|always|usually|already|then|just|still|completely|fully|widely|largely|generally|frequently|rarely|being"
        return RX.make(#"\b(?:am|is|are|was|were|be|been|being)\s+(?:(?:"# + adverbs + #")\s+)?(\p{L}+ed|"# + irregular + #")\b"#,
                       caseInsensitive: true)
    }()

    func check(_ context: RuleContext) -> [Issue] {
        Self.pattern.matches(in: context.text, range: context.fullRange).compactMap { match in
            let participle = context.substring(match.range(at: 1)).lowercased()
            guard !PhraseData.notPassiveParticiples.contains(participle) else { return nil }
            return makeIssue(match.range, in: context, suggestions: [],
                             message: "Passive voice. Consider an active construction if the actor matters.",
                             severity: .hint)
        }
    }
}

struct LongSentenceRule: Rule {
    let info = RuleInfo(id: "long-sentence", name: "Long sentences",
                        summary: "Sentences above your word limit (Settings → General).", category: .clarity)

    func check(_ context: RuleContext) -> [Issue] {
        let limit = max(10, context.settings.longSentenceWordLimit)
        var issues: [Issue] = []
        for span in SentenceSplitter.sentences(in: context.text) {
            let words = TextStatistics.wordPattern.numberOfMatches(in: context.text, range: span.nsRange)
            guard words > limit else { continue }
            issues.append(makeIssue(span.nsRange, in: context, suggestions: [],
                                    message: "This sentence has \(words) words. Consider splitting it.",
                                    severity: .hint))
        }
        return issues
    }
}

struct FormalityRule: Rule {
    let info = RuleInfo(id: "formality", name: "Formality",
                        summary: "Flags slang unless your goal is informal, and contractions when your goal is formal.",
                        category: .tone)

    private struct Compiled: @unchecked Sendable {
        let regex: NSRegularExpression
        let replacements: [String]
    }

    private static func compile(_ list: [(String, [String])]) -> [Compiled] {
        list.map { Compiled(regex: RX.make(PhraseEntry.literalPattern($0.0), caseInsensitive: true), replacements: $0.1) }
    }

    private static let contractions = compile(PhraseData.contractions)
    private static let slang = compile(PhraseData.slang)

    func check(_ context: RuleContext) -> [Issue] {
        let formality = context.settings.goals.formality
        var issues: [Issue] = []
        if formality != .informal {
            issues += run(Self.slang, context: context, message: "Informal word. Consider a more standard alternative.")
        }
        if formality == .formal {
            issues += run(Self.contractions, context: context, message: "Contractions can feel informal in formal writing.")
        }
        return issues
    }

    private func run(_ list: [Compiled], context: RuleContext, message: String) -> [Issue] {
        var issues: [Issue] = []
        for item in list {
            for match in item.regex.matches(in: context.text, range: context.fullRange) {
                let original = context.substring(match.range)
                let suggestions = item.replacements.map { CaseStyle.match($0, to: original) }
                issues.append(makeIssue(match.range, in: context, suggestions: suggestions, message: message, severity: .hint))
            }
        }
        return issues
    }
}
