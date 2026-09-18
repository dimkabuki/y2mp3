# Codex implementation intent: y2mp3 v0.1

Use this document as the initial implementation prompt for Codex in a new GitHub repository.

---

## Role and goal

Act as the primary implementation agent for a new open-source project named **y2mp3**.

Build a small, maintainable, English-language Python application for Termux on Android. The application must provide an interactive terminal interface for downloading either audio or video from public media URLs, including full playlists. YouTube is the primary and tested target; other sites supported by `yt-dlp` may work on a best-effort basis.

The finished v0.1 repository must include the application, automated tests, documentation, Termux `.deb` packaging, and GitHub Actions workflows that build downloadable release artifacts. Do not create or publish a custom APT repository in v0.1.

Work autonomously from this intent. Inspect the repository before making changes, preserve any relevant existing work, state material assumptions, and ask only when a missing decision would block a safe implementation.

## Product summary

`y2mp3` is an interactive terminal application that wraps the `yt-dlp` Python API and FFmpeg.

The primary user flow is:

1. Run `y2mp3` in Termux.
2. Choose **Audio** or **Video**. Audio is the default.
3. Paste one or more URLs separated by commas, whitespace, or new lines. A blank line finishes multiline input.
4. Expand playlist URLs into individual media jobs.
5. In Video mode, choose a quality separately for every expanded video.
6. Choose sequential or parallel processing. Sequential is the default. In parallel mode, choose a worker count; jobs must be queued, so the number of expanded items does not need to equal the number of workers.
7. Observe interactive per-item progress and a final summary.
8. Find completed files in the Android Downloads directory.

All source code, UI strings, logs, documentation, workflows, and package metadata must be written in English.

## Fixed product decisions

- Project, repository, Debian package, and terminal command name: `y2mp3`.
- Implementation language: Python.
- Download engine: the `yt-dlp` Python API, not stdout parsing of the `yt-dlp` CLI.
- Media post-processing: the Termux FFmpeg package.
- JavaScript challenge runtime: Deno, together with the Termux `yt-dlp-ejs` package.
- Primary supported service: YouTube.
- Other `yt-dlp` sites: accepted on a best-effort basis without service-specific promises.
- Only public URLs are supported in v0.1.
- Cookies, account login, private media, and browser authentication are out of scope.
- Current or scheduled live streams are out of scope for v0.1.
- Full playlist expansion is supported in both Audio and Video modes.
- In Video mode, quality is selected separately for every item in a playlist.
- Audio output is MP3 at 192 kbps.
- Video output is always MP4.
- Video should avoid transcoding when suitable MP4-compatible streams exist. When they do not, transcode as necessary so the final result is a broadly playable MP4, preferably H.264 video and AAC audio.
- Sequential processing is the default.
- Parallel processing is optional and uses a bounded worker queue.
- A failed URL must not stop later queued URLs.
- Distribution is a downloadable `.deb` attached to GitHub Releases.
- A custom Termux APT repository is explicitly out of scope.
- Use an MIT license unless the repository already declares another license. Do not invent author identity in the copyright line.

## Supported runtime

Target current supported Termux installations on Android, installed from an official Termux source rather than the obsolete Google Play build.

Use only Termux-compatible paths. Do not assume standard desktop Linux paths such as `/usr/bin`.

The standard Termux prefix is:

```text
/data/data/com.termux/files/usr
```

The application launcher must use the Python interpreter under that prefix.

Use Python 3.10 or newer and keep the project compatible with the Python version currently provided by Termux.

## Termux runtime dependencies

The `.deb` package should declare Termux packages as dependencies instead of downloading them in `postinst`:

```text
python-yt-dlp
yt-dlp-ejs
deno
ffmpeg
```

Add `python` explicitly only if required by the final package metadata; `python-yt-dlp` already depends on it in current Termux repositories.

Do not run `pip install` during package installation. Installation must be deterministic and owned by the package manager.

Bundle the application and its pure-Python terminal UI dependencies in the `y2mp3` package. Do not bundle FFmpeg, Python, Deno, `yt-dlp`, platform-specific wheels, native `.so` files, or binaries built for desktop Linux.

Pin bundled pure-Python dependencies in a packaging-specific lock or requirements file. Verify during the build that the bundled dependency tree contains no native shared libraries.

## Interactive terminal UX

Use a lightweight terminal UI suitable for a phone-sized Termux session. Prefer `rich` for panels, status lines, tables, colors, and progress bars. Avoid a full-screen TUI framework unless it materially simplifies the implementation.

Use numbered selections with visible defaults so the application remains usable with mobile keyboards and pasted input.

Example opening flow:

```text
╭──────────────────────────────────────╮
│                y2mp3                 │
│       Download audio or video        │
╰──────────────────────────────────────╯

What would you like to download?
  1. Audio (default)
  2. Video
> 

Paste URLs separated by commas or new lines.
Submit an empty line when finished:
> https://example.com/one
> https://example.com/two
>
```

Requirements:

- Pressing Enter at a prompt must accept the displayed default.
- Trim input and ignore empty tokens.
- Accept `http://` and `https://` URLs.
- Preserve input order.
- Do not silently remove duplicate URLs.
- Accept both individual media URLs and playlist URLs.
- Show clear validation errors and allow the user to correct input.
- Do not interpolate URLs into shell command strings.
- Keep interactive prompts separate from live progress rendering.
- Support `Ctrl+C`, return exit code 130, and leave resumable partial downloads intact when practical.

## Processing mode

After URL expansion and any video quality selections, ask for the processing mode:

```text
Processing mode:
  1. Sequential (default)
  2. Parallel
```

For parallel mode:

- Ask for a positive worker count.
- Default to `min(2, number_of_expanded_jobs)`.
- Cap the value at the number of expanded jobs.
- A queue of five URLs with two workers must process all five URLs as workers become available.
- Use a concurrency mechanism appropriate for blocking network downloads and FFmpeg subprocesses, such as a bounded `ThreadPoolExecutor`.
- Use a distinct `yt-dlp.YoutubeDL` instance per job; do not assume instances are thread-safe.
- Keep progress updates thread-safe.

## Audio mode

Expand playlist URLs before downloading. A playlist produces one audio job per available media item, in playlist order. For every expanded item:

1. Retrieve metadata.
2. Show the resolved title when available.
3. Download the best available audio source.
4. Convert it to MP3 at 192 kbps with FFmpeg.
5. Move or write the completed file to the audio output directory.
6. Report the final path.

Use `yt-dlp` progress and postprocessor hooks to distinguish at least:

- inspecting metadata;
- queued;
- downloading;
- converting to MP3;
- completed;
- failed.

Do not label the item completed until post-processing succeeds and the final MP3 exists.

For playlist items, preserve the playlist order in filenames with a zero-padded playlist index and place results in a sanitized playlist-title subdirectory. Individual non-playlist URLs remain directly under the normal audio output directory.

## Video mode and quality selection

Video mode has a planning phase before downloads start. First expand every playlist URL into its individual media entries while preserving the order of both top-level inputs and playlist items.

For every expanded video, sequentially retrieve metadata without downloading and collect the usable video formats. Ask for quality separately for each video, including every item in a playlist. Present one concise selection per distinct vertical resolution, for example:

```text
Video: Example title
  1. 2160p
  2. 1440p
  3. 1080p (default)
  4. 720p
  5. 480p
```

Default selection policy:

1. Select 1080p when it is available.
2. Otherwise select 720p when it is available.
3. Otherwise select the highest available resolution.

Additional requirements:

- Show all meaningful lower and higher available resolutions, deduplicated by height.
- Prefer normal SDR formats for v0.1 when both SDR and HDR exist at the same resolution.
- Within the selected resolution, choose the best practical frame rate and bitrate.
- Prefer an MP4-compatible H.264/AVC video stream and M4A/AAC audio stream when available.
- Correctly handle separate video-only and audio-only streams.
- Merge them with FFmpeg.
- If the best suitable streams cannot be placed in a broadly compatible MP4 without transcoding, transcode to H.264/AAC MP4.
- Never leave the final user-facing video in WebM, MKV, or another container.
- Avoid unnecessary transcoding because it is slow and lossy on a phone.
- Reflect merging and transcoding as separate progress states when possible.
- If no video stream is available, mark only that item as failed and continue.

Quality prompts for all individual and playlist-expanded videos must finish before parallel downloads begin. Worker threads must never compete for interactive input.

For playlist items, preserve playlist order in filenames with a zero-padded playlist index and place results in a sanitized playlist-title subdirectory. Individual non-playlist URLs remain directly under the normal video output directory.

## Playlist expansion

Use `yt-dlp` playlist metadata to expand a playlist URL into individual jobs before download execution.

Requirements:

- Download the full public playlist by default.
- Show the playlist title and number of discovered entries before continuing.
- Preserve the ordering of top-level input URLs and the ordering of entries inside each playlist.
- Support a mixed input list containing individual URLs and playlist URLs.
- Treat every expanded playlist item as an ordinary job for progress, error isolation, summaries, and worker scheduling.
- In Audio mode, apply the fixed 192 kbps MP3 policy to every playlist item without additional quality prompts.
- In Video mode, inspect formats and ask for a quality separately for every playlist item.
- If an entry is private, deleted, unavailable, live, or otherwise unsupported, mark only that entry as skipped or failed and continue the remaining playlist.
- Do not allow `yt-dlp` to hide expanded entries inside one opaque parent operation; the application needs explicit per-item state and progress.
- Avoid loading complete media payloads during expansion. Metadata extraction must not start downloads.
- A playlist that expands to zero usable items is a failure for that top-level input but must not stop other inputs.
- Playlist ranges, item filters, reverse order, and interactive selection of only some entries are not required in v0.1.

## Unsupported media behavior

- Detect current and scheduled live streams before starting a long-running download.
- Report that live streams are not supported in v0.1 and continue with the next URL.
- Completed archived streams may be treated as ordinary videos when `yt-dlp` exposes them as non-live media.
- Do not add cookies or authentication workarounds in v0.1.
- When a site requires login, explain that only public media is supported.
- When an individual media URL also contains a playlist query parameter, respect `yt-dlp`'s resolved media type: download the individual item when the URL clearly addresses one item, and expand when the URL represents the playlist itself.

## Output directories and filenames

Use these defaults:

```text
~/storage/downloads/y2mp3/audio
~/storage/downloads/y2mp3/video
```

On startup, verify that Termux shared-storage access is available. If `~/storage/downloads` is missing, show a concise explanation and the command:

```bash
termux-setup-storage
```

Exit without attempting a download. Never attempt to grant Android storage permission automatically.

Create the `y2mp3/audio` and `y2mp3/video` subdirectories when needed.

For playlists, create a sanitized playlist-title subdirectory below the selected media-type directory and prefix filenames with the zero-padded playlist index. This keeps the downloaded playlist ordered and separate from unrelated downloads.

Preserve readable Unicode titles while sanitizing characters that are unsafe for Android filesystems and shell tooling. Include the media ID in the filename to reduce collisions and limit title length to a safe value. Do not overwrite an unrelated existing completed file silently.

Temporary and partial files should stay in a controlled directory and should be resumable when supported by `yt-dlp`.

## Progress and failures

Show a stable per-job progress view with, when known:

- expanded item index and total expanded job count;
- title or shortened URL;
- current state;
- percentage;
- downloaded and total size;
- current speed;
- ETA.

A representative state sequence is:

```text
[1/3] Inspecting URL
[1/3] Metadata received: Example title
[1/3] Downloading  64%  18.3/28.5 MiB  4.1 MiB/s  00:03
[1/3] Converting to MP3
[1/3] Completed: .../Example title [id].mp3
```

Catch failures at the job boundary. Preserve a concise user-facing message, retain detailed diagnostics behind a verbose/debug mode or log, and continue remaining jobs.

At the end, print a summary with successful, failed, and skipped counts plus completed file paths. Return:

- `0` when every requested item completed successfully;
- `1` when one or more jobs failed or were skipped as unsupported;
- `2` for invalid invocation or unrecoverable startup/configuration errors;
- `130` when interrupted by the user.

Never print secrets, cookies, authorization headers, or full internal stack traces in the normal UI.

## Code architecture

Keep the design small and testable. A suitable starting structure is:

```text
.
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── docs/
│   └── intent.md
├── packaging/
│   ├── build_deb.sh
│   ├── control.in
│   ├── postinst
│   ├── vendor-requirements.txt
│   └── y2mp3-launcher
├── src/
│   └── y2mp3/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── models.py
│       ├── input_parser.py
│       ├── downloader.py
│       ├── formats.py
│       ├── progress.py
│       └── paths.py
├── tests/
├── AGENTS.md
├── LICENSE
├── README.md
└── pyproject.toml
```

Adjust the exact module split if a simpler design is clearer, but keep these boundaries:

- terminal interaction;
- URL parsing and validation;
- domain models and job state;
- format discovery and selection;
- `yt-dlp` integration;
- progress rendering;
- orchestration/concurrency;
- platform paths.

Keep core selection and orchestration logic independent of Rich and `yt-dlp` objects so it can be unit-tested without network access.

Use dataclasses and enums where they make job state explicit. Avoid a framework-heavy architecture, a database, dependency injection containers, or background services.

## Python project requirements

- Use `pyproject.toml` as the source of Python package metadata.
- Expose `python -m y2mp3` for development.
- The installed Termux command must be `y2mp3`.
- Provide `--help` and `--version` without starting the interactive flow.
- Use type hints for public and nontrivial internal interfaces.
- Use `pathlib` for paths.
- Use structured logging internally, with normal output rendered through the UI layer.
- Use `subprocess` only with argument arrays and never `shell=True` for FFmpeg/ffprobe operations.
- Keep dependencies minimal.
- Use `ruff` for linting/format checks and `pytest` for tests.
- Do not call private `yt-dlp` APIs when a supported public option or hook exists.
- Document any unavoidable dependency on current `yt-dlp` behavior.

## Local development

Support development on macOS and ordinary Linux without pretending that locally built binaries are Android-compatible.

Document a local virtual environment setup similar to:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
python -m y2mp3
```

The development dependency group may install `yt-dlp[default]`, Rich, pytest, and Ruff. FFmpeg and a supported JS runtime remain external system tools.

Tests must not require downloading real media by default. Any network integration test must be separately marked and excluded from normal CI.

## Termux `.deb` layout

Build one architecture-independent Debian package named:

```text
y2mp3.deb
```

Its essential installed layout should be equivalent to:

```text
/data/data/com.termux/files/usr/bin/y2mp3
/data/data/com.termux/files/usr/lib/y2mp3/...
/data/data/com.termux/files/usr/share/doc/y2mp3/...
```

The launcher should set only the minimal required `PYTHONPATH` for the bundled application/vendor directory and then execute:

```text
/data/data/com.termux/files/usr/bin/python -m y2mp3
```

Forward all command-line arguments and preserve exit codes and signals.

Package metadata requirements:

- `Package: y2mp3`
- `Architecture: all`
- a version derived from the release tag with the leading `v` removed;
- dependencies listed under the Termux package names described above;
- project homepage derived from the GitHub repository URL;
- a concise English description;
- a valid maintainer value obtained from repository configuration or an explicit build variable, not an invented email address.

The package may be assembled with `dpkg-deb` on an Ubuntu GitHub runner because it contains only architecture-independent Python/text assets. Build both Debian archive members as `control.tar.xz` and `data.tar.xz`, matching official Termux packages; reject gzip members during validation. Do not use PyInstaller or include host-built executables.

The maintainer scripts must be noninteractive. `postinst` may print a reminder to run `termux-setup-storage`, but it must not invoke it or mutate Android permissions.

Validate the package by inspecting its control metadata and file list. Fail the build if:

- the install prefix is wrong;
- a required launcher or module is missing;
- a native `.so` or host executable has been bundled accidentally;
- package metadata does not match the release version.

## GitHub Actions

Create two workflows with least-privilege permissions.

### CI workflow

Run on pull requests and relevant pushes.

It must:

1. Check out the repository.
2. Set up supported Python versions.
3. Install development dependencies.
4. Run Ruff checks.
5. Run pytest.
6. Build the Python wheel or source package as an additional packaging sanity check.

Do not require Android, Termux, media network access, or secrets.

### Release workflow

Run when a tag matching `v*` is pushed. Support `workflow_dispatch` with a browser dropdown: `Build only` (default) or `Publish release`. Manual publishing is allowed from the default branch after device acceptance and requires no local clone or manually pushed tag.

It must:

1. Run or depend on the same quality checks as CI.
2. Use the project version for manual runs; on tag runs, require the tag to match it.
3. Build the architecture-independent `.deb`.
4. Validate it with `dpkg-deb --info` and `dpkg-deb --contents` plus project-specific checks.
5. Generate SHA-256 checksums.
6. Upload `y2mp3.deb` and checksums as workflow artifacts.
7. After checks pass, on a tag build or an explicit manual `Publish release` run, create a GitHub Release and upload:
   - one package asset named `y2mp3.deb`;
   - `SHA256SUMS`.

For manual publishing, create the version tag at the exact tested commit. Never move an existing tag or overwrite an existing release. Serialize release runs to prevent accidental concurrent publication.

Use the current stable major versions of official GitHub Actions. Prefer the preinstalled GitHub CLI with `GITHUB_TOKEN` for release creation over unnecessary third-party release actions. Grant `contents: write` only to the release job that needs it.

The stable asset name is required so the README can provide a latest-release installation command without knowing the version. Per the maintainer decision on 2026-09-18, do not create a duplicate versioned filename. Keep the version in package metadata and the release tag. Users should download the `.deb` directly; CI ZIP archives are developer artifacts.

## Installation documentation

Document this initial installation flow:

```bash
pkg update
curl -fL \
  https://github.com/OWNER/y2mp3/releases/latest/download/y2mp3.deb \
  -o y2mp3.deb
apt install ./y2mp3.deb
termux-setup-storage
y2mp3
```

Replace `OWNER` automatically or manually once the repository remote is known. Do not leave a false URL in a release-ready README.

Explain that `apt install ./y2mp3.deb` is used so dependencies are resolved. Also document:

- upgrading by downloading the latest asset and installing it again;
- uninstalling with `pkg uninstall y2mp3`;
- the output directories;
- the need to approve Android storage access;
- the fact that v0.1 supports only public, non-live individual media and playlist URLs;
- legal and service-terms responsibility: users should download only media they are authorized to save.

## Documentation and repository guidance

Create an English README containing:

- a concise description;
- key features;
- installation from GitHub Releases;
- first-run storage setup;
- an example terminal session;
- output locations;
- local development instructions;
- release instructions;
- limitations and troubleshooting;
- license and responsible-use notice.

Store a cleaned version of this product intent in `docs/intent.md` as the source of truth for v0.1 scope.

Create a concise `AGENTS.md` for future coding agents. It should require reading `docs/intent.md`, preserving the Termux prefix, avoiding host-native artifacts in the `.deb`, running tests before handoff, and keeping user-facing text in English.

## Testing requirements

At minimum, add deterministic unit tests for:

- parsing comma-separated, whitespace-separated, and multiline URLs;
- rejecting unsupported schemes and empty input;
- preserving URL order and duplicates;
- default mode selection;
- video resolution deduplication and sorting;
- default resolution selection: 1080, otherwise 720, otherwise highest;
- MP4-compatible format preference;
- fallback requiring transcoding;
- output path selection for audio and video;
- playlist expansion and ordering;
- mixed individual and playlist input ordering;
- per-item quality selection for video playlists;
- playlist directory and indexed filename generation;
- continuation after an unavailable playlist entry;
- storage-not-configured behavior;
- worker-count defaults and bounds;
- queue behavior with more jobs than workers;
- per-job failure isolation;
- final aggregate exit codes;
- live-stream rejection;
- progress hook state mapping.

Mock `yt-dlp`, filesystem boundaries, and subprocess execution. Do not download real copyrighted media in CI.

Add a packaging smoke test that builds the `.deb` and verifies its metadata and installed paths on Ubuntu without claiming that this is a complete Android runtime test.

## Acceptance criteria

The v0.1 implementation is complete when all of the following are true:

1. On a supported Termux installation, downloading and installing the release `.deb` with `apt install ./y2mp3.deb` resolves the declared dependencies.
2. Running `y2mp3` without storage access gives an actionable `termux-setup-storage` message.
3. Audio is the default startup choice.
4. A public YouTube video can be downloaded as a 192 kbps MP3.
5. Multiple URLs can be processed sequentially.
6. A public playlist URL expands and downloads every available non-live item in playlist order.
7. An audio playlist produces one 192 kbps MP3 per available item.
8. A video playlist asks for a quality separately for every item before downloads begin.
9. A mixed input list of individual URLs and playlists preserves deterministic expanded ordering.
10. Five expanded jobs can be processed by two workers without dropping any jobs.
11. A failure for one URL or playlist entry does not stop later jobs.
12. Video mode inspects every expanded video and asks for a resolution before downloads begin.
13. Video quality defaults to 1080p, then 720p, then the highest available resolution.
14. Every successful video result is an MP4 file.
15. Compatible MP4 streams are merged without needless transcoding.
16. Incompatible streams are transcoded to a broadly playable MP4.
17. Current or scheduled live streams are rejected clearly without hanging the queue.
18. Completed files appear under the documented Android Downloads subdirectories.
19. Playlist results use a playlist-title directory and indexed filenames.
20. The final summary and process exit code accurately represent partial failures.
21. Normal CI passes without network media downloads.
22. A matching version tag or browser-triggered `Publish release` run produces a GitHub Release containing one `y2mp3.deb` and checksums; the manual path creates the tag automatically after verification.
23. No custom APT repository is created or required.

## Explicit non-goals for v0.1

Do not implement these unless required to make an accepted requirement work:

- live stream recording;
- scheduled stream waiting;
- cookies or authenticated downloads;
- private, paid, or DRM-protected media;
- selecting only part of a playlist, playlist ranges, reverse ordering, or playlist filtering;
- a native Android APK or graphical UI;
- a custom APT repository;
- automatic self-update logic;
- browser integration or Android share intents;
- download history or a database;
- subtitles, SponsorBlock, thumbnails, or metadata artwork embedding;
- audio formats other than MP3;
- output video containers other than MP4;
- a server or background daemon.

## Implementation approach

Before coding:

1. Inspect the repository and existing instructions.
2. Write a short implementation plan mapped to the acceptance criteria.
3. Verify current public `yt-dlp` option and hook names rather than guessing them.
4. Keep the first implementation minimal and separable.

During implementation:

1. Build the domain and parsing logic with tests first.
2. Add the `yt-dlp` adapter and progress state mapping.
3. Add sequential orchestration, then bounded parallel orchestration.
4. Add the interactive Rich UI.
5. Add Termux paths and storage checks.
6. Add `.deb` packaging and validate its contents.
7. Add CI and release workflows.
8. Complete README, `docs/intent.md`, and `AGENTS.md`.

Before handoff:

1. Run formatting/lint checks and all offline tests.
2. Build and inspect the `.deb` locally in the available environment.
3. Review the repository against every acceptance criterion.
4. Report what was verified directly and what still requires a real Termux device.
5. Do not claim Android runtime verification unless it was actually performed.
