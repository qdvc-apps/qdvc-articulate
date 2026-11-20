import Foundation

/// Curated English phrase lists. Kept deliberately conservative: a false positive costs more trust
/// than a missed hint, and the AI pass catches the subtler cases.
enum PhraseData {

    // MARK: - Common errors (grammar / word choice)

    static let commonErrors: [PhraseEntry] = [
        .regex(#"\b(could|should|would|must|might)\s+of\b(?!\s+course)"#, ["$1 have"],
               "Use “have” (or the contraction “’ve”), not “of”.", category: .grammar, severity: .error),
        .regex(#"\b(more|less|better|worse|rather|other|greater|fewer|larger|smaller|higher|lower|bigger|faster|slower|older|younger|easier|harder|sooner|further|farther|stronger|weaker|cheaper|longer|shorter)\s+(then)\b"#,
               ["$1 than"], "Use “than” for comparisons; “then” refers to time.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+went\b"#, ["$1 gone"], "The past participle of “go” is “gone”.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+came\b"#, ["$1 come"], "The past participle of “come” is “come”.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+saw\b"#, ["$1 seen"], "The past participle of “see” is “seen”.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+did\b"#, ["$1 done"], "The past participle of “do” is “done”.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+ate\b"#, ["$1 eaten"], "The past participle of “eat” is “eaten”.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+wrote\b"#, ["$1 written"], "The past participle of “write” is “written”.", category: .grammar, severity: .error),
        .regex(#"\b(have|has|had)\s+began\b"#, ["$1 begun"], "The past participle of “begin” is “begun”.", category: .grammar, severity: .error),
        .regex(#"\b(was|were|is|are|am|be|been|not)\s+suppose\s+to\b"#, ["$1 supposed to"], "Use “supposed to”.", category: .grammar, severity: .error),
        .regex(#"\b(was|were|is|are|am|get|got|getting|become|became)\s+use\s+to\b"#, ["$1 used to"], "Use “used to” (accustomed to).", category: .grammar, severity: .error),
        .phrase("alot", ["a lot"], "“A lot” is two words.", category: .spelling, severity: .error),
        .phrase("irregardless", ["regardless"], "Use “regardless”.", category: .wordChoice, severity: .warning),
        .phrase("for all intensive purposes", ["for all intents and purposes"], "The idiom is “for all intents and purposes”.", category: .wordChoice, severity: .warning),
        .phrase("per say", ["per se"], "The Latin phrase is “per se”.", category: .spelling, severity: .error),
        .phrase("case and point", ["case in point"], "The idiom is “case in point”.", category: .wordChoice, severity: .warning),
        .phrase("one in the same", ["one and the same"], "The idiom is “one and the same”.", category: .wordChoice, severity: .warning),
        .phrase("sneak peak", ["sneak peek"], "A quick look is a “peek”.", category: .spelling, severity: .error),
        .regex(#"\bpeak(ed|s)?\s+(my|your|his|her|their|our|its)\s+(interest|curiosity)\b"#, ["pique$1 $2 $3"],
               "To arouse interest is to “pique” it.", category: .wordChoice, severity: .warning),
        .phrase("free reign", ["free rein"], "The idiom is “free rein” (from horse riding).", category: .wordChoice, severity: .warning),
        .phrase("baited breath", ["bated breath"], "The idiom is “bated breath”.", category: .spelling, severity: .warning),
        .regex(#"\bdeep[- ]seeded\b"#, ["deep-seated"], "The idiom is “deep-seated”.", category: .wordChoice, severity: .warning),
        .regex(#"\btow(s|ed|ing)?\s+the\s+line\b"#, ["toe$1 the line"], "The idiom is “toe the line”.", category: .wordChoice, severity: .warning),
        .regex(#"\bwreck(s|ed|ing)?\s+havoc\b"#, ["wreak$1 havoc"], "The idiom is “wreak havoc”.", category: .wordChoice, severity: .warning),
        .phrase("it's own", ["its own"], "Possessive “its” has no apostrophe.", category: .grammar, severity: .error),
        .phrase("your welcome", ["you're welcome"], "Use “you’re” (you are).", category: .grammar, severity: .error),
        .phrase("could care less", ["couldn't care less"], "The standard idiom is “couldn’t care less”.", category: .wordChoice, severity: .hint),
        .phrase("between you and I", ["between you and me"], "After a preposition, use “me”.", category: .grammar, severity: .warning),
        .regex(#"\b(an|the)\s+affect\b"#, ["$1 effect"], "The noun is usually “effect”.", category: .wordChoice, severity: .suggestion),
        .regex(#"\bless\s+(people|items|things|words|mistakes|errors|cars|books|options|students|employees|calories|steps|days|hours|questions)\b"#,
               ["fewer $1"], "Use “fewer” with countable nouns.", category: .grammar, severity: .suggestion),
        .phrase("supposably", ["supposedly"], "Use “supposedly”.", category: .spelling, severity: .warning),
        .phrase("expresso", ["espresso"], "The coffee is “espresso”.", category: .spelling, severity: .warning),
        .phrase("heighth", ["height"], "The word is “height”.", category: .spelling, severity: .error),
        .phrase("nip it in the butt", ["nip it in the bud"], "The idiom is “nip it in the bud”.", category: .wordChoice, severity: .warning),
        .phrase("make due", ["make do"], "The idiom is “make do”.", category: .wordChoice, severity: .warning),
        .phrase("on accident", ["by accident"], "The standard phrase is “by accident”.", category: .wordChoice, severity: .hint),
        .phrase("try and", ["try to"], "In formal writing, prefer “try to”.", category: .wordChoice, severity: .hint),
        .phrase("the reason is because", ["the reason is that"], "“The reason is because” is redundant.", category: .grammar, severity: .suggestion),
        .phrase("the reason why is because", ["the reason is that", "because"], "This phrasing is redundant.", category: .concision, severity: .suggestion),
    ]

    // MARK: - Wordiness (concision)

    static let wordiness: [PhraseEntry] = [
        .phrase("in order to", ["to"], "Wordy: “to” is usually enough."),
        .phrase("in order for", ["for"], "Wordy: “for” is usually enough."),
        .phrase("due to the fact that", ["because"], "Wordy: consider “because”."),
        .phrase("owing to the fact that", ["because"], "Wordy: consider “because”."),
        .phrase("in light of the fact that", ["because", "since"], "Wordy: consider “because”."),
        .phrase("in spite of the fact that", ["although"], "Wordy: consider “although”."),
        .phrase("despite the fact that", ["although"], "Wordy: consider “although”."),
        .phrase("at this point in time", ["now"], "Wordy: consider “now”."),
        .phrase("at this moment in time", ["now"], "Wordy: consider “now”."),
        .phrase("at the present time", ["now", "currently"], "Wordy: consider “now” or “currently”."),
        .phrase("in the near future", ["soon"], "Wordy: consider “soon”."),
        .phrase("in the event that", ["if"], "Wordy: consider “if”."),
        .phrase("for the purpose of", ["for", "to"], "Wordy: consider “for” or “to”."),
        .phrase("with regard to", ["about", "regarding"], "Wordy: consider “about”."),
        .phrase("with respect to", ["about", "regarding"], "Wordy: consider “about”."),
        .phrase("in regard to", ["about", "regarding"], "Wordy: consider “about”."),
        .phrase("in reference to", ["about"], "Wordy: consider “about”."),
        .phrase("a large number of", ["many"], "Wordy: consider “many”."),
        .phrase("a great number of", ["many"], "Wordy: consider “many”."),
        .phrase("a great deal of", ["much"], "Wordy: consider “much”."),
        .phrase("the majority of", ["most"], "Wordy: consider “most”."),
        .phrase("a majority of", ["most"], "Wordy: consider “most”."),
        .phrase("a small number of", ["a few"], "Wordy: consider “a few”."),
        .phrase("has the ability to", ["can"], "Wordy: consider “can”."),
        .phrase("have the ability to", ["can"], "Wordy: consider “can”."),
        .phrase("is able to", ["can"], "Wordy: consider “can”.", severity: .hint),
        .phrase("are able to", ["can"], "Wordy: consider “can”.", severity: .hint),
        .phrase("make a decision", ["decide"], "Wordy: consider “decide”."),
        .phrase("made a decision", ["decided"], "Wordy: consider “decided”."),
        .phrase("come to a conclusion", ["conclude"], "Wordy: consider “conclude”."),
        .phrase("take into consideration", ["consider"], "Wordy: consider “consider”."),
        .phrase("give consideration to", ["consider"], "Wordy: consider “consider”."),
        .phrase("conduct an investigation into", ["investigate"], "Wordy: consider “investigate”."),
        .phrase("prior to", ["before"], "Wordy: consider “before”.", severity: .hint),
        .phrase("subsequent to", ["after"], "Wordy: consider “after”."),
        .phrase("in close proximity to", ["near"], "Wordy: consider “near”."),
        .phrase("in the vicinity of", ["near"], "Wordy: consider “near”."),
        .phrase("on a daily basis", ["daily"], "Wordy: consider “daily”."),
        .phrase("on a weekly basis", ["weekly"], "Wordy: consider “weekly”."),
        .phrase("on a monthly basis", ["monthly"], "Wordy: consider “monthly”."),
        .phrase("on a regular basis", ["regularly"], "Wordy: consider “regularly”."),
        .phrase("in the process of", [""], "Often unnecessary: “we are updating” instead of “we are in the process of updating”.", severity: .hint),
        .phrase("it is important to note that", [""], "Often unnecessary: state the point directly.", severity: .hint),
        .phrase("it should be noted that", [""], "Often unnecessary: state the point directly.", severity: .hint),
        .phrase("until such time as", ["until"], "Wordy: consider “until”."),
        .phrase("in the absence of", ["without"], "Wordy: consider “without”.", severity: .hint),
        .phrase("with the exception of", ["except"], "Wordy: consider “except”."),
        .phrase("in a timely manner", ["promptly"], "Wordy: consider “promptly”."),
        .phrase("is indicative of", ["indicates"], "Wordy: consider “indicates”."),
        .phrase("are indicative of", ["indicate"], "Wordy: consider “indicate”."),
        .phrase("in excess of", ["more than"], "Wordy: consider “more than”."),
        .phrase("a sufficient number of", ["enough"], "Wordy: consider “enough”."),
        .phrase("by means of", ["by"], "Wordy: consider “by”."),
        .phrase("each and every", ["each", "every"], "Redundant pairing."),
        .phrase("first and foremost", ["first"], "Redundant pairing."),
        .phrase("any and all", ["all", "any"], "Redundant pairing."),
        .phrase("whether or not", ["whether"], "“Whether” alone is often enough.", severity: .hint),
        .phrase("in this day and age", ["today"], "Wordy cliché: consider “today”."),
        .phrase("during the course of", ["during"], "Wordy: consider “during”."),
        .phrase("for a period of", ["for"], "Wordy: consider “for”.", severity: .hint),
    ]

    // MARK: - Redundancy (concision)

    static let redundancy: [PhraseEntry] = [
        .phrase("absolutely essential", ["essential"], "Redundant: “essential” is already absolute."),
        .phrase("absolutely necessary", ["necessary"], "Redundant: “necessary” is already absolute."),
        .phrase("added bonus", ["bonus"], "Redundant: a bonus is already added."),
        .phrase("advance planning", ["planning"], "Redundant: planning happens in advance."),
        .phrase("advance warning", ["warning"], "Redundant: a warning comes in advance."),
        .phrase("basic fundamentals", ["fundamentals"], "Redundant."),
        .phrase("close proximity", ["proximity"], "Redundant: proximity means closeness."),
        .phrase("collaborate together", ["collaborate"], "Redundant."),
        .phrase("combine together", ["combine"], "Redundant."),
        .phrase("join together", ["join"], "Redundant."),
        .phrase("merge together", ["merge"], "Redundant."),
        .phrase("completely eliminate", ["eliminate"], "Redundant."),
        .phrase("completely finished", ["finished"], "Redundant."),
        .phrase("end result", ["result"], "Redundant."),
        .phrase("final outcome", ["outcome"], "Redundant."),
        .phrase("free gift", ["gift"], "Redundant: gifts are free."),
        .phrase("future plans", ["plans"], "Redundant: plans concern the future."),
        .phrase("past history", ["history"], "Redundant."),
        .phrase("past experience", ["experience"], "Redundant.", severity: .hint),
        .phrase("personal opinion", ["opinion"], "Redundant.", severity: .hint),
        .phrase("repeat again", ["repeat"], "Redundant."),
        .phrase("revert back", ["revert"], "Redundant: “revert” already means go back."),
        .phrase("return back", ["return"], "Redundant."),
        .phrase("unexpected surprise", ["surprise"], "Redundant."),
        .phrase("true facts", ["facts"], "Redundant."),
        .phrase("new innovation", ["innovation"], "Redundant."),
        .phrase("still remains", ["remains"], "Redundant."),
        .phrase("general consensus", ["consensus"], "Redundant."),
        .phrase("consensus of opinion", ["consensus"], "Redundant."),
        .phrase("exact same", ["same"], "Redundant (informal).", severity: .hint),
        .phrase("ATM machine", ["ATM"], "Redundant: the M stands for “machine”."),
        .phrase("PIN number", ["PIN"], "Redundant: the N stands for “number”."),
        .phrase("LCD display", ["LCD"], "Redundant: the D stands for “display”."),
        .phrase("HIV virus", ["HIV"], "Redundant: the V stands for “virus”."),
        .phrase("brief summary", ["summary"], "Redundant: summaries are brief."),
        .phrase("plan ahead", ["plan"], "Redundant.", severity: .hint),
        .phrase("postpone until later", ["postpone"], "Redundant."),
        .phrase("mutual cooperation", ["cooperation"], "Redundant."),
        .phrase("sum total", ["total"], "Redundant."),
        .phrase("very unique", ["unique"], "“Unique” cannot be graded."),
        .phrase("most unique", ["unique"], "“Unique” cannot be graded."),
        .phrase("fellow colleague", ["colleague"], "Redundant."),
        .phrase("ask the question", ["ask"], "Redundant.", severity: .hint),
    ]

    // MARK: - Intensifiers (word choice)

    static let intensifiers: [PhraseEntry] = {
        let pairs: [(String, [String])] = [
            ("good", ["excellent", "great"]), ("bad", ["terrible", "awful"]), ("big", ["huge", "enormous"]),
            ("small", ["tiny", "minute"]), ("important", ["crucial", "essential"]), ("tired", ["exhausted"]),
            ("happy", ["delighted", "thrilled"]), ("sad", ["miserable", "heartbroken"]), ("hungry", ["starving", "ravenous"]),
            ("cold", ["freezing", "frigid"]), ("hot", ["scorching", "sweltering"]), ("difficult", ["arduous", "challenging"]),
            ("easy", ["effortless", "simple"]), ("fast", ["rapid", "swift"]), ("quick", ["swift", "rapid"]),
            ("old", ["ancient", "aged"]), ("scared", ["terrified"]), ("angry", ["furious", "livid"]),
            ("clean", ["spotless"]), ("smart", ["brilliant"]), ("beautiful", ["stunning", "gorgeous"]),
            ("clear", ["obvious", "evident"]), ("tasty", ["delicious"]), ("loud", ["deafening"]),
            ("quiet", ["silent", "hushed"]), ("rich", ["wealthy", "affluent"]), ("poor", ["destitute"]),
            ("large", ["huge", "vast"]), ("ugly", ["hideous"]), ("funny", ["hilarious"]),
            ("interesting", ["fascinating", "compelling"]), ("boring", ["tedious", "dull"]), ("strong", ["powerful", "robust"]),
            ("weak", ["feeble", "frail"]), ("worried", ["anxious", "distraught"]), ("surprised", ["astonished", "amazed"]),
        ]
        var entries: [PhraseEntry] = []
        for (adjective, replacements) in pairs {
            entries.append(.regex(#"\b(?:very|really|extremely|super)\s+"# + adjective + #"\b"#, replacements,
                                  "Consider a single, more precise word."))
        }
        return entries
    }()

    // MARK: - Clichés (style)

    static let cliches: [PhraseEntry] = [
        "at the end of the day", "think outside the box", "low-hanging fruit", "move the needle",
        "touch base", "circle back", "it goes without saying", "needless to say", "in today's fast-paced world",
        "game changer", "game-changer", "paradigm shift", "best of both worlds", "few and far between",
        "last but not least", "avoid like the plague", "better late than never", "tip of the iceberg",
        "when all is said and done", "perfect storm", "push the envelope", "level playing field",
        "hit the ground running", "back to square one", "all walks of life", "only time will tell",
        "read between the lines", "a whole new level", "take it to the next level", "deep dive",
        "win-win situation", "think big", "at the drop of a hat", "the elephant in the room",
    ].map { phrase in
        PhraseEntry.phrase(phrase, [], "Cliché: consider fresher, more specific wording.", severity: .hint)
    }

    // MARK: - Filler words (concision, off by default)

    static let fillers: [PhraseEntry] = [
        "basically", "actually", "literally", "honestly", "totally", "essentially", "kind of", "sort of",
        "definitely", "certainly", "obviously", "simply",
    ].map { word in
        PhraseEntry.phrase(word, [""], "Filler: consider removing “\(word)”.", severity: .hint)
    }

    // MARK: - Inclusive language (tone, off by default)

    static let inclusive: [PhraseEntry] = [
        .phrase("chairman", ["chair", "chairperson"], "Consider a gender-neutral term."),
        .phrase("chairmen", ["chairs", "chairpersons"], "Consider a gender-neutral term."),
        .phrase("mankind", ["humankind", "humanity"], "Consider a gender-neutral term."),
        .phrase("manpower", ["workforce", "staff"], "Consider a gender-neutral term."),
        .regex(#"\bman-?made\b"#, ["artificial", "synthetic"], "Consider a gender-neutral term."),
        .phrase("policeman", ["police officer"], "Consider a gender-neutral term."),
        .phrase("policemen", ["police officers"], "Consider a gender-neutral term."),
        .phrase("fireman", ["firefighter"], "Consider a gender-neutral term."),
        .phrase("firemen", ["firefighters"], "Consider a gender-neutral term."),
        .phrase("salesman", ["salesperson"], "Consider a gender-neutral term."),
        .phrase("businessman", ["businessperson"], "Consider a gender-neutral term."),
        .phrase("stewardess", ["flight attendant"], "Consider a gender-neutral term."),
        .phrase("mailman", ["mail carrier"], "Consider a gender-neutral term."),
        .phrase("whitelist", ["allowlist"], "Consider a more descriptive term."),
        .phrase("blacklist", ["blocklist", "denylist"], "Consider a more descriptive term."),
    ]

    // MARK: - Punctuation & typography

    static let doublePunctuation: [PhraseEntry] = [
        .regex(#"(?<![.])\.\.(?![.])"#, [".", "…"], "Two full stops: use one, or an ellipsis.", category: .punctuation, severity: .warning),
        .regex(#",{2,}"#, [","], "Repeated comma.", category: .punctuation, severity: .warning),
        .regex(#";{2,}"#, [";"], "Repeated semicolon.", category: .punctuation, severity: .warning),
        .regex(#"!{2,}"#, ["!"], "Repeated exclamation marks can feel informal.", category: .tone, severity: .hint),
        .regex(#"\?{2,}"#, ["?"], "Repeated question marks can feel informal.", category: .tone, severity: .hint),
    ]

    static let smartTypography: [PhraseEntry] = [
        .regex(#"(?<=\S) ?-- ?(?=\S)"#, ["—", " – "], "Use a dash instead of two hyphens.", category: .typography, severity: .hint),
        .regex(#"(?<!\.)\.\.\.(?!\.)"#, ["…"], "Use the ellipsis character.", category: .typography, severity: .hint),
    ]

    // MARK: - Formality

    static let contractions: [(String, [String])] = [
        ("don't", ["do not"]), ("doesn't", ["does not"]), ("didn't", ["did not"]), ("can't", ["cannot"]),
        ("won't", ["will not"]), ("isn't", ["is not"]), ("aren't", ["are not"]), ("wasn't", ["was not"]),
        ("weren't", ["were not"]), ("it's", ["it is", "it has"]), ("that's", ["that is"]), ("there's", ["there is"]),
        ("I'm", ["I am"]), ("you're", ["you are"]), ("we're", ["we are"]), ("they're", ["they are"]),
        ("I've", ["I have"]), ("we've", ["we have"]), ("they've", ["they have"]), ("you've", ["you have"]),
        ("I'll", ["I will"]), ("you'll", ["you will"]), ("we'll", ["we will"]), ("they'll", ["they will"]),
        ("I'd", ["I would", "I had"]), ("shouldn't", ["should not"]), ("wouldn't", ["would not"]),
        ("couldn't", ["could not"]), ("hasn't", ["has not"]), ("haven't", ["have not"]), ("hadn't", ["had not"]),
        ("let's", ["let us"]), ("he's", ["he is", "he has"]), ("she's", ["she is", "she has"]),
    ]

    static let slang: [(String, [String])] = [
        ("gonna", ["going to"]), ("wanna", ["want to"]), ("gotta", ["have to", "got to"]), ("kinda", ["kind of"]),
        ("sorta", ["sort of"]), ("ain't", ["is not", "are not"]), ("y'all", ["you all", "everyone"]),
        ("dunno", ["don't know"]), ("lemme", ["let me"]), ("gimme", ["give me"]), ("cuz", ["because"]),
        ("tho", ["though"]), ("thru", ["through"]), ("pls", ["please"]),
        ("plz", ["please"]), ("thx", ["thanks"]),
    ]

    // MARK: - Passive voice helpers

    static let irregularParticiples: [String] = [
        "known", "seen", "done", "given", "taken", "made", "written", "shown", "built", "found", "held", "kept",
        "left", "lost", "paid", "said", "sent", "sold", "told", "thought", "brought", "bought", "caught", "taught",
        "understood", "chosen", "driven", "eaten", "forgotten", "gotten", "hidden", "broken", "spoken", "stolen",
        "frozen", "beaten", "bitten", "born", "borne", "worn", "torn", "sworn", "drawn", "grown", "thrown", "blown",
        "flown", "led", "met", "put", "read", "run", "set", "shut", "spent", "struck", "won", "hit", "cut", "split",
        "spread", "bound", "fed", "forgiven", "overlooked", "undertaken", "withdrawn", "begun", "sung", "rung", "sunk",
    ]

    /// -ed words that are normally adjectives or not participles at all.
    static let notPassiveParticiples: Set<String> = [
        "tired", "interested", "excited", "bored", "married", "used", "supposed", "concerned", "involved", "pleased",
        "surprised", "worried", "scared", "prepared", "qualified", "based", "located", "related", "dedicated",
        "advanced", "detailed", "complicated", "experienced", "talented", "limited", "need", "seed", "bed", "red",
        "shed", "feed", "speed", "breed", "greed", "weed", "steed", "creed", "deed", "indeed", "hundred", "sacred",
        "naked", "wicked", "rugged", "ragged", "beloved", "learned", "aged", "blessed", "crooked", "dogged",
        "jagged", "wretched", "embed", "exceed", "proceed", "succeed", "agreed", "allied", "satisfied", "confused",
        "convinced", "determined", "devoted", "disappointed", "amazed", "annoyed", "ashamed", "relaxed", "stressed",
        "focused", "motivated", "organized", "organised", "sophisticated", "educated", "balanced", "renowned",
        "committed", "engaged", "frustrated", "overwhelmed", "embarrassed", "exhausted", "fed",
    ]

    // MARK: - Proper-noun capitalisation

    /// Lower-case forms that should always be capitalised. Ambiguous words (may, march, august, china,
    /// turkey, polish …) are deliberately absent.
    static let alwaysCapitalized: [String] = [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "april", "june", "july", "september", "october", "november", "december",
        "english", "french", "german", "spanish", "italian", "portuguese", "dutch", "russian", "chinese",
        "japanese", "korean", "arabic", "hindi", "american", "british", "canadian", "australian", "european",
        "african", "asian", "mexican", "irish", "scottish", "welsh", "swedish", "norwegian", "danish", "finnish",
        "greek", "christmas", "hanukkah", "ramadan", "easter",
    ]
}
