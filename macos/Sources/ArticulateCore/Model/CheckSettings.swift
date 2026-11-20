import Foundation

public enum Dialect: String, CaseIterable, Codable, Sendable, Identifiable {
    case us = "en-US"
    case gb = "en-GB"
    case gbOxford = "en-GB-oxendict"
    case ca = "en-CA"
    case au = "en-AU"

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .us: return "English (US)"
        case .gb: return "English (UK)"
        case .gbOxford: return "English (UK, Oxford -ize)"
        case .ca: return "English (Canada)"
        case .au: return "English (Australia)"
        }
    }

    public var shortName: String {
        switch self {
        case .us: return "US"
        case .gb: return "UK"
        case .gbOxford: return "UK (Oxford)"
        case .ca: return "Canadian"
        case .au: return "Australian"
        }
    }

    /// Wording used inside the language-model prompt.
    public var promptName: String {
        switch self {
        case .us: return "American English"
        case .gb: return "British English (-ise spellings)"
        case .gbOxford: return "British English with Oxford spelling (-ize endings, but -yse as in analyse)"
        case .ca: return "Canadian English (-our and -ize spellings)"
        case .au: return "Australian English (-our and -ise spellings)"
        }
    }

    /// Language code understood by macOS NSSpellChecker.
    public var appleSpellLanguage: String {
        switch self {
        case .us: return "en_US"
        case .gb, .gbOxford: return "en_GB"
        case .ca: return "en_CA"
        case .au: return "en_AU"
        }
    }
}

public enum Audience: String, CaseIterable, Codable, Sendable, Identifiable {
    case general, knowledgeable, expert
    public var id: String { rawValue }
    public var displayName: String { rawValue.capitalized }
}

public enum Formality: String, CaseIterable, Codable, Sendable, Identifiable {
    case informal, neutral, formal
    public var id: String { rawValue }
    public var displayName: String { rawValue.capitalized }
}

public enum WritingDomain: String, CaseIterable, Codable, Sendable, Identifiable {
    case general, academic, business, technical, creative, casual, email
    public var id: String { rawValue }
    public var displayName: String {
        switch self {
        case .email: return "Email"
        default: return rawValue.capitalized
        }
    }
}

public struct WritingGoals: Codable, Hashable, Sendable {
    public var audience: Audience = .general
    public var formality: Formality = .neutral
    public var domain: WritingDomain = .general

    public init(audience: Audience = .general, formality: Formality = .neutral, domain: WritingDomain = .general) {
        self.audience = audience
        self.formality = formality
        self.domain = domain
    }

    public var promptDescription: String {
        "audience: \(audience.rawValue); formality: \(formality.rawValue); domain: \(domain.rawValue)"
    }
}

public struct CheckSettings: Codable, Hashable, Sendable {
    public var dialect: Dialect = .us
    public var goals: WritingGoals = WritingGoals()
    /// Per-rule on/off overrides. Rules without an entry use their default.
    public var ruleOverrides: [String: Bool] = [:]
    public var longSentenceWordLimit: Int = 35
    /// Words the user never wants flagged as misspelled.
    public var personalDictionary: [String] = []

    public init() {}

    public func isEnabled(_ info: RuleInfo) -> Bool {
        ruleOverrides[info.id] ?? info.defaultEnabled
    }

    /// Everything that changes what the language model should say about a passage.
    public var aiCacheKey: String {
        "\(dialect.rawValue)|\(goals.audience.rawValue)|\(goals.formality.rawValue)|\(goals.domain.rawValue)"
    }

    private enum CodingKeys: String, CodingKey {
        case dialect, goals, ruleOverrides, longSentenceWordLimit, personalDictionary
    }

    // Tolerant decoding so that adding settings later never wipes a user's saved preferences.
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        dialect = (try? c.decodeIfPresent(Dialect.self, forKey: .dialect)) ?? .us
        goals = (try? c.decodeIfPresent(WritingGoals.self, forKey: .goals)) ?? WritingGoals()
        ruleOverrides = (try? c.decodeIfPresent([String: Bool].self, forKey: .ruleOverrides)) ?? [:]
        longSentenceWordLimit = (try? c.decodeIfPresent(Int.self, forKey: .longSentenceWordLimit)) ?? 35
        personalDictionary = (try? c.decodeIfPresent([String].self, forKey: .personalDictionary)) ?? []
    }
}
