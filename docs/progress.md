# v0.1 implementation checkpoint

## Plan

1. Domain, URL validation, formats, paths, and deterministic tests (acceptance 3, 9, 13, 18–19).
2. yt-dlp adapter, conversion, and playlist planning (4, 6–8, 12, 14–17).
3. UI, failure isolation, cancellation, bounded workers (2, 5, 10–11, 20).
4. Termux package, CI, release artifacts, and documentation (1, 21–23).
5. Offline verification, PR review, then real Termux device acceptance.

## Status

Implementation is on `codex/implement-v0.1`; no release is published.
The source intent is committed on main. GitHub checkpoint e644307 contains the initial
implementation and offline unit tests. Media tests and CI/package gates are now implemented.
Resume by inspecting this branch, this checkpoint, and the latest GitHub Actions results.

## Verification so far

- Ruff lint and format checks pass.
- Offline tests pass, including real FFmpeg synthetic media and the real yt-dlp processing API.
- Python wheel and source distribution build successfully.
- The `.deb` builds successfully with hash-locked pure-Python UI dependencies.
- Extracted-package smoke test passes: module origins, help, version, and missing-storage guard.
- GitHub Actions and real-device acceptance still need to be checked after publishing the PR.

## Decisions and upstream checks

- Verified yt-dlp 2026.08.19 public YoutubeDL options and progress/postprocessor hook contracts.
- Explicit FFmpeg processing enforces MP3 bitrate even for source MP3 files, which upstream's
  extract-audio processor can otherwise leave untouched. Video output is inspected with ffprobe.
- Deno constrains supported devices to Termux architectures providing Deno (64-bit Android).
  The `.deb` remains architecture-independent; its runtime dependencies determine availability.
- GitHub official action majors checked on 2026-09-18: checkout 7, setup-python 7,
  upload-artifact 7, download-artifact 8.
- Public package metadata uses the account-derived GitHub noreply address, never personal email.
  Contact the maintainer through GitHub issues.
- Preliminary yt-dlp playlist filtering does not reject live entries; the per-item planning
  boundary marks them skipped so later playlist entries survive.
- No release tag until real-device acceptance. CI packages provide the first phone test artifact.

## Remaining real-device checks

Dependency resolution, launcher, storage permissions, actual YouTube downloads, playback,
phone-width UI, playlists, parallel queue, and interruption. None has been verified on Android.
