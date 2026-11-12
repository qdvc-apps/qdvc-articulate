# Privacy model

**Requirement:** no data ever leaves the device. The app must be completely cut off from the network.

## How this is enforced

| Layer | Measure |
|---|---|
| Operating system | **App Sandbox ON** with **no** `com.apple.security.network.client` / `network.server` entitlement. macOS denies every socket the process opens, including any opened by bundled libraries such as llama.cpp. |
| Build | `scripts/verify-isolation.sh` runs on every build. It fails if a network entitlement, a sandbox temporary exception, or `disable-library-validation` appears, or if `Info.plist` has App Transport Security exceptions. |
| Runtime | On launch, the app reads its own entitlements. If it isn't sandboxed (for example when started with `swift run`), every window shows an orange warning banner. Settings → Privacy can run a live probe: it tries to connect to `127.0.0.1` and expects macOS to refuse (`EPERM`). Even if the probe were allowed, loopback traffic stays on the Mac. |
| Code | No analytics, telemetry, crash reporting, update checks, cloud sync or downloads. The model is a file the user picks with the standard Open dialog. |
| Editor | Writing Tools are disabled (macOS 15+). The view's text is never offered to the Services menu. The context menu is replaced, so there's no Share, "Search With…" or Look Up. Inline predictions, auto-correction and data detectors are off. |
| Import | `.docx`, `.doc`, `.odt` and `.rtf` go through AppKit's local text importers. HTML and web archives are **not** supported: AppKit imports them through WebKit, which may try to fetch remote resources. |
| Storage | Preferences live in the sandbox container's `UserDefaults`. AI results are cached **in memory only**. Documents are saved where the user chooses. |

## What still runs outside the app's own process

The **macOS spelling and grammar checker** (AppleSpell) is a local system service. The app sends it
text over XPC, on the same Mac. It doesn't use the network for checking, but it is outside the app's
sandbox. You can switch it off in Settings → General → Checking. The rule engine and the AI model
then do all the checking inside the app's own process.

## Verifying it yourself

```sh
scripts/verify-isolation.sh "build/QDVC Articulate.app"
codesign -d --entitlements - "build/QDVC Articulate.app"
```

For independent confirmation, run a network monitor (Little Snitch, LuLu) or
`sudo nettop -p QDVCArticulate` while you use the app. You should see no connections.
