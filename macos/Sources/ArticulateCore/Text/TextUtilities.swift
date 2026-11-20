import Foundation

extension String {
    /// Length in UTF-16 code units (the unit used by `TextSpan`).
    public var utf16Length: Int { utf16.count }

    /// Returns the substring for a UTF-16 span, or nil if the span is out of bounds.
    public func substring(in span: TextSpan) -> String? {
        let count = utf16.count
        guard span.location >= 0, span.length >= 0, span.upperBound <= count else { return nil }
        let start = String.Index(utf16Offset: span.location, in: self)
        let end = String.Index(utf16Offset: span.upperBound, in: self)
        return String(self[start..<end])
    }

    var fullNSRange: NSRange { NSRange(location: 0, length: utf16.count) }
}

/// Small helper for compiling the app's static, known-good regular expressions.
enum RX {
    static func make(_ pattern: String, caseInsensitive: Bool = false) -> NSRegularExpression {
        var options: NSRegularExpression.Options = []
        if caseInsensitive { options.insert(.caseInsensitive) }
        do {
            return try NSRegularExpression(pattern: pattern, options: options)
        } catch {
            preconditionFailure("Invalid built-in pattern \(pattern): \(error)")
        }
    }
}

public enum CaseStyle {
    public static func capitalizeFirst(_ s: String) -> String {
        guard let first = s.first else { return s }
        return first.uppercased() + s.dropFirst()
    }

    /// Makes `replacement` follow the capitalisation of `original` (UPPER, Title or as-is).
    public static func match(_ replacement: String, to original: String) -> String {
        guard !replacement.isEmpty else { return replacement }
        let letters = original.filter { $0.isLetter }
        if letters.count >= 2 && letters.allSatisfy({ $0.isUppercase }) {
            return replacement.uppercased()
        }
        if let first = original.first(where: { $0.isLetter }), first.isUppercase,
           let replacementFirst = replacement.first, replacementFirst.isLowercase {
            return capitalizeFirst(replacement)
        }
        return replacement
    }
}

enum UnitClass {
    static func isWhitespace(_ unit: unichar) -> Bool {
        unit == 0x20 || unit == 0x09 || unit == 0x0A || unit == 0x0D || unit == 0xA0 || unit == 0x2028 || unit == 0x2029
    }

    static func isLetter(_ unit: unichar) -> Bool {
        guard let scalar = Unicode.Scalar(unit) else { return false }
        return scalar.properties.isAlphabetic
    }
}
