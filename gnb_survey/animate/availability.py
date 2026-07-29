"""Whether the renderer can actually start, not merely whether it exists.

`which("manimgl")` answers "is the binary there", which is not the question a
menu needs answered. manimgl imports its whole dependency tree before it looks
at its arguments, so an installation can be present, executable and unusable at
the same time: PEP 594 dropped the stdlib `audioop` in Python 3.13, manimgl's
pydub imports it at module scope, and `survey.py <date> animate` duly offered
the verb and then died in `from manimlib.__main__ import main`.

Asking manimgl for its version runs that same import chain, in the same
interpreter the render would use, so it answers the real question. It costs a
process start, hence `current()`: the --list table asks once per survey and the
runner asks again before it spawns, but the binary is only run once.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache
from shutil import which
from typing import Callable

BINARY: str = "manimgl"
VERSION_FLAG: str = "--version"
PROBE_TIMEOUT_S: float = 60.0
INSTALL_HINT: str = 'pip install -e ".[animation]"'

WhichFn = Callable[[str], "str | None"]
ProbeFn = Callable[[list[str]], "tuple[int, str]"]


@dataclass(frozen=True)
class Renderer:
    """What we know about the manimgl on PATH.

    The two fields stay separate because the two failures want different
    things from the user: an absent renderer needs installing, a broken one
    needs the reason it is broken.
    """

    on_path: bool
    start_error: str | None = None

    @property
    def ready(self) -> bool:
        return self.on_path and self.start_error is None


MISSING: Renderer = Renderer(on_path=False)
READY: Renderer = Renderer(on_path=True)


def broken(detail: str) -> Renderer:
    """manimgl is installed, and `detail` is why it will not start."""
    return Renderer(on_path=True, start_error=detail)


def default_probe(argv: list[str]) -> tuple[int, str]:
    """Run `argv`, returning its exit code and whatever it said.

    Failures to launch are reported, never raised. Listing what a survey can
    do is a read-only question; it should not end the program because a
    binary turned out to be unreadable or wedged.
    """
    try:
        done = subprocess.run(
            argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return 1, f"did not respond within {PROBE_TIMEOUT_S:.0f}s"
    except OSError as exc:
        return 1, str(exc)
    return done.returncode, done.stderr or done.stdout


def probe(
    *, which_fn: WhichFn | None = None, probe_fn: ProbeFn | None = None
) -> Renderer:
    """Ask the renderer whether it can start. Uncached; `current()` remembers."""
    if (which_fn or which)(BINARY) is None:
        return MISSING
    code, output = (probe_fn or default_probe)([BINARY, VERSION_FLAG])
    if code == 0:
        return READY
    return broken(_cause(output))


@lru_cache(maxsize=1)
def current() -> Renderer:
    """The answer for this process. `current.cache_clear()` asks again."""
    return probe()


def _cause(output: str) -> str:
    """A traceback's last line names the cause; the frames above it are noise."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "exited without explanation"
