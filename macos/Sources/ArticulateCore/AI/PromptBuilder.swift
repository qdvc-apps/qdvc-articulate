import Foundation

/// Builds the copy-editing instructions given to the local language model.
/// Small (2–8B) models do best with short, explicit rules and one worked example.
public struct PromptBuilder: Sendable {
    public let settings: CheckSettings

    public init(settings: CheckSettings) {
        self.settings = settings
    }

    public static let userLead = "TEXT:\n"

    public var systemPrompt: String {
        let goals = settings.goals
        var lines: [String] = []
        lines.append("You are a meticulous, conservative copy editor for \(settings.dialect.promptName).")
        lines.append("Find genuine errors and clear improvements in the TEXT the user sends: spelling, grammar, punctuation, word choice, clarity and concision.")
        lines.append("Writing goals: \(goals.promptDescription). Only suggest tone changes that serve these goals.")
        lines.append("")
        lines.append("Rules:")
        lines.append("- Report only real problems. If the text is fine, return {\"issues\":[]}.")
        lines.append("- \"original\" must be copied EXACTLY from the TEXT (same letters, case and punctuation) and be as short as possible, usually 1 to 6 words.")
        lines.append("- \"replacement\" is the corrected text that replaces \"original\". Keep the author's meaning and voice.")
        lines.append("- Use \(settings.dialect.promptName) spelling. Never change a correct spelling into another variety of English.")
        lines.append("- Do not rewrite whole sentences unless needed for clarity. Do not report matters of taste as errors.")
        lines.append("- Ignore code, URLs, e-mail addresses and Markdown syntax.")
        lines.append("- \"explanation\" is one short sentence of at most 20 words.")
        lines.append("- \"category\" is one of: spelling, grammar, punctuation, wordChoice, clarity, concision, style, tone.")
        lines.append("")
        lines.append("Respond with JSON only, in this exact form:")
        lines.append(#"{"issues":[{"original":"...","replacement":"...","category":"grammar","explanation":"..."}]}"#)
        lines.append("")
        lines.append("Example")
        lines.append("TEXT: Their going to the libary tomorow, and they has alot of book to return.")
        lines.append(#"OUTPUT: {"issues":[{"original":"Their going","replacement":"They're going","category":"grammar","explanation":"Use \"they're\" (they are)."},{"original":"libary","replacement":"library","category":"spelling","explanation":"Misspelling."},{"original":"tomorow","replacement":"tomorrow","category":"spelling","explanation":"Misspelling."},{"original":"they has","replacement":"they have","category":"grammar","explanation":"Subject and verb must agree."},{"original":"alot of book","replacement":"a lot of books","category":"grammar","explanation":"\"A lot\" is two words, and the noun should be plural."}]}"#)
        return lines.joined(separator: "\n")
    }

    public func render(chunk: String, format: PromptFormat) -> RenderedPrompt {
        format.render(system: systemPrompt, userLead: Self.userLead, userText: chunk)
    }
}
