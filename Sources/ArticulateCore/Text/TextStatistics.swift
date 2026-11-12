import Foundation

public struct TextStatistics: Equatable, Sendable {
    public var characters = 0
    public var charactersExcludingSpaces = 0
    public var words = 0
    public var sentences = 0
    public var paragraphs = 0
    public var syllables = 0
    public var uniqueWords = 0
    public var longestSentenceWords = 0
    public var averageWordsPerSentence = 0.0
    public var averageSyllablesPerWord = 0.0
    /// Flesch Reading Ease (higher = easier). Nil for very short texts.
    public var fleschReadingEase: Double?
    /// Flesch–Kincaid grade level. Nil for very short texts.
    public var fleschKincaidGrade: Double?
    /// At 238 words per minute (average adult silent reading).
    public var readingTimeSeconds = 0
    /// At 150 words per minute.
    public var speakingTimeSeconds = 0

    public init() {}

    public static let empty = TextStatistics()

    public var lexicalDiversity: Double {
        words == 0 ? 0 : Double(uniqueWords) / Double(words)
    }

    public var readabilityLabel: String {
        guard let score = fleschReadingEase else { return "Not enough text" }
        switch score {
        case 90...: return "Very easy"
        case 80..<90: return "Easy"
        case 70..<80: return "Fairly easy"
        case 60..<70: return "Plain English"
        case 50..<60: return "Fairly difficult"
        case 30..<50: return "Difficult"
        default: return "Very difficult"
        }
    }

    static let wordPattern = RX.make(#"[\p{L}\p{N}]+(?:['’][\p{L}]+)*"#)

    public static func compute(_ text: String) -> TextStatistics {
        var stats = TextStatistics()
        stats.characters = text.count
        stats.charactersExcludingSpaces = text.reduce(0) { $0 + ($1.isWhitespace ? 0 : 1) }

        let ns = NSString(string: text)
        let wordMatches = wordPattern.matches(in: text, range: NSRange(location: 0, length: ns.length))
        stats.words = wordMatches.count

        var unique = Set<String>()
        var syllableTotal = 0
        for match in wordMatches {
            let word = ns.substring(with: match.range).lowercased()
            unique.insert(word)
            syllableTotal += syllableCount(word)
        }
        stats.uniqueWords = unique.count
        stats.syllables = syllableTotal

        let sentenceSpans = SentenceSplitter.sentences(in: text).filter { span in
            // Ignore "sentences" that contain no words (e.g. a line of dashes).
            wordPattern.firstMatch(in: text, range: span.nsRange) != nil
        }
        stats.sentences = sentenceSpans.count
        for span in sentenceSpans {
            let n = wordPattern.numberOfMatches(in: text, range: span.nsRange)
            stats.longestSentenceWords = max(stats.longestSentenceWords, n)
        }

        stats.paragraphs = text.split(whereSeparator: { $0 == "\n" || $0 == "\r\n" })
            .filter { $0.contains(where: { $0.isLetter || $0.isNumber }) }
            .count

        if stats.sentences > 0 {
            stats.averageWordsPerSentence = Double(stats.words) / Double(stats.sentences)
        }
        if stats.words > 0 {
            stats.averageSyllablesPerWord = Double(stats.syllables) / Double(stats.words)
        }
        if stats.words >= 30 && stats.sentences > 0 {
            let wps = stats.averageWordsPerSentence
            let spw = stats.averageSyllablesPerWord
            stats.fleschReadingEase = 206.835 - 1.015 * wps - 84.6 * spw
            stats.fleschKincaidGrade = 0.39 * wps + 11.8 * spw - 15.59
        }
        stats.readingTimeSeconds = Int((Double(stats.words) / 238.0 * 60.0).rounded())
        stats.speakingTimeSeconds = Int((Double(stats.words) / 150.0 * 60.0).rounded())
        return stats
    }

    /// Heuristic English syllable count (good enough for readability formulas).
    public static func syllableCount(_ word: String) -> Int {
        let letters = word.lowercased().filter { $0.isLetter }
        guard !letters.isEmpty else { return 1 }
        if letters.count <= 3 { return 1 }
        let vowels: Set<Character> = ["a", "e", "i", "o", "u", "y"]
        var count = 0
        var previousWasVowel = false
        for ch in letters {
            let isVowel = vowels.contains(ch)
            if isVowel && !previousWasVowel { count += 1 }
            previousWasVowel = isVowel
        }
        if letters.hasSuffix("e") && !letters.hasSuffix("le") && count > 1 { count -= 1 }
        if (letters.hasSuffix("es") || letters.hasSuffix("ed")) && count > 1,
           !(letters.hasSuffix("ted") || letters.hasSuffix("ded") || letters.hasSuffix("ses") || letters.hasSuffix("zes") || letters.hasSuffix("ces") || letters.hasSuffix("ges")) {
            count -= 1
        }
        return max(1, count)
    }
}
