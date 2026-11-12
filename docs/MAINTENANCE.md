# Maintenance

## 1. Building

### 1.0 Toolchain

Build with full Xcode. From Xcode 27, SwiftUI's `@State` is a macro whose
implementation (the SwiftUIMacros compiler plugin) ships with Xcode, so the
Command Line Tools or a swift.org toolchain fail with "plugin for module
'SwiftUIMacros' not found". `scripts/build-app.sh` therefore sets
`DEVELOPER_DIR` to the newest installed Xcode when `xcode-select` points at
the Command Line Tools, runs `xcrun swift`, prints the compiler and SDK
versions, and warns when the SDK is older than 26 (no Liquid Glass). An
explicit `DEVELOPER_DIR` is respected. The same block is used in the other
QDVC macOS apps (it is marked "shared … keep in step" in the script); keep
them in step.

AppKit decides on Liquid Glass from the SDK version recorded in the
executable's `LC_BUILD_VERSION`. `swift build` records the deployment target
there (`sdk 14.0`), so after copying the executable into the bundle the
script rewrites that field with `vtool -set-build-version macos <minos>
<sdk> -replace`, before signing. Check with `vtool -show-build`.

The window uses only standard SwiftUI/AppKit chrome (toolbar, inspector,
status bar on `.bar` material), so it picks up Liquid Glass without custom
styling. Don't paint opaque backgrounds behind the toolbar or inspector.

### 1.1 Signing and isolation (specific to this app)

Unlike the other QDVC apps, QDVC Articulate is signed with
`Resources/QDVCArticulate.entitlements`: App Sandbox on, user-selected file
access and app-scoped bookmarks (for the GGUF model), and **no network
entitlement**. `scripts/verify-isolation.sh` runs before the build (on the
entitlements file) and after signing (on the signed app). It fails on any
network entitlement, sandbox temporary exception,
`disable-library-validation`, or App Transport Security exception. See
docs/PRIVACY.md.

The sandbox container is keyed to the bundle identifier
(`org.qdvc.articulate.mac`). Changing the identifier gives the app a fresh
container, which means fresh settings and the model file has to be chosen again.

Ad-hoc signing can't use the Hardened Runtime, because library validation
rejects ad-hoc signed frameworks. The script adds `--options runtime` only
when `SIGN_IDENTITY` names a real certificate.

### 1.2 llama.cpp

`Package.swift` links `Vendor/llama.xcframework` only if it exists (see
Vendor/README.md), and then defines `QDVC_LLAMA` for `ArticulateLLM`.
`LlamaEngine.swift` uses `#if QDVC_LLAMA`, not `#if canImport(llama)`, so a
framework that can't be imported is a build error instead of a quiet stub.

SwiftPM caches its evaluation of the manifest and doesn't notice the
framework being added, removed or replaced. It then keeps building the
previous way, and the app says it has no AI engine even though the framework
is in `Vendor/`. The build script writes a fingerprint of `Vendor/llama.xcframework`
(file names, sizes and dates, or "absent") to `.build/qdvc-llama-state`, and
removes `.build` when the fingerprint changes. After building, it checks with
`otool -L` that the executable really links `llama.framework`, and fails
otherwise. It copies `llama.framework` into `Contents/Frameworks`, from the
build products, or from the XCFramework's macOS slice if SwiftPM didn't copy
it. It then adds the `@executable_path/../Frameworks` rpath and signs the
framework before the app. `Sources/ArticulateLLM/LlamaEngine.swift`
is the only file that calls the llama.cpp C API. When a llama.cpp update
renames something, that file is where the errors appear.

### 1.3 App icon

`tools/make_icon.py` writes `Resources/AppIcon.svg` and
`Resources/AppIcon.icns` (needs `rsvg-convert`). The design is a glossy green
bubble with a white tick on a pale green gradient, in the "Meadow" palette,
with Apple's template geometry, matching the other QDVC apps. `--preview` also
writes `build/icon-preview.png`.

The 16 and 32 px images are written in the classic formats (`is32`/`s8mk`,
`il32`/`l8mk`: run-length-encoded RGB plus an alpha mask). Larger sizes are
PNG. Don't put PNG under `icp4`/`icp5`: Apple defines those codes as PNG,
JPEG 2000 *or* raw RGB, and Finder's list view read the PNG bytes as raw RGB,
which showed as a garbled 16 px icon. Finder caches icons. `--install` touches
the installed app so Finder picks up a new icon. If an old one lingers, run
`killall Finder Dock`.

## 2. Pitfalls (learned in the sibling apps)

- **Public initialisers.** Public structs in `ArticulateCore` that the app
  creates need an explicit `public init`. Swift's automatic memberwise
  initialiser is `internal`, so the app module can't call it.
- **Name clashes.** The app imports SwiftUI, AppKit and Foundation together
  with the core. Check new public type names against them. QDVC Progress
  hit `GridRow`, and Response Letter avoided `Section`.
- **Text view width.** A text view must never decide the window's width.
  `EditorTextView.sizeThatFits` returns exactly the proposed size, and
  the text container tracks the view's width.
- **Underlines** use TextKit 1 temporary attributes, which don't touch the
  text or undo. The text view is therefore created with
  `NSTextView(usingTextLayoutManager: false)`. Don't switch it to TextKit 2
  without replacing the underline drawing.
- **Collecting errors:** `scripts/build-app.sh 2>&1 | grep -E "error:" | sort -u`.

## 3. Behaviour to preserve (tests)

- Rules: the cases in `RuleTests` (a/an incl. acronyms and "un-" words,
  "could of" but not "could of course", dialect spelling incl. Oxford -ize,
  deletions taking one adjacent space).
- AI pipeline: truncated and fenced JSON still parse; quotes are anchored
  case- and smart-quote-insensitively; suggestions that switch the
  variety of English are dropped; unchanged paragraphs hit the cache.
- Text: sentence splitting around abbreviations; adjusting issues after edits
  shifts later ones and drops touched ones; merging de-duplicates by span and group.
