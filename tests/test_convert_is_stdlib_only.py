"""The coordinate converter must run on a bare Python.

Field laptops get a stock interpreter and no network. Conversion is the one
thing that has to work there, so it may not import numpy, scipy, pyproj or
openpyxl -- not even transitively through a sibling module. This test reads
the source rather than importing it, so it stays honest even if some other
test has already pulled the heavy packages into sys.modules.
"""

from __future__ import annotations

import ast
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Task 4 replaces this with: ROOT / "gnb_survey" / "convert"
CONVERT_SOURCES = (ROOT / "csv_to_mymaps.py",)

_STDLIB_DIR = Path(sysconfig.get_paths()["stdlib"]).resolve()


def _is_stdlib(module_root: str) -> bool:
    """True if `module_root` resolves inside the interpreter's stdlib directory.

    sys.stdlib_module_names would be simpler but is 3.10+; resolving against
    sysconfig works on every version and, unlike a hardcoded allowlist, cannot
    drift as the stdlib grows.
    """
    import importlib.util

    if module_root in ("__future__",):
        return True
    try:
        spec = importlib.util.find_spec(module_root)
    except (ImportError, ValueError):
        return False
    if spec is None:
        return False
    if spec.origin in (None, "built-in", "frozen"):
        return True
    origin = Path(spec.origin).resolve()
    if "site-packages" in origin.parts or "dist-packages" in origin.parts:
        return False
    return _STDLIB_DIR in origin.parents


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: stays inside the package
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _sources() -> list[Path]:
    files: list[Path] = []
    for entry in CONVERT_SOURCES:
        if entry.is_dir():
            files.extend(sorted(entry.rglob("*.py")))
        elif entry.is_file():
            files.append(entry)
    return files


def test_convert_sources_exist():
    assert _sources(), f"nothing to check under {CONVERT_SOURCES}"


def test_convert_imports_only_stdlib():
    offenders: dict[str, list[str]] = {}
    for source in _sources():
        extra = sorted(r for r in _imported_roots(source) if not _is_stdlib(r))
        if extra:
            offenders[str(source.relative_to(ROOT))] = extra
    assert not offenders, (
        "the converter must run on a bare Python, but these files import "
        f"non-stdlib modules: {offenders}"
    )


def test_the_detector_catches_a_non_stdlib_import(tmp_path):
    """A guard that cannot fail is decoration.

    test_convert_imports_only_stdlib passes the moment it is written, because
    it locks in a property that already holds. That makes it a characterisation
    test, and characterisation tests need their detector exercised in the
    failing direction too -- permanently, not once by hand.
    """
    offender = tmp_path / "offender.py"
    offender.write_text(
        "import csv\nimport numpy\nfrom scipy import optimize\n", encoding="utf-8"
    )

    roots = _imported_roots(offender)

    assert roots == {"csv", "numpy", "scipy"}
    assert _is_stdlib("csv")
    assert not _is_stdlib("numpy")
    assert not _is_stdlib("scipy")


def test_the_detector_ignores_relative_imports(tmp_path):
    """`from .formats import Format` stays inside the package and is always fine."""
    sibling = tmp_path / "sibling.py"
    sibling.write_text("from .formats import Format\nfrom . import writer\n", encoding="utf-8")

    assert _imported_roots(sibling) == set()
