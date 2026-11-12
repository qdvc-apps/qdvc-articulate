import Foundation

public struct RuleInfo: Identifiable, Hashable, Sendable {
    public let id: String
    public let name: String
    public let summary: String
    public let category: IssueCategory
    public let defaultEnabled: Bool

    public init(id: String, name: String, summary: String, category: IssueCategory, defaultEnabled: Bool = true) {
        self.id = id
        self.name = name
        self.summary = summary
        self.category = category
        self.defaultEnabled = defaultEnabled
    }
}

public struct RuleContext {
    public let text: String
    public let ns: NSString
    public let settings: CheckSettings
    public let fullRange: NSRange

    public init(text: String, settings: CheckSettings) {
        self.text = text
        self.ns = NSString(string: text)
        self.settings = settings
        self.fullRange = NSRange(location: 0, length: ns.length)
    }

    func substring(_ range: NSRange) -> String {
        ns.substring(with: range)
    }

    func character(at index: Int) -> unichar? {
        guard index >= 0, index < ns.length else { return nil }
        return ns.character(at: index)
    }
}

public protocol Rule: Sendable {
    var info: RuleInfo { get }
    func check(_ context: RuleContext) -> [Issue]
}

extension Rule {
    func makeIssue(
        _ range: NSRange,
        in context: RuleContext,
        suggestions: [String],
        message: String,
        category: IssueCategory? = nil,
        severity: IssueSeverity? = nil
    ) -> Issue {
        let cat = category ?? info.category
        return Issue(
            span: TextSpan(range),
            original: context.substring(range),
            suggestions: suggestions,
            category: cat,
            severity: severity,
            message: message,
            ruleID: info.id,
            source: .rules
        )
    }
}

/// Runs all enabled deterministic rules. Pure and thread-safe: call it off the main thread.
public struct RuleEngine: Sendable {
    public static let rules: [Rule] = BuiltInRules.all

    public static var ruleInfos: [RuleInfo] { rules.map(\.info) }

    public let settings: CheckSettings

    public init(settings: CheckSettings) {
        self.settings = settings
    }

    public func check(_ text: String) -> [Issue] {
        guard !text.isEmpty else { return [] }
        let context = RuleContext(text: text, settings: settings)
        let zones = ExclusionZones.compute(in: text)
        var issues: [Issue] = []
        for rule in Self.rules where settings.isEnabled(rule.info) {
            issues.append(contentsOf: rule.check(context))
        }
        return issues
            .filter { !ExclusionZones.isExcluded($0.span, zones: zones) }
            .sorted { $0.span.location < $1.span.location }
    }
}
