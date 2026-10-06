# Immersive Message Maker v0.5-assets

A standalone mobile-friendly utility for composing in-universe UI and copying deterministic self-contained HTML into TauriTavern / SillyTavern user messages.

## Presets

- WeChat: text messages, timestamps, voice messages, and stickers.
- iMessage: text messages with optional Delivered / Read receipts.
- Stream Chat: normal chat, optional avatars, MOD/SUB/VIP badges, notices, viewer count, and highlighted donations.
- X Thread: multiple posts/replies with per-post author, optional avatar, timestamp, verification, and engagement counts.

## Images

Paste a direct HTTP(S) image URL into an **Avatar image URL** field on an X post, Stream message, or highlighted donation. The editor shows a thumbnail and load feedback; **Remove** restores the default appearance. WeChat's **Sticker** field accepts either an image URL or its existing emoji/text value. Image stickers fit inside a 128px square without cropping; their alt/meaning remains in the generated HTML.

Prefer HTTPS URLs that remain publicly accessible. Images stay linked, so the destination chat must be able to load them. This first foundation uses URLs only; local uploads and embedded image data are deferred to keep drafts small and persistence simple.

Existing v0.4.2 drafts continue to load under the same autosave key. Avatars add an optional `avatarUrl` string to X and Stream items; stickers keep the existing `sticker` string. Copy JSON retains schema version 4 with these additive fields. The reusable `createImageInput({value, label, allowText, onChange})` control and shared `imageUrl()` validator are available for future presets.

## Model readability

WeChat voice messages and stickers can include an optional transcript / alt meaning. The generated HTML keeps that semantic description hidden visually so the RP model can still receive meaningful text while the user sees the immersive UI.

## Running

Open `immersive-message-maker-standalone.html` directly, or host `index.html` on GitHub Pages. Everything is self-contained; no API or build step is required.

## Optional regression checks

The app itself has no dependencies. To run the browser checks, install Python's `playwright` package and its Chromium browser, then run `python tests/browser_regression.py`. Set `CHROMIUM_PATH` to an installed Chromium executable if preferred.

The suite covers preset switching, Copy HTML/JSON, old drafts and autosave, X thread edits/reordering, Stream donations, stickers, voice transcript disclosure without JavaScript, invalid/broken URLs, and layouts from 320px to desktop. Both HTML entry points must remain identical. Manually check a pasted image thread, donation, and voice/sticker conversation in your TauriTavern/SillyTavern theme, plus touch interactions in mobile Safari.

## v0.5 assets foundation

- Shared image URL control with thumbnail, loading/error feedback, and removal.
- Optional avatars for X posts/replies and Stream messages/donations.
- Bounded WeChat image stickers with preserved emoji/text and semantic meaning.
- Inline-styled, script-free exported images; narrow-screen wrapping for controls and long social/donation text.


## v0.4.1

- WeChat voice notes are now tappable. When a transcript/meaning is provided, tapping the voice bubble expands a visible WeChat-style transcript while preserving hidden semantic text for model readability.


## v0.4.2

- Hardened the tappable WeChat voice-note control against host/theme CSS. The native disclosure element is now visually reset, while the actual voice bubble lives inside a fully inline-styled child element. This keeps the no-JavaScript tap-to-transcript behavior without inheriting TauriTavern button styling.
