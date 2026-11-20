import SwiftUI
import ArticulateCore

/// The right-hand inspector listing all current issues.
struct IssueListView: View {
    @ObservedObject var controller: EditorController

    var body: some View {
        VStack(spacing: 0) {
            GroupFilterBar(controller: controller)
            Divider()
            if controller.visibleIssues.isEmpty {
                EmptyIssuesView(hasHiddenGroups: !controller.hiddenGroups.isEmpty, aiState: controller.aiState)
            } else {
                ScrollViewReader { proxy in
                    List(selection: selection) {
                        ForEach(controller.visibleIssues) { issue in
                            IssueRow(issue: issue, controller: controller, isFocused: issue.id == controller.focusedIssueID)
                                .tag(issue.id)
                                .id(issue.id)
                        }
                    }
                    .listStyle(.inset)
                    .onChange(of: controller.focusedIssueID) { _, id in
                        guard let id else { return }
                        withAnimation(.easeInOut(duration: 0.2)) {
                            proxy.scrollTo(id, anchor: .center)
                        }
                    }
                }
            }
        }
    }

    private var selection: Binding<UUID?> {
        Binding(
            get: { controller.focusedIssueID },
            set: { id in
                guard let id, id != controller.focusedIssueID,
                      let issue = controller.issues.first(where: { $0.id == id }) else { return }
                controller.focus(issue)
            }
        )
    }
}

private struct GroupFilterBar: View {
    @ObservedObject var controller: EditorController

    var body: some View {
        HStack(spacing: 6) {
            ForEach(IssueGroup.allCases) { group in
                let hidden = controller.hiddenGroups.contains(group)
                Button {
                    if hidden {
                        controller.hiddenGroups.remove(group)
                    } else {
                        controller.hiddenGroups.insert(group)
                    }
                } label: {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(IssueStyle.color(for: group))
                            .frame(width: 8, height: 8)
                            .opacity(hidden ? 0.3 : 1)
                        Text("\(controller.count(in: group))")
                            .monospacedDigit()
                            .foregroundStyle(hidden ? HierarchicalShapeStyle.tertiary : HierarchicalShapeStyle.primary)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(HierarchicalShapeStyle.quaternary.opacity(hidden ? 0.3 : 0.8), in: Capsule())
                }
                .buttonStyle(.plain)
                .help("\(group.displayName): \(hidden ? "hidden — click to show" : "click to hide")")
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }
}

private struct EmptyIssuesView: View {
    let hasHiddenGroups: Bool
    let aiState: EditorController.AIState

    var body: some View {
        VStack(spacing: 10) {
            Spacer()
            Image(systemName: "checkmark.circle")
                .font(.system(size: 34, weight: .light))
                .foregroundStyle(.secondary)
            Text(hasHiddenGroups ? "No issues in the visible categories" : "No issues found")
                .font(.headline)
            Text(hint)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var hint: String {
        switch aiState {
        case .finished: return "The AI review found nothing more to improve."
        case .running: return "The AI review is still running…"
        default: return "Quick checks run as you type. Press ⇧⌘K for an in-depth AI review."
        }
    }
}

private struct IssueRow: View {
    let issue: Issue
    let controller: EditorController
    let isFocused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle()
                    .fill(IssueStyle.color(for: issue.category.group))
                    .frame(width: 8, height: 8)
                Text(issue.category.displayName)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                Text(issue.source.displayName)
                    .font(.caption2)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(.quaternary, in: Capsule())
                    .foregroundStyle(.secondary)
            }

            Text(issue.message)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)

            if !issue.suggestions.isEmpty {
                Text(issue.original.excerpt())
                    .font(.callout)
                    .strikethrough(true, color: IssueStyle.color(for: issue.category.group))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)

                VStack(alignment: .leading, spacing: 4) {
                    ForEach(Array(issue.suggestions.prefix(isFocused ? 5 : 2).enumerated()), id: \.offset) { _, suggestion in
                        Button {
                            controller.apply(issue, suggestion: suggestion)
                        } label: {
                            Text(suggestion.isEmpty ? "Remove" : suggestion.excerpt())
                                .lineLimit(2)
                                .multilineTextAlignment(.leading)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(IssueStyle.color(for: issue.category.group))
                        .controlSize(.small)
                    }
                }
            } else {
                Text(issue.original.excerpt())
                    .font(.callout.italic())
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            HStack(spacing: 12) {
                Button("Ignore") { controller.ignore(issue) }
                if issue.category == .spelling {
                    Button("Add to Dictionary") { controller.addToDictionary(issue) }
                }
            }
            .buttonStyle(.borderless)
            .font(.caption)
        }
        .padding(.vertical, 6)
        .contentShape(Rectangle())
    }
}
