import Foundation

/// US ⇄ Commonwealth spelling variants, generated from stems so inflections are covered
/// (colour, colours, coloured, colouring, colourful …).
public enum DialectLexicon {
    enum Preference { case us, uk }

    private struct Pair {
        let us: String
        let uk: String
        /// Canadian preference; nil = both are accepted in Canada.
        let canada: Preference?
    }

    // -or / -our
    private static let ourStems = [
        "col", "fav", "hon", "lab", "neighb", "behavi", "hum", "flav", "rum", "harb", "vap", "savi", "arm",
        "endeav", "od", "vig", "val", "splend", "parl", "tum", "cand", "clam", "rig", "demean", "ferv", "sav",
    ]
    private static let ourSuffixes = [
        "", "s", "ed", "ing", "ful", "fully", "less", "able", "ably", "ite", "ites", "er", "ers", "hood", "hoods",
        "ly", "al", "ally",
    ]
    /// Generated forms that are spelled the same in all dialects.
    private static let invariantForms: Set<String> = ["humoral", "humorally", "armoral", "armorally", "laboral", "odoral"]

    // -ize / -ise
    private static let izeStems = [
        "organ", "real", "recogn", "apolog", "critic", "emphas", "priorit", "summar", "minim", "maxim", "optim",
        "character", "categor", "special", "final", "util", "standard", "normal", "visual", "author", "custom",
        "memor", "symbol", "sympath", "modern", "mobil", "legal", "capital", "central", "general", "harmon",
        "ideal", "industrial", "jeopard", "local", "material", "neutral", "patron", "penal", "polar", "popular",
        "rational", "revolution", "scandal", "stabil", "steril", "subsid", "synchron", "synthes", "theor",
        "trivial", "vandal", "vocal", "fertil", "global", "digit", "energ", "hospital", "human", "hypothes",
        "immun", "internal", "item", "mesmer", "monopol", "natural", "personal", "privat", "random", "serial",
        "parameter", "familiar", "commercial", "conceptual", "contextual", "criminal", "democrat", "dramat",
        "emotional", "equal", "external", "fantas", "formal", "fossil", "galvan", "individual", "liberal", "moral",
        "national", "official", "ostrac", "pasteur", "plagiar", "politic", "public", "quant", "radical", "regular",
        "satir", "scrutin", "sanit", "social", "stigmat", "terror", "traumat", "urban", "vapor", "victim",
        "agon", "bapt", "colon", "computer", "crystall", "desensit", "euthan", "evangel", "fratern",
        "glamor", "hybrid", "metabol", "miniatur", "moistur", "nasal", "oxid", "philosoph", "pressur",
        "rhapsod", "sensit", "sermon", "tantal", "token", "tyrann",
    ]
    private static let izeSuffixes = [
        "ize", "izes", "ized", "izing", "ization", "izations", "izer", "izers", "izable", "izational",
    ]

    // -yze / -yse
    private static let yzeStems = ["anal", "paral", "catal", "dial", "electrol", "hydrol", "psychoanal"]
    private static let yzeSuffixes = ["yze", "yzes", "yzed", "yzing", "yzer", "yzers"]

    // -er / -re
    private static let reStems = ["cent", "theat", "lit", "fib", "calib", "somb", "lust", "meag", "sab", "spect", "mit", "och", "sepulch"]
    private static let reSuffixes: [(String, String)] = [("er", "re"), ("ers", "res"), ("ered", "red"), ("ering", "ring")]

    // Explicit pairs (doubled consonants, Greek/Latin digraphs, misc).
    private static let explicitPairs: [Pair] = [
        // doubled l
        Pair(us: "traveled", uk: "travelled", canada: .uk), Pair(us: "traveling", uk: "travelling", canada: .uk),
        Pair(us: "traveler", uk: "traveller", canada: .uk), Pair(us: "travelers", uk: "travellers", canada: .uk),
        Pair(us: "canceled", uk: "cancelled", canada: .uk), Pair(us: "canceling", uk: "cancelling", canada: .uk),
        Pair(us: "labeled", uk: "labelled", canada: .uk), Pair(us: "labeling", uk: "labelling", canada: .uk),
        Pair(us: "modeled", uk: "modelled", canada: .uk), Pair(us: "modeling", uk: "modelling", canada: .uk),
        Pair(us: "fueled", uk: "fuelled", canada: .uk), Pair(us: "fueling", uk: "fuelling", canada: .uk),
        Pair(us: "leveled", uk: "levelled", canada: .uk), Pair(us: "leveling", uk: "levelling", canada: .uk),
        Pair(us: "signaled", uk: "signalled", canada: .uk), Pair(us: "signaling", uk: "signalling", canada: .uk),
        Pair(us: "totaled", uk: "totalled", canada: .uk), Pair(us: "totaling", uk: "totalling", canada: .uk),
        Pair(us: "marveled", uk: "marvelled", canada: .uk), Pair(us: "marveling", uk: "marvelling", canada: .uk),
        Pair(us: "marvelous", uk: "marvellous", canada: .uk), Pair(us: "jewelry", uk: "jewellery", canada: .uk),
        Pair(us: "jeweler", uk: "jeweller", canada: .uk), Pair(us: "jewelers", uk: "jewellers", canada: .uk),
        Pair(us: "counselor", uk: "counsellor", canada: .uk), Pair(us: "counselors", uk: "counsellors", canada: .uk),
        Pair(us: "counseled", uk: "counselled", canada: .uk), Pair(us: "counseling", uk: "counselling", canada: .uk),
        Pair(us: "quarreled", uk: "quarrelled", canada: .uk), Pair(us: "quarreling", uk: "quarrelling", canada: .uk),
        Pair(us: "tunneled", uk: "tunnelled", canada: .uk), Pair(us: "tunneling", uk: "tunnelling", canada: .uk),
        Pair(us: "channeled", uk: "channelled", canada: .uk), Pair(us: "channeling", uk: "channelling", canada: .uk),
        Pair(us: "dialed", uk: "dialled", canada: .uk), Pair(us: "dialing", uk: "dialling", canada: .uk),
        Pair(us: "woolen", uk: "woollen", canada: .uk), Pair(us: "rivaled", uk: "rivalled", canada: .uk),
        // single l in UK
        Pair(us: "fulfill", uk: "fulfil", canada: .us), Pair(us: "fulfills", uk: "fulfils", canada: .us),
        Pair(us: "fulfillment", uk: "fulfilment", canada: .us), Pair(us: "enroll", uk: "enrol", canada: .us),
        Pair(us: "enrolls", uk: "enrols", canada: .us), Pair(us: "enrollment", uk: "enrolment", canada: .us),
        Pair(us: "installment", uk: "instalment", canada: .us), Pair(us: "skillful", uk: "skilful", canada: .us),
        Pair(us: "willful", uk: "wilful", canada: .us), Pair(us: "distill", uk: "distil", canada: .us),
        Pair(us: "instill", uk: "instil", canada: .us),
        // misc
        Pair(us: "gray", uk: "grey", canada: nil), Pair(us: "grays", uk: "greys", canada: nil),
        Pair(us: "aluminum", uk: "aluminium", canada: .us),
        Pair(us: "defense", uk: "defence", canada: .uk), Pair(us: "defenses", uk: "defences", canada: .uk),
        Pair(us: "offense", uk: "offence", canada: .uk), Pair(us: "offenses", uk: "offences", canada: .uk),
        Pair(us: "pretense", uk: "pretence", canada: .uk),
        Pair(us: "catalog", uk: "catalogue", canada: .uk), Pair(us: "catalogs", uk: "catalogues", canada: .uk),
        Pair(us: "cataloged", uk: "catalogued", canada: .uk), Pair(us: "cataloging", uk: "cataloguing", canada: .uk),
        Pair(us: "analog", uk: "analogue", canada: .uk),
        Pair(us: "mold", uk: "mould", canada: nil), Pair(us: "molds", uk: "moulds", canada: nil),
        Pair(us: "moldy", uk: "mouldy", canada: nil), Pair(us: "molding", uk: "moulding", canada: nil),
        Pair(us: "smolder", uk: "smoulder", canada: nil), Pair(us: "plow", uk: "plough", canada: nil),
        Pair(us: "skeptic", uk: "sceptic", canada: .us), Pair(us: "skeptical", uk: "sceptical", canada: .us),
        Pair(us: "skepticism", uk: "scepticism", canada: .us),
        Pair(us: "aging", uk: "ageing", canada: nil),
        Pair(us: "pajamas", uk: "pyjamas", canada: .us), Pair(us: "cozy", uk: "cosy", canada: .us),
        Pair(us: "airplane", uk: "aeroplane", canada: .us), Pair(us: "airplanes", uk: "aeroplanes", canada: .us),
        Pair(us: "mustache", uk: "moustache", canada: .uk), Pair(us: "sulfur", uk: "sulphur", canada: nil),
        Pair(us: "fetus", uk: "foetus", canada: .us), Pair(us: "estrogen", uk: "oestrogen", canada: .us),
        Pair(us: "anemia", uk: "anaemia", canada: .us), Pair(us: "anesthesia", uk: "anaesthesia", canada: .us),
        Pair(us: "anesthetic", uk: "anaesthetic", canada: .us), Pair(us: "pediatric", uk: "paediatric", canada: .us),
        Pair(us: "pediatrician", uk: "paediatrician", canada: .us), Pair(us: "leukemia", uk: "leukaemia", canada: .us),
        Pair(us: "diarrhea", uk: "diarrhoea", canada: .us), Pair(us: "orthopedic", uk: "orthopaedic", canada: .us),
        Pair(us: "hemoglobin", uk: "haemoglobin", canada: .us),
        Pair(us: "maneuver", uk: "manoeuvre", canada: .uk), Pair(us: "maneuvers", uk: "manoeuvres", canada: .uk),
        Pair(us: "maneuvered", uk: "manoeuvred", canada: .uk), Pair(us: "maneuvering", uk: "manoeuvring", canada: .uk),
        Pair(us: "tidbit", uk: "titbit", canada: .us), Pair(us: "artifact", uk: "artefact", canada: .us),
        Pair(us: "artifacts", uk: "artefacts", canada: .us), Pair(us: "yogurt", uk: "yoghurt", canada: nil),
        Pair(us: "omelet", uk: "omelette", canada: .uk), Pair(us: "acknowledgment", uk: "acknowledgement", canada: nil),
    ]

    private struct Preferences {
        let our: Preference
        let ize: Preference
        let yze: Preference
        let re: Preference
    }

    private static func preferences(for dialect: Dialect) -> Preferences {
        switch dialect {
        case .us: return Preferences(our: .us, ize: .us, yze: .us, re: .us)
        case .gb: return Preferences(our: .uk, ize: .uk, yze: .uk, re: .uk)
        case .gbOxford: return Preferences(our: .uk, ize: .us, yze: .uk, re: .uk)
        case .ca: return Preferences(our: .uk, ize: .us, yze: .us, re: .uk)
        case .au: return Preferences(our: .uk, ize: .uk, yze: .uk, re: .uk)
        }
    }

    /// Map from dispreferred spelling → preferred spelling (lowercased) for one dialect.
    private static func build(_ dialect: Dialect) -> [String: String] {
        let prefs = preferences(for: dialect)
        var map: [String: String] = [:]

        func add(us: String, uk: String, prefer: Preference?) {
            guard let prefer, us != uk, !invariantForms.contains(us) else { return }
            switch prefer {
            case .us: map[uk] = us
            case .uk: map[us] = uk
            }
        }

        for stem in ourStems {
            for suffix in ourSuffixes {
                add(us: stem + "or" + suffix, uk: stem + "our" + suffix, prefer: prefs.our)
            }
        }
        for stem in izeStems {
            for suffix in izeSuffixes {
                let uk = suffix.replacingOccurrences(of: "iz", with: "is")
                add(us: stem + suffix, uk: stem + uk, prefer: prefs.ize)
            }
        }
        for stem in yzeStems {
            for suffix in yzeSuffixes {
                let uk = suffix.replacingOccurrences(of: "yz", with: "ys")
                add(us: stem + suffix, uk: stem + uk, prefer: prefs.yze)
            }
        }
        for stem in reStems {
            for (usSuffix, ukSuffix) in reSuffixes {
                add(us: stem + usSuffix, uk: stem + ukSuffix, prefer: prefs.re)
            }
        }
        for pair in explicitPairs {
            let prefer: Preference?
            switch dialect {
            case .us: prefer = .us
            case .gb, .gbOxford, .au: prefer = .uk
            case .ca: prefer = pair.canada
            }
            add(us: pair.us, uk: pair.uk, prefer: prefer)
        }
        return map
    }

    private static let maps: [Dialect: [String: String]] = {
        var result: [Dialect: [String: String]] = [:]
        for dialect in Dialect.allCases { result[dialect] = build(dialect) }
        return result
    }()

    /// Preferred spelling of `word` for `dialect`, or nil if the word is already fine.
    public static func preferredSpelling(of word: String, for dialect: Dialect) -> String? {
        guard let preferred = maps[dialect]?[word.lowercased()] else { return nil }
        return CaseStyle.match(preferred, to: word)
    }

    /// True if `replacement` would introduce a spelling that is wrong for `dialect`
    /// (used to reject language-model suggestions that "correct" colour → color for UK users).
    public static func introducesDispreferredSpelling(_ replacement: String, for dialect: Dialect) -> Bool {
        guard let map = maps[dialect] else { return false }
        for word in replacement.lowercased().split(whereSeparator: { !$0.isLetter }) where map[String(word)] != nil {
            return true
        }
        return false
    }
}
