"""`__version__` and `--version` must agree, and `--version` must not need a
survey or a data root to answer -- clig.dev's Arguments #6.
"""

from __future__ import annotations

import re

import pytest

import gnb_survey
from gnb_survey.cli.dispatch import main


@pytest.mark.unit
def test_dunder_version_is_a_dotted_triple():
    assert re.match(r"^\d+\.\d+\.\d+", gnb_survey.__version__)


@pytest.mark.unit
def test_version_flag_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["survey.py", "--version"], output_fn=lambda _: None)
    assert exc_info.value.code == 0
    assert gnb_survey.__version__ in capsys.readouterr().out
