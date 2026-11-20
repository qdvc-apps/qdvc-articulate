import Foundation

/// GBNF grammar that forces the model's output to be exactly the JSON shape we parse.
/// With constrained decoding the model physically cannot produce chatter, Markdown fences,
/// "thinking" blocks or malformed JSON.
public enum JSONGrammar {
    public static let issues: String = #"""
    root        ::= "{" ws "\"issues\"" ws ":" ws "[" ws issue-list? ws "]" ws "}"
    issue-list  ::= issue ( ws "," ws issue )*
    issue       ::= "{" ws "\"original\"" ws ":" ws string ws "," ws "\"replacement\"" ws ":" ws string ws "," ws "\"category\"" ws ":" ws category ws "," ws "\"explanation\"" ws ":" ws string ws "}"
    category    ::= "\"spelling\"" | "\"grammar\"" | "\"punctuation\"" | "\"wordChoice\"" | "\"clarity\"" | "\"concision\"" | "\"style\"" | "\"tone\""
    string      ::= "\"" char* "\""
    char        ::= [^"\\\x00-\x1F] | "\\" ( ["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] )
    ws          ::= [ \t\n]{0,8}
    """#
}
