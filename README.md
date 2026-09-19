# y2mp3

Interactive audio and video downloads for **Termux on Android**. Powered by the
public yt-dlp Python API and FFmpeg. YouTube is the primary target; other public
sites supported by yt-dlp work on a best-effort basis.

**Status:** v0.1.1 compatibility fix, pending real-device acceptance. Do not install
the v0.1.0 package: its Debian archive compression is incompatible with Termux APT.
Use a v0.1.1 CI package for testing until the corrected release is published.

- MP3 audio at 192 kbps (default mode).
- H.264/AAC MP4 video; choose a resolution separately for each video.
- Full public playlists, indexed filenames, and playlist subdirectories.
- Sequential downloads by default, optional bounded parallel workers.
- Per-item progress, failure isolation, and resumable partial downloads.

## Quick start in Termux

Use a current official Termux installation with the standard
`/data/data/com.termux/files/usr` prefix. F-Droid or the official GitHub release is
recommended. The current Google Play build is also supported on a best-effort basis;
it uses a separate package repository whose versions can lag behind the other sources.
A **64-bit device with the Termux Deno package available** is required by v0.1. Do not
use the obsolete legacy Play Store build. See the [Termux installation
instructions](https://github.com/termux/termux-app#installation).

Each block below contains one command. Copy it, paste it into Termux, press Enter,
and wait for it to finish before continuing with the next block.

### Install the test package before the first release

First download `y2mp3.deb` in the Android browser and save it in **Downloads**.
Then open Termux and update its package lists:

```sh
pkg update
```

Create the Termux link to Android shared storage:

```sh
termux-setup-storage
```

Approve the Android storage permission when prompted. Then open Downloads:

```sh
cd ~/storage/downloads
```

Confirm that the downloaded package is present:

```sh
ls -lh y2mp3.deb
```

Install it together with its Termux dependencies:

```sh
apt install ./y2mp3.deb
```

Check the installed version:

```sh
y2mp3 --version
```

Start the application:

```sh
y2mp3
```

If `ls` cannot find the package, check the browser's download location. On some
Android versions it may have been renamed, for example to `y2mp3 (1).deb`.

### Install after the first GitHub Release

Once a release exists, the package can be downloaded directly from GitHub. Run
these commands one at a time:

```sh
pkg update
```

```sh
pkg install curl
```

```sh
termux-setup-storage
```

Approve storage access if Android asks, then download the current release:

```sh
curl -fL https://github.com/dimkabuki/y2mp3/releases/latest/download/y2mp3.deb -o "$HOME/storage/downloads/y2mp3.deb"
```

```sh
apt install "$HOME/storage/downloads/y2mp3.deb"
```

```sh
y2mp3 --version
```

```sh
y2mp3
```

Use `apt install`, rather than `dpkg -i`, so dependencies are resolved. The package
requires `python-yt-dlp`, `yt-dlp-ejs`, Deno, and FFmpeg. Installation never runs pip.
The `.deb` deliberately does not pin these dependencies to a particular Termux release;
your configured Termux repository selects compatible versions and `pkg upgrade` keeps
them current.
GitHub Releases serve the `.deb` directly, without an archive. Before a release exists,
a maintainer can supply the validated `.deb` directly. Developer CI artifacts remain
ZIP archives on GitHub and require a signed-in account to download. Each new build
contains only one package, `y2mp3.deb`; its version is stored in the package metadata.

## Step-by-step usage

### Download one video as MP3 audio

Start the application:

```sh
y2mp3
```

Then answer the prompts:

1. At **What would you like to download?**, press Enter. Audio is the default.
2. At the URL prompt, paste the public video URL and press Enter.
3. Press Enter again on the empty URL line to finish entering URLs.
4. At **Processing mode**, press Enter. Sequential processing is the default.
5. Wait for the completed path and final summary.

The MP3 appears in:

```text
~/storage/downloads/y2mp3/audio
```

### Download one video as MP4

Start `y2mp3` again:

```sh
y2mp3
```

Then:

1. Enter `2` to select Video.
2. Paste the public video URL, press Enter, then press Enter on the empty URL line.
3. Choose a displayed resolution, or press Enter for the suggested default.
4. Press Enter at **Processing mode** for sequential processing.
5. Wait for the completed path and summary.

The MP4 appears in:

```text
~/storage/downloads/y2mp3/video
```

### Download several URLs

At the URL prompt, either paste several URLs separated by spaces or commas, or paste
one URL per line. After the last URL, submit an empty line. Input order and duplicate
URLs are preserved.

To use parallel downloads, enter `2` at **Processing mode**, then enter the number
of workers. Pressing Enter accepts the suggested value, normally two workers.

### Download a playlist

Paste the public playlist URL exactly like an individual URL. The application expands
the full playlist. Audio mode uses 192 kbps MP3 for every available item. Video mode
asks for a resolution separately for every item before downloading begins.

Every playlist gets its own folder, for example:

```text
~/storage/downloads/y2mp3/audio/My playlist [playlist ID]/
```

Items keep their playlist order:

```text
001 - First item [video ID].mp3
002 - Second item [video ID].mp3
```

### Prompt reference

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

To upgrade after releases are available, update Termux first:

```sh
pkg update
```

```sh
pkg upgrade
```

Download the latest y2mp3 package again:

```sh
curl -fL https://github.com/dimkabuki/y2mp3/releases/latest/download/y2mp3.deb -o "$HOME/storage/downloads/y2mp3.deb"
```

Install the downloaded update:

```sh
apt install "$HOME/storage/downloads/y2mp3.deb"
```

Confirm the installed version:

```sh
y2mp3 --version
```

Updating Termux also updates yt-dlp, which often fixes changes made by supported sites.

To uninstall the application:

```sh
pkg uninstall y2mp3
```

Uninstalling does not remove downloaded media or retained partial files.

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
python packaging/validate_deb.py dist/y2mp3.deb 0.1.1
```

The build bundles only this app and locked, pure-Python UI wheels. Runtime tools
come from Termux's package manager. Maintainer metadata is in
`packaging/maintainer.txt` (GitHub noreply address) and may be overridden with
`Y2MP3_MAINTAINER`. Use GitHub issues for contact.
No host binaries or host Python interpreter are included. An Ubuntu packaging
smoke test is **not** Android runtime verification.

## Releases

CI runs lint, offline tests, Python package builds, and a `.deb` smoke test. Every
successful CI run includes a `termux-deb` artifact for testing before a release.
After the workflow is merged into `main`, releases can be published entirely in a
browser, including on a phone. No local clone, token setup, or terminal is needed.

1. Finish the checks in `docs/device-test.md` and record the results.
2. Merge the reviewed PR and wait for CI on `main` to pass.
3. Open [Actions → Release](https://github.com/dimkabuki/y2mp3/actions/workflows/release.yml).
4. Tap **Run workflow** and select branch **main**.
5. Choose **Publish release** under the action dropdown, then tap **Run workflow**.
6. Wait for the run to finish, then open [Releases](https://github.com/dimkabuki/y2mp3/releases)
   and download **y2mp3.deb** directly. The run summary also links to the package.

If the mobile layout hides the controls, enable **Desktop site** in your browser menu.
The default **Build only** choice runs the checks and makes a CI artifact without
creating a tag or release. The button appears only after the workflow is on `main`.

Publishing reruns all quality and package checks. The workflow reads the package
version (currently `0.1.1`), creates its tag (`v0.1.1`) at the exact tested commit,
and publishes one `y2mp3.deb` plus `SHA256SUMS`. Manual publishing requires the default
branch. Existing tags must point to the tested commit; existing releases are never
replaced. If a run fails after creating its tag but before creating a release, rerun
that same workflow run. If a draft release already exists after an interrupted upload,
inspect it before deciding how to recover; the workflow will not overwrite it.

For later releases, update the version in both `pyproject.toml` and
`src/y2mp3/__init__.py` through a PR first. The corrected package uses `0.1.1`.
Pushing a matching `v*` tag remains supported for contributors who use Git.
Only the publishing job receives `contents: write`; it uses GitHub's built-in token.
No custom APT repository or self-update service is created.

## Limitations and troubleshooting

- Public, non-live media only. No cookies, login, private/paid/DRM media, or stream recording.
  Archived streams work once exposed as ordinary completed media.
- Availability depends on yt-dlp, YouTube policies, regional restrictions, and your network.
  No guarantee is made for every public URL or supported third-party site.
- Missing storage: run `termux-setup-storage` and approve permission. Check Android
  app permissions if the Downloads directory remains inaccessible.
- Missing dependencies: `pkg update && pkg install python-yt-dlp yt-dlp-ejs deno ffmpeg`.
- `could not locate member control.tar...`: the obsolete v0.1.0 package used an
  incompatible archive compression. Install v0.1.1 or newer.
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
