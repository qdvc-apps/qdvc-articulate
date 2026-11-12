import SwiftUI
import AppKit
import ArticulateCore

/// NSTextView configured for private, plain-text editing with issue underlines.
final class ArticulateTextView: NSTextView {
    weak var controller: EditorController?
    private var appliedFontKey = ""

    func configureForPrivateEditing() {
        isRichText = false
        importsGraphics = false
        allowsUndo = true
        usesFindBar = true
        isIncrementalSearchingEnabled = true
        allowsDocumentBackgroundColorChange = false
        usesInspectorBar = false
        usesRuler = false
        drawsBackground = true
        backgroundColor = .textBackgroundColor
        textColor = .textColor
        textContainerInset = NSSize(width: 28, height: 22)

        // We do our own checking; disable AppKit's to avoid double underlines and silent edits.
        isContinuousSpellCheckingEnabled = false
        isGrammarCheckingEnabled = false
        isAutomaticSpellingCorrectionEnabled = false
        isAutomaticTextReplacementEnabled = false
        isAutomaticQuoteSubstitutionEnabled = false
        isAutomaticDashSubstitutionEnabled = false
        isAutomaticTextCompletionEnabled = false
        isAutomaticLinkDetectionEnabled = false
        isAutomaticDataDetectionEnabled = false
        inlinePredictionType = .no

        // Writing Tools can hand text to an external service (e.g. ChatGPT) if the user enabled that
        // integration system-wide, so it is switched off for this view.
        if #available(macOS 15.0, *) {
            writingToolsBehavior = .none
        }
    }

    func applyFont(size: Double, monospaced: Bool) {
        let key = "\(size)|\(monospaced)"
        guard key != appliedFontKey else { return }
        appliedFontKey = key

        let font: NSFont = monospaced
            ? .monospacedSystemFont(ofSize: size, weight: .regular)
            : .systemFont(ofSize: size)
        let paragraph = NSMutableParagraphStyle()
        paragraph.lineHeightMultiple = 1.25
        paragraph.paragraphSpacing = size * 0.35
        self.font = font
        defaultParagraphStyle = paragraph
        typingAttributes = [.font: font, .foregroundColor: NSColor.textColor, .paragraphStyle: paragraph]
        applyBaseAttributes()
    }

    func applyBaseAttributes() {
        guard let storage = textStorage, storage.length > 0 else { return }
        storage.beginEditing()
        storage.setAttributes(typingAttributes, range: NSRange(location: 0, length: storage.length))
        storage.endEditing()
    }

    /// Never offer this view's text to the system Services menu (which could pass it to other apps).
    override func validRequestor(forSendType sendType: NSPasteboard.PasteboardType?, returnType: NSPasteboard.PasteboardType?) -> Any? {
        nil
    }

    /// A minimal context menu: suggestions first, then basic editing.
    /// AppKit's default menu (Share, Services, "Search With…", Writing Tools) is replaced on purpose.
    override func menu(for event: NSEvent) -> NSMenu? {
        let point = convert(event.locationInWindow, from: nil)
        let index = characterIndexForInsertion(at: point)
        let menu = NSMenu()

        if let controller, let issue = controller.issue(at: index) {
            let header = NSMenuItem(title: issue.message, action: nil, keyEquivalent: "")
            header.isEnabled = false
            menu.addItem(header)
            for suggestion in issue.suggestions.prefix(6) {
                let title = suggestion.isEmpty
                    ? "Remove “\(issue.original.trimmingCharacters(in: .whitespaces))”"
                    : suggestion.replacingOccurrences(of: "\n", with: "↩︎")
                menu.addItem(ActionMenuItem(title: title) { [weak controller] in
                    controller?.apply(issue, suggestion: suggestion)
                })
            }
            menu.addItem(ActionMenuItem(title: "Ignore") { [weak controller] in
                controller?.ignore(issue)
            })
            if issue.category == .spelling {
                menu.addItem(ActionMenuItem(title: "Add “\(issue.original)” to Dictionary") { [weak controller] in
                    controller?.addToDictionary(issue)
                })
            }
            menu.addItem(.separator())
        }

        for (title, action) in [
            ("Cut", #selector(NSText.cut(_:))),
            ("Copy", #selector(NSText.copy(_:))),
            ("Paste", #selector(NSText.paste(_:))),
        ] {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
            item.target = self
            menu.addItem(item)
        }
        menu.addItem(.separator())
        let selectAllItem = NSMenuItem(title: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "")
        selectAllItem.target = self
        menu.addItem(selectAllItem)
        return menu
    }
}

/// NSMenuItem that runs a closure.
final class ActionMenuItem: NSMenuItem {
    private let handler: () -> Void

    init(title: String, handler: @escaping () -> Void) {
        self.handler = handler
        super.init(title: title, action: #selector(fire), keyEquivalent: "")
        target = self
    }

    required init(coder: NSCoder) {
        fatalError("init(coder:) is not supported")
    }

    @objc private func fire() {
        handler()
    }
}

/// SwiftUI wrapper around `ArticulateTextView`.
struct EditorTextView: NSViewRepresentable {
    @Binding var text: String
    let controller: EditorController
    let fontSize: Double
    let monospaced: Bool

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text, controller: controller)
    }

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.autohidesScrollers = true
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = true

        // TextKit 1 is used deliberately: it supports temporary attributes for underlines.
        let textView = ArticulateTextView(usingTextLayoutManager: false)
        textView.configureForPrivateEditing()
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.minSize = NSSize(width: 0, height: 0)
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(width: 0, height: CGFloat.greatestFiniteMagnitude)

        textView.applyFont(size: fontSize, monospaced: monospaced)
        textView.string = text
        textView.applyBaseAttributes()

        textView.controller = controller
        textView.delegate = context.coordinator
        scrollView.documentView = textView

        controller.textView = textView
        controller.load(text: text)
        return scrollView
    }

    /// Always take exactly the space SwiftUI offers: the text must never decide the window's width
    /// (the rule in the other QDVC macOS apps' docs/DESIGN.md). Lines wrap to the width given.
    func sizeThatFits(_ proposal: ProposedViewSize, nsView: NSScrollView, context: Context) -> CGSize? {
        CGSize(width: proposal.width ?? 480, height: proposal.height ?? 360)
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        context.coordinator.text = $text
        guard let textView = scrollView.documentView as? ArticulateTextView else { return }
        textView.applyFont(size: fontSize, monospaced: monospaced)
        if textView.string != text {
            textView.string = text
            textView.applyBaseAttributes()
            // Defer: publishing controller changes during a SwiftUI view update is not allowed.
            let newText = text
            let controller = controller
            Task { @MainActor in
                controller.textReplacedExternally(newText)
            }
        }
    }

    @MainActor
    final class Coordinator: NSObject, NSTextViewDelegate {
        var text: Binding<String>
        let controller: EditorController

        init(text: Binding<String>, controller: EditorController) {
            self.text = text
            self.controller = controller
        }

        func textView(_ textView: NSTextView, shouldChangeTextIn affectedCharRange: NSRange, replacementString: String?) -> Bool {
            if let replacementString {
                controller.willEdit(range: affectedCharRange, replacementLength: (replacementString as NSString).length)
            }
            return true
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            let newText = textView.string
            text.wrappedValue = newText
            controller.textDidChange(newText)
        }

        func textViewDidChangeSelection(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            controller.selectionChanged(textView.selectedRange())
        }
    }
}
