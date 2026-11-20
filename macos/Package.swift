// swift-tools-version:5.10
//
// QDVC Articulate for macOS — a fully offline writing checker: spelling,
// grammar, wording and clarity, with an optional local AI model (llama.cpp).
// Nothing leaves the Mac: the app is sandboxed without network entitlements.
//
// Build:   swift build            (or open this folder in Xcode)
// Test:    swift test
// Bundle:  scripts/build-app.sh   (sandboxed, ad-hoc signed .app, no Apple account needed)
//
// Module layout (see docs/ARCHITECTURE.md):
//   ArticulateCore  – platform-neutral checking logic (Foundation only; builds on Linux).
//   ArticulateLLM   – llama.cpp wrapper. Compiled as a stub unless Vendor/llama.xcframework exists.
//   QDVCArticulate  – the macOS app (SwiftUI + AppKit). Only declared when building on macOS.
//
import PackageDescription
import Foundation

// llama.cpp is linked only when the user has placed the prebuilt XCFramework into Vendor/.
// Nothing is downloaded by the build: see Vendor/README.md.
//
// NOTE: SwiftPM caches the result of evaluating this manifest and does not notice when the
// framework is added or removed. scripts/build-app.sh detects that and cleans .build itself;
// with plain `swift build`, run `rm -rf .build` after adding or removing the framework.
let llamaFrameworkPath = "Vendor/llama.xcframework"

#if os(macOS)
let hasLlama = FileManager.default.fileExists(atPath: Context.packageDirectory + "/" + llamaFrameworkPath)
#else
let hasLlama = false
#endif

var llmDependencies: [Target.Dependency] = ["ArticulateCore"]
var llmSwiftSettings: [SwiftSetting] = []
if hasLlama {
    llmDependencies.append("llama")
    llmSwiftSettings.append(.define("QDVC_LLAMA"))
}

var targets: [Target] = [
    .target(
        name: "ArticulateCore",
        path: "Sources/ArticulateCore"
    ),
    .target(
        name: "ArticulateLLM",
        dependencies: llmDependencies,
        path: "Sources/ArticulateLLM",
        // An explicit flag rather than `canImport(llama)`: if the framework is present but can't be
        // imported, the build fails loudly instead of silently producing an app without the AI engine.
        swiftSettings: llmSwiftSettings
    ),
    .testTarget(
        name: "ArticulateCoreTests",
        dependencies: ["ArticulateCore"],
        path: "Tests/ArticulateCoreTests"
    ),
]

if hasLlama {
    targets.append(.binaryTarget(name: "llama", path: llamaFrameworkPath))
}

var products: [Product] = [
    .library(name: "ArticulateCore", targets: ["ArticulateCore"]),
]

#if os(macOS)
targets.append(
    .executableTarget(
        name: "QDVCArticulate",
        dependencies: ["ArticulateCore", "ArticulateLLM"],
        path: "Sources/QDVCArticulate"
    )
)
products.append(.executable(name: "QDVCArticulate", targets: ["QDVCArticulate"]))
#endif

let package = Package(
    name: "QDVCArticulate",
    platforms: [.macOS(.v14)],
    products: products,
    targets: targets
)
