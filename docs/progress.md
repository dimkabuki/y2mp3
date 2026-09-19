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
  This is a historical artifact; new builds use one filename as described below.
- PR remains unmerged. Android runtime acceptance and stable release remain pending.

## Packaging simplification (2026-09-18)

- At the maintainer's request, build and publish only `y2mp3.deb`, with `SHA256SUMS`
  as a separate integrity file. The version remains in Debian metadata and release tags.
- Updated the builder, CI, release workflow, intent, and device instructions together.
- Direct `.deb` delivery is the user-facing path. GitHub Actions ZIPs remain developer
  artifacts; no release is published before device acceptance.
- Rechecked Ruff (lint and formatting), all 63 offline tests, and Python distributions.
- `PYTHON=.venv/bin/python bash packaging/build_deb.sh` and
  `.venv/bin/python packaging/smoke_test.py dist/y2mp3.deb 0.1.0` pass.
  The new single-file package is validated on Linux; Android remains untested.

## Browser release workflow (2026-09-18)

- Added a mobile-browser-compatible **Run workflow** choice: `Build only` (default) or
  `Publish release`. The control becomes available after this workflow is merged to `main`.
- Manual publishing is accepted only from the default branch and only after the reusable CI
  workflow succeeds. It creates `v<package version>` at the exact tested commit and publishes
  `y2mp3.deb` plus `SHA256SUMS` without requiring a local clone.
- Release runs are serialized. Existing tags are never moved, existing releases are never
  replaced, and tag/package version mismatches stop publication.
- Added 12 release-safeguard tests covering manual and tag paths, wrong branches/commits,
  corrupt checksums, existing tags/releases, and failed tag creation.
- `ruff check .`, `ruff format --check .`, `bash -n packaging/publish_release.sh`, and
  `pytest` pass; the full suite is now **75 passed**. Both workflow YAML files parse locally.

## Phone-friendly README (2026-09-18)

- Reworked installation, first audio/video download, multiple-URL, playlist, upgrade, and
  uninstall instructions into numbered steps suitable for a mobile browser and Termux.
- Shell instructions use one copyable command per code block. Interactive application choices
  remain explicit steps because the URL and available video resolutions vary per download.
- Documented both the current pre-release file flow and the direct GitHub Release flow, including
  storage permission, package-presence verification, output locations, and playlist folders.
- Rechecked Ruff, all **75 tests**, Python distributions, the Debian package validator, and the
  extracted-package smoke test. Android device acceptance remains pending.

## Termux package compression fix (2026-09-18)

- First real-device installation exposed an APT error: `could not locate member
  control.tar{.xz,.lzma,}`. The published v0.1.0 package must not be installed.
- Root cause: the project builder forced gzip, while official Termux Debian packages use
  `control.tar.xz` and `data.tar.xz`.
- Changed the builder to uniform xz compression and made validation require the exact Debian
  members `debian-binary`, `control.tar.xz`, and `data.tar.xz`.
- Added a regression test proving that a gzip-member package is rejected before publication.
- Bumped the corrected package version to 0.1.1. After CI and real-device installation, publish
  v0.1.1 so it replaces v0.1.0 as the latest release.
- Automated verification passes with 77 tests, and the rebuilt package contains exactly
  `debian-binary`, `control.tar.xz`, and `data.tar.xz` before passing the install smoke test.
- A current Google Play Termux build (`googleplay.2026.02.11`, aarch64, Android 16) exposed
  an unnecessary `python-yt-dlp (>= 2026.08.19)` constraint: its current repository provides
  `python-yt-dlp` 2026.06.09 while all four required packages are available.
- Removed the calendar-version constraint so the configured Termux repository owns dependency
  selection. Package validation and a regression test now reject version-pinned dependencies.
- Real-device launcher checks exposed `usage: __main__.py` in help output. Set argparse's public
  program name explicitly to `y2mp3` and added a regression assertion.

## Decisions and upstream checks

- Verified the public YoutubeDL options and progress/postprocessor hook contracts against both
  yt-dlp 2026.06.09 (Google Play repository level) and 2026.08.19 (build environment level).
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
