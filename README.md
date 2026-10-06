# Immersive Message Maker v0.4.2

A standalone mobile-friendly utility for composing in-universe UI and copying deterministic self-contained HTML into TauriTavern / SillyTavern user messages.

## Presets

- WeChat: text messages, timestamps, voice messages, and stickers.
- iMessage: text messages with optional Delivered / Read receipts.
- Stream Chat: normal chat, MOD/SUB/VIP badges, notices, viewer count, and highlighted donations.
- X Thread: multiple posts/replies with per-post author, timestamp, verification, and engagement counts.

## Model readability

WeChat voice messages and stickers can include an optional transcript / alt meaning. The generated HTML keeps that semantic description hidden visually so the RP model can still receive meaningful text while the user sees the immersive UI.

## Running

Open `immersive-message-maker-standalone.html` directly, or host `index.html` on GitHub Pages. Everything is self-contained; no API or build step is required.


## v0.4.1

- WeChat voice notes are now tappable. When a transcript/meaning is provided, tapping the voice bubble expands a visible WeChat-style transcript while preserving hidden semantic text for model readability.


## v0.4.2

- Hardened the tappable WeChat voice-note control against host/theme CSS. The native disclosure element is now visually reset, while the actual voice bubble lives inside a fully inline-styled child element. This keeps the no-JavaScript tap-to-transcript behavior without inheriting TauriTavern button styling.

## PR previews

Open same-repository PRs targeting `main` have public previews at
`https://chikausa14.github.io/immersive-message-maker/previews/pr-N/`.
Production continues to use `main`. See [preview deployment setup and safety notes](docs/preview-deployments.md)
for updates, cleanup, browser-origin sharing, and rollback.
