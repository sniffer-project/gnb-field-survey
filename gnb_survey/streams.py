"""Shared output-sink typing and the default error sink.

Every layer of the CLI takes its result sink (`output_fn`) and its error sink
(`error_fn`) as injected parameters rather than printing directly, so the
whole flow is exercised in tests without a terminal, and callers -- not this
library -- decide where each stream lands. The default keeps clig.dev's
basic contract: results on stdout, diagnostics on stderr.
"""

from __future__ import annotations

import sys
from typing import Callable

OutputFn = Callable[[str], None]


def default_error_fn(line: str) -> None:
    print(line, file=sys.stderr)
