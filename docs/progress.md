# v0.1 implementation checkpoint

## Plan

1. Domain, URL validation, formats, paths, and deterministic tests (acceptance 3, 9, 13, 18–19).
2. yt-dlp adapter, conversion, and playlist planning (4, 6–8, 12, 14–17).
3. UI, failure isolation, cancellation, bounded workers (2, 5, 10–11, 20).
4. Termux package, CI, release artifacts, and documentation (1, 21–23).
5. Offline verification, PR review, then real Termux device acceptance.

## Status

Implementation is on `codex/implement-v0.1`; no release is published.
The source intent is committed on main. Implementation commit `c2ef95b` is available in
[PR #1](https://github.com/dimkabuki/y2mp3/pull/1). Automated verification is complete;
the next step is real-device acceptance using `docs/device-test.md`.

## Verification so far

- `ruff check .` and `ruff format --check .` pass.
- `pytest`: **63 passed** locally, including real FFmpeg synthetic media and the real
  yt-dlp processing API. No live YouTube downloads were used for these tests.
- `python -m build`: Python wheel and source distribution build successfully.
- `bash packaging/build_deb.sh --version 0.1.0`: the `.deb` builds and validates successfully
  with hash-locked pure-Python UI dependencies.
- `python packaging/smoke_test.py dist/y2mp3_0.1.0_all.deb 0.1.0`: passes module-origin,
  help, version, and missing-storage checks on Linux.
- [GitHub Actions run 35373913754](https://github.com/dimkabuki/y2mp3/actions/runs/35373913754)
  passed all quality jobs (Python 3.10, 3.12, 3.14) and the package job on 2026-09-18.
  The package job also verified SHA256 checksums and uploaded the `termux-deb` artifact.
- [Download the tested artifact](https://github.com/dimkabuki/y2mp3/actions/runs/35373913754/artifacts/10559292796)
  while signed into GitHub. It contains the versioned `.deb`, `y2mp3.deb`, and `SHA256SUMS`.
  Extract it into Android Downloads and follow the pre-release installation steps in README.
- PR remains unmerged. Android runtime acceptance and stable release remain pending.

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
