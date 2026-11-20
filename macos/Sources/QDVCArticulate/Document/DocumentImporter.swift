import AppKit
import UniformTypeIdentifiers

/// Converts rich documents to plain text using AppKit's local text importers.
///
/// HTML and web archives are deliberately NOT supported: AppKit imports them through WebKit,
/// which may try to fetch remote resources referenced by the document.
enum DocumentImporter {
    enum ImportError: LocalizedError {
        case unsupported(String)

        var errorDescription: String? {
            switch self {
            case .unsupported(let ext):
                return "“.\(ext)” files can’t be imported. Supported: .docx, .doc, .odt, .rtf, .rtfd, .txt, .md."
            }
        }
    }

    static var importableTypes: [UTType] {
        [
            UTType("org.openxmlformats.wordprocessingml.document"),
            UTType("com.microsoft.word.doc"),
            UTType("org.oasis-open.opendocument.text"),
            .rtf,
            .rtfd,
            .plainText,
            .markdownText,
        ].compactMap { $0 }
    }

    static func importText(from url: URL) throws -> String {
        let ext = url.pathExtension.lowercased()
        let type: NSAttributedString.DocumentType
        switch ext {
        case "docx": type = .officeOpenXML
        case "doc": type = .docFormat
        case "odt": type = .openDocument
        case "rtf": type = .rtf
        case "rtfd": type = .rtfd
        case "txt", "text", "md", "markdown":
            return TextDocument.decode(try Data(contentsOf: url))
        default:
            throw ImportError.unsupported(ext)
        }
        let attributed = try NSAttributedString(url: url, options: [.documentType: type], documentAttributes: nil)
        return attributed.string
            .replacingOccurrences(of: "\u{FFFC}", with: "")      // attachment placeholders
            .replacingOccurrences(of: "\u{2028}", with: "\n")    // line separators
            .replacingOccurrences(of: "\r\n", with: "\n")
    }
}
