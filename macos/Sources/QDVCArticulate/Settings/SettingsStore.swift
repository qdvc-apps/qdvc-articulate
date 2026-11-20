import Foundation
import Combine
import ArticulateCore

struct LlamaSettings: Codable, Equatable {
    var contextLength = 8192
    var gpuLayers = 99
    var threads = 0
    var maxOutputTokens = 1024
    var chunkLength = 1200
    var temperature = 0.0
    var promptFormat: PromptFormat = .automatic
    var reusePromptCache = true
    var loadAtLaunch = true

    init() {}

    private enum CodingKeys: String, CodingKey {
        case contextLength, gpuLayers, threads, maxOutputTokens, chunkLength, temperature, promptFormat, reusePromptCache, loadAtLaunch
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let d = LlamaSettings()
        contextLength = (try? c.decodeIfPresent(Int.self, forKey: .contextLength)) ?? d.contextLength
        gpuLayers = (try? c.decodeIfPresent(Int.self, forKey: .gpuLayers)) ?? d.gpuLayers
        threads = (try? c.decodeIfPresent(Int.self, forKey: .threads)) ?? d.threads
        maxOutputTokens = (try? c.decodeIfPresent(Int.self, forKey: .maxOutputTokens)) ?? d.maxOutputTokens
        chunkLength = (try? c.decodeIfPresent(Int.self, forKey: .chunkLength)) ?? d.chunkLength
        temperature = (try? c.decodeIfPresent(Double.self, forKey: .temperature)) ?? d.temperature
        promptFormat = (try? c.decodeIfPresent(PromptFormat.self, forKey: .promptFormat)) ?? d.promptFormat
        reusePromptCache = (try? c.decodeIfPresent(Bool.self, forKey: .reusePromptCache)) ?? d.reusePromptCache
        loadAtLaunch = (try? c.decodeIfPresent(Bool.self, forKey: .loadAtLaunch)) ?? d.loadAtLaunch
    }
}

/// App-wide preferences, persisted in the sandbox container's UserDefaults (never synced anywhere).
@MainActor
final class SettingsStore: ObservableObject {
    static let shared = SettingsStore()

    private enum Keys {
        static let check = "check.settings"
        static let llama = "llama.settings"
        static let fontSize = "editor.fontSize"
        static let monospaced = "editor.monospaced"
        static let systemSpelling = "check.systemSpelling"
        static let systemGrammar = "check.systemGrammar"
        static let autoAI = "check.autoAI"
        static let modelBookmark = "model.bookmark"
        static let modelFileName = "model.fileName"
    }

    private let defaults = UserDefaults.standard

    @Published var check: CheckSettings { didSet { save(check, Keys.check) } }
    @Published var llama: LlamaSettings { didSet { save(llama, Keys.llama) } }
    @Published var editorFontSize: Double { didSet { defaults.set(editorFontSize, forKey: Keys.fontSize) } }
    @Published var useMonospacedFont: Bool { didSet { defaults.set(useMonospacedFont, forKey: Keys.monospaced) } }
    @Published var useSystemSpelling: Bool { didSet { defaults.set(useSystemSpelling, forKey: Keys.systemSpelling) } }
    @Published var useSystemGrammar: Bool { didSet { defaults.set(useSystemGrammar, forKey: Keys.systemGrammar) } }
    @Published var autoAICheck: Bool { didSet { defaults.set(autoAICheck, forKey: Keys.autoAI) } }
    @Published var modelBookmark: Data? { didSet { defaults.set(modelBookmark, forKey: Keys.modelBookmark) } }
    @Published var modelFileName: String? { didSet { defaults.set(modelFileName, forKey: Keys.modelFileName) } }

    private init() {
        // A local constant: `self.defaults` can't be read before every stored property is initialised.
        let defaults = UserDefaults.standard
        check = Self.load(CheckSettings.self, Keys.check, from: defaults) ?? CheckSettings()
        llama = Self.load(LlamaSettings.self, Keys.llama, from: defaults) ?? LlamaSettings()
        editorFontSize = defaults.object(forKey: Keys.fontSize) as? Double ?? 15
        useMonospacedFont = defaults.object(forKey: Keys.monospaced) as? Bool ?? false
        useSystemSpelling = defaults.object(forKey: Keys.systemSpelling) as? Bool ?? true
        useSystemGrammar = defaults.object(forKey: Keys.systemGrammar) as? Bool ?? true
        autoAICheck = defaults.object(forKey: Keys.autoAI) as? Bool ?? false
        modelBookmark = defaults.data(forKey: Keys.modelBookmark)
        modelFileName = defaults.string(forKey: Keys.modelFileName)
    }

    // MARK: Personal dictionary

    func addToDictionary(_ word: String) {
        let trimmed = word.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              !check.personalDictionary.contains(where: { $0.caseInsensitiveCompare(trimmed) == .orderedSame }) else { return }
        var words = check.personalDictionary
        words.append(trimmed)
        words.sort { $0.localizedCaseInsensitiveCompare($1) == .orderedAscending }
        check.personalDictionary = words
    }

    func removeFromDictionary(_ word: String) {
        check.personalDictionary.removeAll { $0 == word }
    }

    // MARK: Rules

    func isRuleEnabled(_ info: RuleInfo) -> Bool {
        check.isEnabled(info)
    }

    func setRule(_ info: RuleInfo, enabled: Bool) {
        if enabled == info.defaultEnabled {
            check.ruleOverrides.removeValue(forKey: info.id)
        } else {
            check.ruleOverrides[info.id] = enabled
        }
    }

    func resetRules() {
        check.ruleOverrides = [:]
    }

    // MARK: Persistence

    private func save<T: Encodable>(_ value: T, _ key: String) {
        if let data = try? JSONEncoder().encode(value) {
            defaults.set(data, forKey: key)
        }
    }

    private static func load<T: Decodable>(_ type: T.Type, _ key: String, from defaults: UserDefaults) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }
}
