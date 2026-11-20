import XCTest
@testable import ArticulateCore

final class RuleTests: XCTestCase {
    private func issues(_ text: String, dialect: Dialect = .us, formality: Formality = .neutral, rule: String? = nil) -> [Issue] {
        var settings = CheckSettings()
        settings.dialect = dialect
        settings.goals.formality = formality
        let all = RuleEngine(settings: settings).check(text)
        guard let rule else { return all }
        return all.filter { $0.ruleID == rule }
    }

    func testRepeatedWord() {
        let found = issues("I went to the the shop.", rule: "repeated-word")
        XCTAssertEqual(found.count, 1)
        XCTAssertEqual(found.first?.original, "the the")
        XCTAssertEqual(found.first?.suggestions, ["the"])
    }

    func testRepeatedWordAllowsHadHad() {
        XCTAssertTrue(issues("She had had enough.", rule: "repeated-word").isEmpty)
    }

    func testArticles() {
        XCTAssertEqual(issues("It took a hour.", rule: "a-an").first?.suggestions, ["an"])
        XCTAssertEqual(issues("She is an university student.", rule: "a-an").first?.suggestions, ["a"])
        XCTAssertEqual(issues("He has a MBA.", rule: "a-an").first?.suggestions, ["an"])
        XCTAssertTrue(issues("It was an unimportant detail.", rule: "a-an").isEmpty)
        XCTAssertTrue(issues("It was a unique event.", rule: "a-an").isEmpty)
        XCTAssertTrue(issues("Plan A is good.", rule: "a-an").isEmpty)
        XCTAssertTrue(issues("We need an herb garden.", rule: "a-an").isEmpty) // dialect-dependent: not flagged
    }

    func testCommonErrors() {
        XCTAssertEqual(issues("I could of done it.", rule: "common-errors").first?.suggestions, ["could have"])
        XCTAssertTrue(issues("It could of course be true.", rule: "common-errors").isEmpty)
        XCTAssertEqual(issues("This is better then that.", rule: "common-errors").first?.suggestions, ["better than"])
        XCTAssertEqual(issues("They should have went home.", rule: "common-errors").first?.suggestions, ["have gone"])
    }

    func testDialectSpelling() {
        XCTAssertEqual(issues("The colour is nice.", dialect: .us, rule: "dialect-spelling").first?.suggestions, ["color"])
        XCTAssertEqual(issues("The color is nice.", dialect: .gb, rule: "dialect-spelling").first?.suggestions, ["colour"])
        XCTAssertEqual(issues("We must organize it.", dialect: .gb, rule: "dialect-spelling").first?.suggestions, ["organise"])
        XCTAssertTrue(issues("We must organize it.", dialect: .gbOxford, rule: "dialect-spelling").isEmpty)
        XCTAssertEqual(issues("Colours", dialect: .us, rule: "dialect-spelling").first?.suggestions, ["Colors"])
        XCTAssertTrue(issues("The humorous honorary member.", dialect: .gb, rule: "dialect-spelling").isEmpty)
    }

    func testSentenceCapitalization() {
        XCTAssertEqual(issues("This is fine. this is not.", rule: "sentence-capitalization").first?.suggestions, ["This"])
        XCTAssertTrue(issues("Use e.g. apples.", rule: "sentence-capitalization").isEmpty)
        XCTAssertTrue(issues("I bought one. iPhone sales rose.", rule: "sentence-capitalization").isEmpty)
    }

    func testLowercaseI() {
        XCTAssertEqual(issues("Yesterday i went home.", rule: "lowercase-i").count, 1)
        XCTAssertTrue(issues("That is, i.e. this one.", rule: "lowercase-i").isEmpty)
    }

    func testSpacing() {
        XCTAssertEqual(issues("Two  spaces.", rule: "multiple-spaces").count, 1)
        XCTAssertEqual(issues("Hello , world.", rule: "space-before-punctuation").count, 1)
        XCTAssertEqual(issues("Hello,world.", rule: "missing-space").first?.suggestions, [", "])
        XCTAssertTrue(issues("Pi is 3.14 and 1,000 is big.", rule: "missing-space").isEmpty)
    }

    func testUnbalanced() {
        XCTAssertEqual(issues("This (is open.", rule: "unbalanced-pairs").count, 1)
        XCTAssertTrue(issues("1) First item", rule: "unbalanced-pairs").isEmpty)
        XCTAssertTrue(issues("A (closed) one.", rule: "unbalanced-pairs").isEmpty)
    }

    func testWordinessDeletionIncludesSpace() {
        let text = "We are in the process of updating."
        let found = issues(text, rule: "wordiness")
        XCTAssertEqual(found.first?.suggestions, [""])
        XCTAssertEqual(found.first?.original, "in the process of ")
    }

    func testFormality() {
        XCTAssertTrue(issues("We don't know.", formality: .neutral, rule: "formality").isEmpty)
        XCTAssertEqual(issues("We don't know.", formality: .formal, rule: "formality").first?.suggestions, ["do not"])
        XCTAssertEqual(issues("I'm gonna go.", formality: .neutral, rule: "formality").first?.suggestions, ["going to"])
    }

    func testURLsAreExcluded() {
        XCTAssertTrue(issues("See https://example.com/the/the/page for more.", rule: "repeated-word").isEmpty)
    }

    func testCaseStyle() {
        XCTAssertEqual(CaseStyle.match("because", to: "Due to the fact that"), "Because")
        XCTAssertEqual(CaseStyle.match("pin", to: "PIN"), "PIN")
        XCTAssertEqual(CaseStyle.match("near", to: "in close proximity to"), "near")
    }
}
