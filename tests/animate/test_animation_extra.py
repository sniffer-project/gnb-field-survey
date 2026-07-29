"""The animation extra, once installed, must import on this interpreter.

manimgl depends on pydub, which imports the stdlib `audioop` module at import
time. PEP 594 removed `audioop` in Python 3.13, and pydub's fallback is
`pyaudioop`, a Python 2 shim that was never published. So on 3.13 a plain
`pip install -e ".[animation]"` yields a manimgl whose import chain is broken:
`survey.py <date> animate` put manimgl on PATH, passed the capability check,
then died in `import manimlib` before rendering a frame.

The extra carries `audioop-lts` on 3.13+ to put the module back. This test
fails if that pin is dropped, or if a future release breaks the chain again.
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("manimlib") is None,
    reason="animation extra is not installed",
)


def test_pydub_imports_without_the_stdlib_audioop():
    """The exact link that broke: pydub's `import audioop` at module scope."""
    importlib.import_module("pydub")


def test_manimlib_imports():
    """What the runner's subprocess needs before it can render anything."""
    importlib.import_module("manimlib")
