# Real Termux acceptance (before v0.1.0)

Record device model, Android version, Termux source/version, package commit SHA,
and `python --version`, `ffmpeg -version`, `deno --version`, `yt-dlp --version`.
Use short media you own or are authorized to download.

1. On a current 64-bit Termux, run `pkg update`, then `apt install ./y2mp3_0.1.0_all.deb`.
   All declared dependencies must install without pip or manual downloads.
2. `y2mp3 --help` and `y2mp3 --version` work without starting prompts.
3. Before storage setup, `y2mp3` should explain `termux-setup-storage` and exit 2.
   If storage is already configured, skip this check; do not revoke existing access just to test it.
4. Run `termux-setup-storage` and approve Android permissions.
5. Download one short video as default audio. Check 192 kbps MP3 in Android Downloads.
6. Download one video as 720p/1080p MP4. Check both picture and audio in your player.
7. Use an authorized source with incompatible codecs to exercise transcoding if available.
8. Download a small playlist as audio, then video. Video must prompt separately for each item.
   Verify playlist subdirectory and numbered filenames.
9. Mix individual URLs and playlists; include a duplicate and an unavailable URL. Verify order,
   preserved existing files, continuation, summary counts, and exit status (`echo $?`).
10. Process five items with two workers. Verify all five finish and at most two run at once.
11. Interrupt a download with Ctrl+C; check exit 130. Repeat identical inputs/quality to resume.
12. Verify narrow-screen progress and the final paths are readable. Report text errors; a screenshot
    is useful only for layout problems that cannot be described.

Record results in `docs/progress.md`. Linux tests and successful packaging do not satisfy these
Android checks. Fix and repeat only failing cases. Tag the stable release after acceptance.
