# v0.1 implementation checkpoint

## Plan

1. Domain, URL validation, formats, paths, and deterministic tests (acceptance 3, 9, 13, 18–19).
2. yt-dlp adapter, conversion, and playlist planning (4, 6–8, 12, 14–17).
3. UI, failure isolation, cancellation, bounded workers (2, 5, 10–11, 20).
4. Termux package, CI, release artifacts, and documentation (1, 21–23).
5. Offline verification, PR review, then real Termux device acceptance.

## Status

Implementation in progress on `codex/implement-v0.1`. No release is published.
The source intent is committed on main. Resume by inspecting this branch and test results.

## Decisions and upstream checks

- Verified yt-dlp 2026.08.19 public YoutubeDL options and progress/postprocessor hook contracts.
- Explicit FFmpeg processing enforces MP3 bitrate even for source MP3 files, which upstream's
  extract-audio processor can otherwise leave untouched. Video output is inspected with ffprobe.
- Deno constrains supported devices to Termux architectures providing Deno (64-bit Android).
  The `.deb` remains architecture-independent; its runtime dependencies determine availability.
- GitHub official action majors checked on 2026-09-18: checkout 7, setup-python 7, upload-artifact 7.
- No release tag until real-device acceptance. CI packages provide the first phone test artifact.

## Remaining real-device checks

Dependency resolution, launcher, storage permissions, actual YouTube downloads, playback,
phone-width UI, playlists, parallel queue, and interruption. None has been verified on Android.
