# y2mp3

Interactive audio and video downloads for **Termux on Android**. Powered by the
public yt-dlp Python API and FFmpeg. YouTube is the primary target; other public
sites supported by yt-dlp work on a best-effort basis.

**Status:** v0.1 implementation, pending real-device acceptance. No stable release yet.
Use the Debian package artifact from CI for device testing. The latest-release
installation URL below becomes available after the first stable release.

- MP3 audio at 192 kbps (default mode).
- H.264/AAC MP4 video; choose a resolution separately for each video.
- Full public playlists, indexed filenames, and playlist subdirectories.
- Sequential downloads by default, optional bounded parallel workers.
- Per-item progress, failure isolation, and resumable partial downloads.

## Install in Termux

Use a current official Termux installation (F-Droid or the official GitHub release
is recommended), with the standard `/data/data/com.termux/files/usr` prefix.
A **64-bit device with the Termux Deno package available** is required by v0.1.
Do not use the obsolete legacy Play Store build. See the [Termux installation
instructions](https://github.com/termux/termux-app#installation).

After the first stable release:

```sh
pkg update
pkg install curl
curl -fL https://github.com/dimkabuki/y2mp3/releases/latest/download/y2mp3.deb -o y2mp3.deb
apt install ./y2mp3.deb
termux-setup-storage
y2mp3
```

Approve Android storage access when prompted. Use `apt install ./y2mp3.deb`, which
resolves dependencies, rather than installing with `dpkg -i` alone. The package
requires `python-yt-dlp`, `yt-dlp-ejs`, Deno, and FFmpeg. Installation never runs pip.

For the pre-release device test, download the `termux-deb` artifact from a successful
[CI run](https://github.com/dimkabuki/y2mp3/actions), unzip it into Downloads, then:

```sh
termux-setup-storage
cd ~/storage/downloads
apt install ./y2mp3_0.1.0_all.deb
y2mp3 --version
y2mp3
```

GitHub artifact downloads require a signed-in GitHub account. Extract the ZIP using
Android's file manager, or `pkg install unzip` followed by `unzip termux-deb.zip`.

## Use

```text
y2mp3 — Download audio or video
What would you like to download?
  1. Audio (default)
  2. Video
>
Paste URLs separated by commas, spaces, or new lines.
Submit an empty line when finished.
> https://www.youtube.com/watch?v=YOUR_VIDEO_ID
>
Processing mode:
  1. Sequential (default)
  2. Parallel
>
```

Enter accepts the displayed default. URLs keep their input order and duplicates
are separate jobs. A watch URL with a playlist parameter downloads that video;
an explicit playlist URL expands the playlist. For video, all quality prompts
finish before downloads start. The default is 1080p, then 720p, then the highest
available resolution. Parallel mode defaults to two workers (or one for one job).

Output:

- `~/storage/downloads/y2mp3/audio/*.mp3`
- `~/storage/downloads/y2mp3/video/*.mp4`
- Playlists: `<audio|video>/<playlist title> [playlist ID]/001 - <title> [media ID].<ext>`

Existing files are preserved; duplicates receive numbered suffixes. Temporary
files live under `y2mp3/.partial/`. Successful jobs remove their own workspace.
Repeat the same input ordering, mode, and video quality to reuse partial downloads.
Deleting `.partial/` while the app is stopped discards resume data and frees space.
Allow space for source, converted output, and final copy during processing.

Ctrl+C stops scheduling, cancels downloads at the next hook, and stops explicit
FFmpeg conversion. A running yt-dlp metadata request or built-in merge can take time
to return before shutdown finishes. Partial files are retained when practical.

Exit status: 0 = all succeeded; 1 = failed/skipped item; 2 = startup/input error;
130 = interrupted. Use `--verbose` for redacted diagnostics on stderr.

## Upgrade and uninstall

Repeat the download and `apt install ./y2mp3.deb` commands to upgrade. Update upstream
extractors with `pkg upgrade`; yt-dlp updates often fix site changes. Uninstall with
`pkg uninstall y2mp3`. Downloaded media and partial files are not removed.

## Develop on macOS or Linux

Install Python 3.10+, FFmpeg (including ffprobe), and Deno using your system package
manager. Then:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
python -m y2mp3 --output-dir ./downloads
ruff check .
ruff format --check .
pytest
python -m build
```

`--output-dir` bypasses the Android shared-storage check for desktop development.
Normal tests use fake metadata and local synthetic media; they never download real
media. Network tests, if added, must use `@pytest.mark.network` and run explicitly.

## Build a Termux package

On Linux with `dpkg-deb` and Python development dependencies installed:

```sh
bash packaging/build_deb.sh
python packaging/validate_deb.py dist/y2mp3_0.1.0_all.deb 0.1.0
```

The build bundles only this app and locked, pure-Python UI wheels. Runtime tools
come from Termux's package manager. Maintainer metadata is in
`packaging/maintainer.txt` and may be overridden with `Y2MP3_MAINTAINER`.
No host binaries or host Python interpreter are included. An Ubuntu packaging
smoke test is **not** Android runtime verification.

## Releases

CI runs lint, offline tests, Python package builds, and a `.deb` smoke test. Every
successful CI run includes a `termux-deb` artifact for testing before a release.
The release workflow also supports a non-publishing manual build after it is on main.

1. Record successful checks from `docs/device-test.md` in `docs/progress.md`.
2. Merge the reviewed implementation PR.
3. Update the version in `pyproject.toml` and `src/y2mp3/__init__.py` together.
4. Push a matching tag, e.g. `v0.1.0`, after device acceptance.
5. The release workflow reruns quality checks and publishes the versioned `.deb`,
   byte-identical `y2mp3.deb`, and `SHA256SUMS`.

Only the publishing job receives `contents: write`. Version/tag mismatches fail.
No custom APT repository or self-update service is created.

## Limitations and troubleshooting

- Public, non-live media only. No cookies, login, private/paid/DRM media, or stream recording.
  Archived streams work once exposed as ordinary completed media.
- Availability depends on yt-dlp, YouTube policies, regional restrictions, and your network.
  No guarantee is made for every public URL or supported third-party site.
- Missing storage: run `termux-setup-storage` and approve permission. Check Android
  app permissions if the Downloads directory remains inaccessible.
- Missing dependencies: `pkg update && pkg install python-yt-dlp yt-dlp-ejs deno ffmpeg`.
- A Deno dependency unavailable on your device means that architecture is outside v0.1.
- Video conversion on phones can be slow, use substantial storage, and drain battery.
  Compatible H.264/AAC streams are preferred and copied without re-encoding. Other
  codecs are transcoded. SDR is preferred; HDR-specific tone mapping is not implemented.
- A failed/private/deleted playlist entry is reported and does not stop the remainder.
- Shell/control characters are removed from filenames; Unicode titles are retained.
- See `docs/intent.md` for the complete scope and `AGENTS.md` for contributor guidance.

## License and responsible use

MIT, see `LICENSE`. Third-party dependencies retain their own licenses (included
with bundled UI wheels). Download only media you are authorized to save and follow
applicable service terms.
