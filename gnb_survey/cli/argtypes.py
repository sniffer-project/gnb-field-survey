"""argparse `type=` callables that reject bad values before they reach the solver.

argparse reports a `ValueError` raised here as its own clean usage error;
letting an invalid value through instead means it resurfaces several frames
deep inside scipy, as a traceback naming neither the flag nor the file.
"""

from __future__ import annotations

import argparse


def positive_float(raw: str) -> float:
    """Parse a strictly-positive float, e.g. for `--sigma-distance`."""
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{raw!r} is not a number") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"{raw!r} must be > 0")
    return value
