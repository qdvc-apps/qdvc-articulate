import XCTest
@testable import ArticulateCore

final class TextTests: XCTestCase {
    func testSentenceSplitting() {
        let text = "Dr. Smith arrived. He said hello! Did it work? Yes, e.g. this one."
        let sentences = SentenceSplitter.sentences(in: text).compactMap { text.substring(in: $0) }
        XCTAssertEqual(sentences, ["Dr. Smith arrived.", "He said hello!", "Did it work?", "Yes, e.g. this one."])
    }

    func testStatistics() {
        let text = String(repeating: "The cat sat on the mat. ", count: 10)
        let stats = TextStatistics.compute(text)
        XCTAssertEqual(stats.words, 60)
        XCTAssertEqual(stats.sentences, 10)
        XCTAssertNotNil(stats.fleschReadingEase)
        XCTAssertGreaterThan(stats.fleschReadingEase ?? 0, 90)
    }

    func testAdjusterShiftsAndDrops() {
        let a = Issue(span: TextSpan(location: 0, length: 3), original: "teh", category: .spelling, message: "", ruleID: "x", source: .rules)
        let b = Issue(span: TextSpan(location: 10, length: 3), original: "abc", category: .spelling, message: "", ruleID: "x", source: .rules)
        let c = Issue(span: TextSpan(location: 20, length: 3), original: "xyz", category: .spelling, message: "", ruleID: "x", source: .rules)
        // Replace 2 characters at 11 with 5 characters: b overlaps (dropped), c shifts by 3.
        let adjusted = IssueAdjuster.adjust([a, b, c], editedSpan: TextSpan(location: 11, length: 2), replacementLength: 5)
        XCTAssertEqual(adjusted.map(\.original), ["teh", "xyz"])
        XCTAssertEqual(adjusted.last?.span.location, 23)
    }

    func testMergerDeduplicatesAndValidates() {
        let text = "teh cat"
        let spell = Issue(span: TextSpan(location: 0, length: 3), original: "teh", suggestions: ["the"], category: .spelling, message: "", ruleID: "s", source: .spellChecker)
        let ai = Issue(span: TextSpan(location: 0, length: 3), original: "teh", suggestions: ["the", "tea"], category: .spelling, message: "", ruleID: "a", source: .ai)
        let stale = Issue(span: TextSpan(location: 4, length: 3), original: "dog", category: .spelling, message: "", ruleID: "s", source: .spellChecker)
        let merged = IssueMerger.merge([[spell], [ai, stale]], text: text, ignored: [], settings: CheckSettings(), zones: [])
        XCTAssertEqual(merged.count, 1)
        XCTAssertEqual(merged.first?.suggestions, ["the", "tea"])
    }

    func testPersonalDictionary() {
        var settings = CheckSettings()
        settings.personalDictionary = ["QDVC"]
        let issue = Issue(span: TextSpan(location: 0, length: 4), original: "qdvc", category: .spelling, message: "", ruleID: "s", source: .spellChecker)
        XCTAssertTrue(IssueMerger.merge([[issue]], text: "qdvc", ignored: [], settings: settings, zones: []).isEmpty)
    }

    func testExclusionZones() {
        let text = "Run `the the` or visit www.example.com now."
        let zones = ExclusionZones.compute(in: text)
        XCTAssertEqual(zones.count, 2)
    }
}
