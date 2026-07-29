"""Make the gnb_survey package importable, and keep the suite out of data/.

`survey.py` writes where the user keeps their survey data: solutions to
data/output/, converted CSVs to data/processed/. Those are tracked files in
this checkout, so a test that runs the CLI without saying where to write
rewrites them -- `pytest` alone was enough to leave `git status` dirty.

Two layers below. The redirect handles the defaults; the guard catches
anything that names a repo path by hand.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from gnb_survey.cli import dispatch  # noqa: E402  (needs the path above)

_DATA = _ROOT / "data"


@pytest.fixture(autouse=True)
def generated_files_go_to_tmp(tmp_path, monkeypatch):
    """Point the CLI's default output locations at this test's tmp_path.

    `_parse_args` reads these module globals on every call, so patching them
    reaches any test that builds a Namespace through the CLI -- including
    the ones that never mention an output directory at all.
    """
    monkeypatch.setattr(dispatch, "_DEFAULT_OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(dispatch, "_DEFAULT_PROCESSED_ROOT", tmp_path / "processed")


def _digest(root: Path) -> dict[str, str]:
    """Content hashes of every file under `root`, keyed by relative path."""
    if not root.is_dir():
        return {}
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(autouse=True, scope="session")
def data_directory_is_left_alone():
    """Fail the run if the suite changed anything under data/.

    The redirect above covers the defaults, but a test can still pass
    `--output-dir` or `--csv` a real path. Comparing content hashes across
    the session turns that into a failed run instead of a surprise in
    `git status` some days later.
    """
    before = _digest(_DATA)
    yield
    after = _digest(_DATA)

    touched = sorted(
        name
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    )
    assert not touched, (
        "the test suite wrote into the repo's data/ directory: "
        + ", ".join(touched)
        + ". Give the run a tmp_path via --output-dir/--csv, or let the "
        "autouse `generated_files_go_to_tmp` fixture supply the default."
    )
