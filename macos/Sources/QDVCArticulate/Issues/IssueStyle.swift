import SwiftUI
import AppKit
import ArticulateCore

enum IssueStyle {
    static func nsColor(for group: IssueGroup) -> NSColor {
        switch group {
        case .correctness: return .systemRed
        case .clarity: return .systemBlue
        case .engagement: return .systemGreen
        case .delivery: return .systemPurple
        }
    }

    static func color(for group: IssueGroup) -> Color {
        Color(nsColor: nsColor(for: group))
    }

    static func symbol(for group: IssueGroup) -> String {
        switch group {
        case .correctness: return "checkmark.seal"
        case .clarity: return "eye"
        case .engagement: return "sparkles"
        case .delivery: return "megaphone"
        }
    }
}

extension String {
    /// Single-line, length-limited version for display in lists.
    func excerpt(maxLength: Int = 90) -> String {
        let flattened = replacingOccurrences(of: "\n", with: " ")
        guard flattened.count > maxLength else { return flattened }
        return String(flattened.prefix(maxLength - 1)) + "…"
    }
}
