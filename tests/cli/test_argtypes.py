"""`--sigma-distance`/`--sigma-elevation` must reject non-positive values at the
argparse boundary, not several stack frames deep inside scipy.

Both sigmas divide into the solver's residual weights (see solver.py's SIGMA_*
docstring), so zero produces a division by zero and a negative value inverts
the weighting silently. Neither is a value a caller could ever mean.
"""

from __future__ import annotations

import argparse

import pytest

from gnb_survey.cli.argtypes import positive_float


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["1", "0.001", "2.0", "1e-3"])
def test_accepts_positive_values(raw):
    assert positive_float(raw) == pytest.approx(float(raw))


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["0", "0.0", "-1", "-0.5"])
def test_rejects_zero_and_negative_values(raw):
    with pytest.raises(argparse.ArgumentTypeError, match="must be > 0"):
        positive_float(raw)


@pytest.mark.unit
def test_rejects_unparseable_values():
    with pytest.raises(argparse.ArgumentTypeError, match="not a number"):
        positive_float("nope")
