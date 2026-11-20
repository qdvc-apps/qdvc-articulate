import Foundation

/// High-level grouping used for colours and filters in the UI.
public enum IssueGroup: String, CaseIterable, Codable, Sendable, Identifiable {
    case correctness
    case clarity
    case engagement
    case delivery

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .correctness: return "Correctness"
        case .clarity: return "Clarity"
        case .engagement: return "Engagement"
        case .delivery: return "Delivery"
        }
    }
}

public enum IssueCategory: String, CaseIterable, Codable, Sendable, Identifiable {
    case spelling
    case grammar
    case punctuation
    case consistency
    case clarity
    case concision
    case wordChoice
    case style
    case tone
    case typography

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .spelling: return "Spelling"
        case .grammar: return "Grammar"
        case .punctuation: return "Punctuation"
        case .consistency: return "Consistency"
        case .clarity: return "Clarity"
        case .concision: return "Concision"
        case .wordChoice: return "Word choice"
        case .style: return "Style"
        case .tone: return "Tone"
        case .typography: return "Typography"
        }
    }

    public var group: IssueGroup {
        switch self {
        case .spelling, .grammar, .punctuation, .consistency: return .correctness
        case .clarity, .concision: return .clarity
        case .wordChoice, .style: return .engagement
        case .tone, .typography: return .delivery
        }
    }

    public var defaultSeverity: IssueSeverity {
        switch self {
        case .spelling, .grammar: return .error
        case .punctuation, .consistency: return .warning
        case .clarity, .concision, .wordChoice: return .suggestion
        case .style, .tone, .typography: return .hint
        }
    }

    /// Lenient mapping for category names produced by a language model.
    public init?(looseName: String) {
        let key = looseName.lowercased().filter { $0.isLetter }
        switch key {
        case "spelling", "typo", "misspelling", "orthography": self = .spelling
        case "grammar", "agreement", "tense", "capitalization", "capitalisation", "syntax": self = .grammar
        case "punctuation", "comma": self = .punctuation
        case "consistency": self = .consistency
        case "clarity", "readability", "ambiguity": self = .clarity
        case "concision", "conciseness", "wordiness", "redundancy", "brevity": self = .concision
        case "wordchoice", "vocabulary", "usage", "diction": self = .wordChoice
        case "style", "fluency": self = .style
        case "tone", "formality", "register": self = .tone
        case "typography", "formatting", "spacing": self = .typography
        default: return nil
        }
    }
}

public enum IssueSeverity: Int, Codable, Comparable, Sendable {
    case hint = 0
    case suggestion = 1
    case warning = 2
    case error = 3

    public static func < (lhs: IssueSeverity, rhs: IssueSeverity) -> Bool {
        lhs.rawValue < rhs.rawValue
    }
}

public enum IssueSource: String, Codable, Sendable {
    case rules
    case spellChecker
    case ai

    public var displayName: String {
        switch self {
        case .rules: return "Rules"
        case .spellChecker: return "Spelling"
        case .ai: return "AI"
        }
    }
}

/// A range in UTF-16 code units. UTF-16 is what NSString/NSTextView use on macOS;
/// a GTK port will convert at the UI boundary.
public struct TextSpan: Hashable, Codable, Sendable {
    public var location: Int
    public var length: Int

    public init(location: Int, length: Int) {
        self.location = location
        self.length = length
    }

    public init(_ range: NSRange) {
        self.location = range.location
        self.length = range.length
    }

    public var upperBound: Int { location + length }

    public var nsRange: NSRange { NSRange(location: location, length: length) }

    public func intersects(_ other: TextSpan) -> Bool {
        location < other.upperBound && other.location < upperBound
    }

    public func contains(_ other: TextSpan) -> Bool {
        other.location >= location && other.upperBound <= upperBound
    }

    public func offset(by delta: Int) -> TextSpan {
        TextSpan(location: location + delta, length: length)
    }
}

public struct Issue: Identifiable, Hashable, Codable, Sendable {
    public var id: UUID
    public var span: TextSpan
    /// The exact text the issue refers to. Used to validate the span after edits.
    public var original: String
    /// Replacement candidates. An empty string means "delete".
    public var suggestions: [String]
    public var category: IssueCategory
    public var severity: IssueSeverity
    public var message: String
    public var ruleID: String
    public var source: IssueSource

    public init(
        id: UUID = UUID(),
        span: TextSpan,
        original: String,
        suggestions: [String] = [],
        category: IssueCategory,
        severity: IssueSeverity? = nil,
        message: String,
        ruleID: String,
        source: IssueSource
    ) {
        self.id = id
        self.span = span
        self.original = original
        self.suggestions = suggestions
        self.category = category
        self.severity = severity ?? category.defaultSeverity
        self.message = message
        self.ruleID = ruleID
        self.source = source
    }

    /// Text-based identity used for "Ignore" so the decision survives edits elsewhere.
    public var fingerprint: String {
        "\(category.rawValue)|\(original)|\(suggestions.first ?? "")"
    }
}
