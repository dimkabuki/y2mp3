from io import StringIO

import pytest
from rich.console import Console

from y2mp3 import cli
from y2mp3.models import Job, Mode, State


def test_help_and_version_do_not_need_storage(monkeypatch, capsys):
    def unexpected(*args):
        raise AssertionError("Startup checks ran for --help/--version")

    monkeypatch.setattr(cli, "storage_root", unexpected)
    for flag in ("--help", "--version"):
        with pytest.raises(SystemExit) as result:
            cli.main([flag])
        assert result.value.code == 0
    output = capsys.readouterr().out
    assert "usage: y2mp3 " in output
    assert "__main__.py" not in output
    assert "0.1.1" in output


def test_missing_storage_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert cli.main([]) == 2


def test_audio_default_flow_prompts_finish_before_workers(monkeypatch, tmp_path):
    answers = iter(["", "https://example.test/a,https://example.test/b", "", "2", "2"])
    console = Console(file=StringIO())
    monkeypatch.setattr(console, "input", lambda prompt: next(answers))
    monkeypatch.setattr(cli, "Console", lambda **kwargs: console)
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")

    class Engine:
        def __init__(self, *args):
            pass

        def expand(self, url):
            return {"id": url[-1], "title": "Test", "formats": [{"format_id": "a"}]}

        def download(self, job, root):
            # All interactive answers must have been consumed by the main thread.
            assert next(answers, None) is None
            assert job.mode == Mode.AUDIO
            return root / f"{job.media_id}.mp3"

    monkeypatch.setattr(cli, "Downloader", Engine)
    assert cli.main(["--output-dir", str(tmp_path)]) == 0
    assert "Successful: 2" in console.file.getvalue()


def test_eof_is_invalid_invocation(monkeypatch, tmp_path):
    console = Console(file=StringIO())

    def eof(prompt):
        raise EOFError

    monkeypatch.setattr(console, "input", eof)
    monkeypatch.setattr(cli, "Console", lambda **kwargs: console)
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert cli.main(["--output-dir", str(tmp_path)]) == 2


def test_render_treats_titles_as_literal_text():
    from y2mp3.progress import Progress

    console = Console(file=StringIO(), width=40)
    job = Job(1, "https://example.test", Mode.AUDIO, title="[red]Literal[/red]", state=State.QUEUED)
    console.print(cli.render([job], Progress(), 40))
    assert "[red]Literal[/red]" in console.file.getvalue()
