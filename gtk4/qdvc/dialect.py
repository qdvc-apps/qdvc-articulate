"""US ⇄ Commonwealth spelling variants: a port of Rules/DialectLexicon.swift.

Generated from stems so inflections are covered (colour, colours, coloured,
colouring, colourful …).
"""

from __future__ import annotations

from .model import Dialect
from .textutil import match_case

US, UK = "us", "uk"

# -or / -our
OUR_STEMS = [
    "col", "fav", "hon", "lab", "neighb", "behavi", "hum", "flav", "rum", "harb", "vap", "savi",
    "arm", "endeav", "od", "vig", "val", "splend", "parl", "tum", "cand", "clam", "rig", "demean",
    "ferv", "sav",
]
OUR_SUFFIXES = [
    "", "s", "ed", "ing", "ful", "fully", "less", "able", "ably", "ite", "ites", "er",
    "ers", "hood", "hoods", "ly", "al", "ally",
]
#: Generated forms that are spelled the same in all dialects.
INVARIANT_FORMS = frozenset({"humoral", "humorally", "armoral", "armorally", "laboral", "odoral"})

# -ize / -ise
IZE_STEMS = [
    "organ", "real", "recogn", "apolog", "critic", "emphas", "priorit", "summar", "minim", "maxim",
    "optim", "character", "categor", "special", "final", "util", "standard", "normal", "visual", "author",
    "custom", "memor", "symbol", "sympath", "modern", "mobil", "legal", "capital", "central", "general",
    "harmon", "ideal", "industrial", "jeopard", "local", "material", "neutral", "patron", "penal", "polar",
    "popular", "rational", "revolution", "scandal", "stabil", "steril", "subsid", "synchron", "synthes", "theor",
    "trivial", "vandal", "vocal", "fertil", "global", "digit", "energ", "hospital", "human", "hypothes",
    "immun", "internal", "item", "mesmer", "monopol", "natural", "personal", "privat", "random", "serial",
    "parameter", "familiar", "commercial", "conceptual", "contextual", "criminal", "democrat", "dramat", "emotional", "equal",
    "external", "fantas", "formal", "fossil", "galvan", "individual", "liberal", "moral", "national", "official",
    "ostrac", "pasteur", "plagiar", "politic", "public", "quant", "radical", "regular", "satir", "scrutin",
    "sanit", "social", "stigmat", "terror", "traumat", "urban", "vapor", "victim", "agon", "bapt",
    "colon", "computer", "crystall", "desensit", "euthan", "evangel", "fratern", "glamor", "hybrid", "metabol",
    "miniatur", "moistur", "nasal", "oxid", "philosoph", "pressur", "rhapsod", "sensit", "sermon", "tantal",
    "token", "tyrann",
]
IZE_SUFFIXES = [
    "ize", "izes", "ized", "izing", "ization", "izations", "izer", "izers", "izable", "izational",
]

# -yze / -yse
YZE_STEMS = [
    "anal", "paral", "catal", "dial", "electrol", "hydrol", "psychoanal",
]
YZE_SUFFIXES = [
    "yze", "yzes", "yzed", "yzing", "yzer", "yzers",
]

# -er / -re
RE_STEMS = [
    "cent", "theat", "lit", "fib", "calib", "somb", "lust", "meag", "sab", "spect", "mit", "och",
    "sepulch",
]
RE_SUFFIXES = [("er", "re"), ("ers", "res"), ("ered", "red"), ("ering", "ring")]

#: Explicit pairs (doubled consonants, Greek/Latin digraphs, misc): (US, UK, Canadian preference or None
#: when both are accepted in Canada).
EXPLICIT_PAIRS = [
    ("traveled", "travelled", "uk"), ("traveling", "travelling", "uk"), ("traveler", "traveller", "uk"),
    ("travelers", "travellers", "uk"), ("canceled", "cancelled", "uk"), ("canceling", "cancelling", "uk"),
    ("labeled", "labelled", "uk"), ("labeling", "labelling", "uk"), ("modeled", "modelled", "uk"),
    ("modeling", "modelling", "uk"), ("fueled", "fuelled", "uk"), ("fueling", "fuelling", "uk"),
    ("leveled", "levelled", "uk"), ("leveling", "levelling", "uk"), ("signaled", "signalled", "uk"),
    ("signaling", "signalling", "uk"), ("totaled", "totalled", "uk"), ("totaling", "totalling", "uk"),
    ("marveled", "marvelled", "uk"), ("marveling", "marvelling", "uk"), ("marvelous", "marvellous", "uk"),
    ("jewelry", "jewellery", "uk"), ("jeweler", "jeweller", "uk"), ("jewelers", "jewellers", "uk"),
    ("counselor", "counsellor", "uk"), ("counselors", "counsellors", "uk"), ("counseled", "counselled", "uk"),
    ("counseling", "counselling", "uk"), ("quarreled", "quarrelled", "uk"), ("quarreling", "quarrelling", "uk"),
    ("tunneled", "tunnelled", "uk"), ("tunneling", "tunnelling", "uk"), ("channeled", "channelled", "uk"),
    ("channeling", "channelling", "uk"), ("dialed", "dialled", "uk"), ("dialing", "dialling", "uk"),
    ("woolen", "woollen", "uk"), ("rivaled", "rivalled", "uk"), ("fulfill", "fulfil", "us"),
    ("fulfills", "fulfils", "us"), ("fulfillment", "fulfilment", "us"), ("enroll", "enrol", "us"),
    ("enrolls", "enrols", "us"), ("enrollment", "enrolment", "us"), ("installment", "instalment", "us"),
    ("skillful", "skilful", "us"), ("willful", "wilful", "us"), ("distill", "distil", "us"),
    ("instill", "instil", "us"), ("gray", "grey", None), ("grays", "greys", None),
    ("aluminum", "aluminium", "us"), ("defense", "defence", "uk"), ("defenses", "defences", "uk"),
    ("offense", "offence", "uk"), ("offenses", "offences", "uk"), ("pretense", "pretence", "uk"),
    ("catalog", "catalogue", "uk"), ("catalogs", "catalogues", "uk"), ("cataloged", "catalogued", "uk"),
    ("cataloging", "cataloguing", "uk"), ("analog", "analogue", "uk"), ("mold", "mould", None),
    ("molds", "moulds", None), ("moldy", "mouldy", None), ("molding", "moulding", None),
    ("smolder", "smoulder", None), ("plow", "plough", None), ("skeptic", "sceptic", "us"),
    ("skeptical", "sceptical", "us"), ("skepticism", "scepticism", "us"), ("aging", "ageing", None),
    ("pajamas", "pyjamas", "us"), ("cozy", "cosy", "us"), ("airplane", "aeroplane", "us"),
    ("airplanes", "aeroplanes", "us"), ("mustache", "moustache", "uk"), ("sulfur", "sulphur", None),
    ("fetus", "foetus", "us"), ("estrogen", "oestrogen", "us"), ("anemia", "anaemia", "us"),
    ("anesthesia", "anaesthesia", "us"), ("anesthetic", "anaesthetic", "us"), ("pediatric", "paediatric", "us"),
    ("pediatrician", "paediatrician", "us"), ("leukemia", "leukaemia", "us"), ("diarrhea", "diarrhoea", "us"),
    ("orthopedic", "orthopaedic", "us"), ("hemoglobin", "haemoglobin", "us"), ("maneuver", "manoeuvre", "uk"),
    ("maneuvers", "manoeuvres", "uk"), ("maneuvered", "manoeuvred", "uk"), ("maneuvering", "manoeuvring", "uk"),
    ("tidbit", "titbit", "us"), ("artifact", "artefact", "us"), ("artifacts", "artefacts", "us"),
    ("yogurt", "yoghurt", None), ("omelet", "omelette", "uk"), ("acknowledgment", "acknowledgement", None),
]

#: Which side each dialect prefers for -our, -ize, -yze and -re.
_PREFERENCES = {
    Dialect.US: dict(our=US, ize=US, yze=US, re=US),
    Dialect.GB: dict(our=UK, ize=UK, yze=UK, re=UK),
    Dialect.GB_OXFORD: dict(our=UK, ize=US, yze=UK, re=UK),
    Dialect.CA: dict(our=UK, ize=US, yze=US, re=UK),
    Dialect.AU: dict(our=UK, ize=UK, yze=UK, re=UK),
}


def _build(dialect: Dialect) -> dict[str, str]:
    """Map from dispreferred spelling → preferred spelling (lowercased) for one dialect."""
    prefs = _PREFERENCES[dialect]
    table: dict[str, str] = {}

    def add(us: str, uk: str, prefer: str | None) -> None:
        if prefer is None or us == uk or us in INVARIANT_FORMS:
            return
        if prefer == US:
            table[uk] = us
        else:
            table[us] = uk

    for stem in OUR_STEMS:
        for suffix in OUR_SUFFIXES:
            add(stem + "or" + suffix, stem + "our" + suffix, prefs["our"])
    for stem in IZE_STEMS:
        for suffix in IZE_SUFFIXES:
            add(stem + suffix, stem + suffix.replace("iz", "is"), prefs["ize"])
    for stem in YZE_STEMS:
        for suffix in YZE_SUFFIXES:
            add(stem + suffix, stem + suffix.replace("yz", "ys"), prefs["yze"])
    for stem in RE_STEMS:
        for us_suffix, uk_suffix in RE_SUFFIXES:
            add(stem + us_suffix, stem + uk_suffix, prefs["re"])
    for us, uk, canada in EXPLICIT_PAIRS:
        if dialect is Dialect.US:
            prefer = US
        elif dialect is Dialect.CA:
            prefer = canada
        else:
            prefer = UK
        add(us, uk, prefer)
    return table


_MAPS = {d: _build(d) for d in Dialect}


def preferred_spelling(word: str, dialect: Dialect) -> str | None:
    """Preferred spelling of `word` for `dialect`, or None if the word is already fine."""
    preferred = _MAPS[dialect].get(word.lower())
    return None if preferred is None else match_case(preferred, word)


def introduces_dispreferred_spelling(replacement: str, dialect: Dialect) -> bool:
    """True if `replacement` would introduce a spelling that is wrong for `dialect` (used to reject
    language-model suggestions that "correct" colour → color for UK users)."""
    table = _MAPS[dialect]
    word = []
    for ch in replacement.lower() + " ":
        if ch.isalpha():
            word.append(ch)
        elif word:
            if "".join(word) in table:
                return True
            word = []
    return False
