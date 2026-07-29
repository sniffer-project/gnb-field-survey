"""Being on PATH and being able to start are different questions."""

from __future__ import annotations

import subprocess

import pytest

from gnb_survey.animate import availability

# The failure this module exists for: manimgl on PATH, dead on import.
_AUDIOOP_TRACEBACK = """\
Traceback (most recent call last):
  File "/p/.venv/bin/manimgl", line 3, in <module>
    from manimlib.__main__ import main
  File "/p/.venv/lib/python3.13/site-packages/pydub/utils.py", line 16, in <module>
    import pyaudioop as audioop
ModuleNotFoundError: No module named 'pyaudioop'
"""


@pytest.fixture(autouse=True)
def forget_the_cached_answer():
    """A probe result cached by one test must not answer another's question."""
    availability.current.cache_clear()
    yield
    availability.current.cache_clear()


def _never_called(argv):
    raise AssertionError(f"the binary should not have been run: {argv}")


def test_a_binary_that_is_not_on_path_is_missing():
    state = availability.probe(which_fn=lambda _: None, probe_fn=_never_called)

    assert state == availability.MISSING
    assert not state.ready
    assert not state.on_path


def test_a_binary_that_starts_cleanly_is_ready():
    state = availability.probe(
        which_fn=lambda _: "/p/.venv/bin/manimgl",
        probe_fn=lambda argv: (0, "ManimGL v1.7.2"),
    )

    assert state.ready
    assert state.start_error is None


def test_a_binary_that_cannot_start_is_broken_not_missing():
    state = availability.probe(
        which_fn=lambda _: "/p/.venv/bin/manimgl",
        probe_fn=lambda argv: (1, _AUDIOOP_TRACEBACK),
    )

    assert not state.ready
    assert state.on_path, "the binary is there; it just does not work"
    assert state.start_error == "ModuleNotFoundError: No module named 'pyaudioop'", (
        "the last line of a traceback names the actual cause; the frames above "
        "it are noise in a one-line menu entry"
    )


def test_the_probe_asks_the_binary_for_its_version():
    seen: list[list[str]] = []

    availability.probe(
        which_fn=lambda _: "/p/.venv/bin/manimgl",
        probe_fn=lambda argv: (seen.append(argv), (0, ""))[1],
    )

    assert seen == [[availability.BINARY, "--version"]], (
        "--version is the cheapest subcommand that still runs the whole import "
        "chain, which is the part that breaks"
    )


def test_a_binary_that_says_nothing_useful_still_reports_something():
    state = availability.probe(
        which_fn=lambda _: "/p/.venv/bin/manimgl",
        probe_fn=lambda argv: (127, "   \n\n"),
    )

    assert not state.ready
    assert state.start_error


def test_a_hanging_binary_is_reported_not_waited_on(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="manimgl", timeout=kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)
    code, output = availability.default_probe(["manimgl", "--version"])

    assert code != 0
    assert "respond" in output


def test_an_unlaunchable_binary_is_reported_not_raised(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(subprocess, "run", refuse)
    code, output = availability.default_probe(["manimgl", "--version"])

    assert code != 0
    assert "Permission denied" in output


def test_the_answer_is_reused_for_the_life_of_the_process(monkeypatch):
    """--list asks once per survey; each ask must not cost a process start."""
    calls: list[int] = []
    monkeypatch.setattr(
        availability, "probe", lambda: calls.append(1) or availability.READY
    )

    first = availability.current()
    second = availability.current()

    assert first is second
    assert len(calls) == 1
