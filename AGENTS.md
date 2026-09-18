# Repository guidance

Read `docs/intent.md` before changing behavior and `docs/progress.md` when resuming work.
Keep the implementation small and all user-facing text, code, and documentation in English.
Use public yt-dlp APIs and verify upstream options before changing the adapter.
Preserve `/data/data/com.termux/files/usr` in the Termux package and launcher.
Bundle only the application and locked pure-Python UI dependencies; never host-native artifacts.
Use argument arrays for subprocesses, isolate per-job failures, and keep prompts outside workers.
Before handoff run Ruff, offline pytest, Python package builds, and the Debian packaging smoke test.
Record commands, actual results, and remaining device checks in `docs/progress.md`.
Never claim Android runtime validation from Ubuntu tests. Leave release tagging to the maintainer
until device acceptance is recorded. Use a branch and PR for implementation changes.
