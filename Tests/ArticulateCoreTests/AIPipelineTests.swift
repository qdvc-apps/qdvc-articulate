import XCTest
@testable import ArticulateCore

final class AIPipelineTests: XCTestCase {
    func testParsesCleanJSON() {
        let raw = #"{"issues":[{"original":"teh","replacement":"the","category":"spelling","explanation":"Typo."}]}"#
        XCTAssertEqual(LLMResponseParser.parse(raw).map(\.replacement), ["the"])
    }

    func testParsesTruncatedJSON() {
        let raw = #"{"issues":[{"original":"teh","replacement":"the","category":"spelling","explanation":"Typo."},{"original":"recieve","replac"#
        XCTAssertEqual(LLMResponseParser.parse(raw).map(\.original), ["teh"])
    }

    func testParsesFencedJSON() {
        let raw = "Sure! Here you go:\n```json\n{\"issues\":[]}\n```"
        XCTAssertTrue(LLMResponseParser.parse(raw).isEmpty)
    }

    func testAnchoring() {
        let chunk = TextChunk(span: TextSpan(location: 100, length: 29), text: "I recieve the the mail daily.")
        let suggestions = [
            LLMSuggestion(original: "recieve", replacement: "receive", category: "spelling", explanation: "Typo."),
            LLMSuggestion(original: "Missing words", replacement: "x", category: "grammar", explanation: "Not in text."),
        ]
        let anchored = IssueAnchorer.anchor(suggestions, in: chunk, settings: CheckSettings())
        XCTAssertEqual(anchored.count, 1)
        XCTAssertEqual(anchored.first?.span, TextSpan(location: 102, length: 7))
        XCTAssertEqual(anchored.first?.category, .spelling)
    }

    func testAnchoringNormalisesQuotes() {
        let chunk = TextChunk(span: TextSpan(location: 0, length: 14), text: "It’s own thing")
        let suggestions = [LLMSuggestion(original: "It's own", replacement: "Its own", category: "grammar", explanation: "")]
        let anchored = IssueAnchorer.anchor(suggestions, in: chunk, settings: CheckSettings())
        XCTAssertEqual(anchored.first?.original, "It’s own")
    }

    func testDialectGuardRejectsWrongVariety() {
        var settings = CheckSettings()
        settings.dialect = .gb
        let chunk = TextChunk(span: TextSpan(location: 0, length: 15), text: "A lovely colour")
        let suggestions = [LLMSuggestion(original: "colour", replacement: "color", category: "spelling", explanation: "")]
        XCTAssertTrue(IssueAnchorer.anchor(suggestions, in: chunk, settings: settings).isEmpty)
    }

    func testChunkerMergesShortParagraphs() {
        let text = "Heading\n\n" + String(repeating: "This is a sentence that goes on. ", count: 5) + "\n\nShort tail."
        let chunks = TextChunker.chunks(in: text, maxLength: 1200)
        XCTAssertEqual(chunks.count, 2)
        XCTAssertTrue(chunks[0].text.hasPrefix("Heading"))
    }

    func testChunkerSplitsLongParagraphs() {
        let sentence = "This is a reasonably long sentence used for testing the chunker. "
        let text = String(repeating: sentence, count: 40)
        let chunks = TextChunker.chunks(in: text, maxLength: 500)
        XCTAssertGreaterThan(chunks.count, 1)
        XCTAssertTrue(chunks.allSatisfy { $0.span.length <= 500 })
    }

    func testPromptFormatDetection() {
        XCTAssertEqual(PromptFormat.detect(chatTemplate: "{{ '<|turn>user' }}", architecture: "gemma4"), .gemma4)
        XCTAssertEqual(PromptFormat.detect(chatTemplate: "<start_of_turn>", architecture: nil), .gemma)
        XCTAssertEqual(PromptFormat.detect(chatTemplate: nil, architecture: "qwen3"), .chatml)
    }

    func testReviewerUsesCache() async throws {
        actor Counter { var calls = 0; func increment() { calls += 1 } }
        struct MockGenerator: TextGenerating {
            let counter: Counter
            func generate(prefix: String, body: String, grammar: String?, maxTokens: Int) async throws -> String {
                await counter.increment()
                return #"{"issues":[{"original":"teh","replacement":"the","category":"spelling","explanation":"Typo."}]}"#
            }
        }
        let counter = Counter()
        let reviewer = AIReviewer(generator: MockGenerator(counter: counter), cache: ReviewCache())
        let text = "This paragraph has teh typo and is long enough to stand on its own as a chunk of text."
        let options = AIReviewOptions(format: .chatml, modelIdentifier: "mock")

        var found: [Issue] = []
        for try await progress in reviewer.review(text: text, settings: CheckSettings(), options: options) {
            found += progress.issues
        }
        XCTAssertEqual(found.map(\.original), ["teh"])

        for try await _ in reviewer.review(text: text, settings: CheckSettings(), options: options) {}
        let calls = await counter.calls
        XCTAssertEqual(calls, 1)
    }
}
