"""`survey.py 20260716 solve` and `survey.py solve A.csv B.xlsx` must both parse.

The noun comes first (clig.dev: "noun verb seems to be more common"), but the
explicit-paths form has no noun, so the first positional is a verb. Which is
which is decided by membership in VERBS, not by position alone.
"""

from __future__ import annotations

import pytest

from gnb_survey.cli.dispatch import split_target_and_verb


@pytest.mark.parametrize(
    "positionals,expected",
    [
        ([], (None, None, [])),
        (["20260716"], ("20260716", None, [])),
        (["20260716", "solve"], ("20260716", "solve", [])),
        (["20260716", "convert"], ("20260716", "convert", [])),
        (["convert"], (None, "convert", [])),
        (["convert", "a.csv", "b.csv"], (None, "convert", ["a.csv", "b.csv"])),
        (["solve", "A.csv", "B.xlsx"], (None, "solve", ["A.csv", "B.xlsx"])),
        (["/tmp/A.csv", "/tmp/B.xlsx"], ("/tmp/A.csv", None, ["/tmp/B.xlsx"])),
    ],
)
def test_splits_target_from_verb(positionals, expected):
    assert split_target_and_verb(positionals) == expected
