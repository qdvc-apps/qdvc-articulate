# Privacy model (GNOME edition)

**Requirement:** no data ever leaves the device. The app must be completely cut off from the network.
(The macOS edition's model is in [../../macos/docs/PRIVACY.md](../../macos/docs/PRIVACY.md).)

## How this is enforced

| Layer | Measure |
|---|---|
| Operating system | The **Flatpak has no network permission** (no `--share=network`). Flatpak then runs the app in a network namespace of its own with only the loopback interface: no route leads off the computer, for the app or for any library inside it, llama.cpp included. |
| Files | The Flatpak has **no filesystem permission**. Documents and the GGUF model are opened through the file chooser portal, which grants access to each file chosen (and keeps it across launches). Drafts and preferences stay in the app's own folder under `~/.var/app/qdvc.articulate.gtk4app/`. |
| Build | `scripts/build-app.sh` and the tests refuse a manifest that grants network or filesystem access. llama.cpp is built without its tools, server and download code; nothing is downloaded during the build. |
| Runtime | The app reads its own sandbox description (`/.flatpak-info`) and the network interfaces it can see. If it is not sandboxed (run from a checkout) or could reach a network, a banner says so and the status bar shield turns orange. Preferences › Privacy shows the details and can check again. The check opens no socket. |
| Code | No analytics, telemetry, crash reporting, update checks, cloud sync or downloads. No networking modules in the sources (tested). The model is a file the user picks. |
| Spelling | Enchant and its Hunspell dictionaries run **inside the app's process**: unlike AppleSpell on macOS, no other process sees the text. |
| Import | `.docx`, `.doc`, `.odt` and `.rtf` are read by the app's own code (zipped XML, the RTF text, the Word 97 piece table). Nothing in them is fetched; HTML is not imported. |
| Storage | AI results are cached in memory only. Drafts of unsaved documents are kept until saved or discarded. |

## Verifying it yourself

- Flatseal: QDVC Articulate › Network is off, and no filesystem access is listed.
- `flatpak info --show-permissions qdvc.articulate.gtk4app`
- `flatpak run --command=sh qdvc.articulate.gtk4app -c 'ls /sys/class/net'` prints only `lo`.
