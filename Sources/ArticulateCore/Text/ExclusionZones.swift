import Foundation

/// Regions that should never be "corrected": code, URLs, e-mail addresses and Markdown link targets.
public enum ExclusionZones {
    private static let patterns: [NSRegularExpression] = [
        // Fenced Markdown code blocks.
        RX.make(#"(?ms)^[ \t]*```.*?^[ \t]*```[ \t]*$"#),
        // Inline code.
        RX.make(#"`[^`\n]+`"#),
        // URLs.
        RX.make(#"\b(?:https?://|ftp://|www\.)[^\s<>"'()\[\]]+"#, caseInsensitive: true),
        // E-mail addresses.
        RX.make(#"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"#),
        // Markdown link / image targets: ](...)
        RX.make(#"\]\([^)\s]*\)"#),
        // HTML-ish tags.
        RX.make(#"</?[A-Za-z][^<>\n]{0,200}>"#),
    ]

    public static func compute(in text: String) -> [TextSpan] {
        let range = text.fullNSRange
        var zones: [TextSpan] = []
        for pattern in patterns {
            for match in pattern.matches(in: text, range: range) {
                zones.append(TextSpan(match.range))
            }
        }
        return zones.sorted { $0.location < $1.location }
    }

    public static func isExcluded(_ span: TextSpan, zones: [TextSpan]) -> Bool {
        zones.contains { $0.intersects(span) }
    }
}
