"""The coordinate converter must run on a bare Python.

Field laptops get a stock interpreter and no network. Conversion is the one
thing that has to work there, so it may not import numpy, scipy, pyproj or
openpyxl -- not even transitively through a sibling module. This test reads
the source rather than importing it, so it stays honest even if some other
test has already pulled the heavy packages into sys.modules.
"""

from __future__ import annotations

import ast
import importlib
import sysconfig
from pathlib import Path

import pytest

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
    if spec.origin in ("built-in", "frozen"):
        return True
    if spec.origin is None:
        # A genuine built-in/frozen module has no submodule search locations.
        # A PEP 420 implicit namespace package (no __init__.py) also reports
        # origin=None, but *does* have search locations -- that is a real
        # (often third-party, e.g. the google.*/azure.* split-package style)
        # package, not part of the stdlib, so it must not be waved through.
        return spec.submodule_search_locations is None
    origin = Path(spec.origin).resolve()
    if "site-packages" in origin.parts or "dist-packages" in origin.parts:
        return False
    return _STDLIB_DIR in origin.parents


# Guaranteed to fail `_is_stdlib` (it is not an importable module name), so a
# dynamic import whose target cannot be resolved statically fails the guard
# loudly instead of silently passing.
_DYNAMIC_IMPORT_SENTINEL = "<dynamic>"


def _dynamic_import_root(node: ast.Call) -> str | None:
    """Return the imported root for a recognised dynamic-import call.

    Recognises `__import__("x")`, `import_module("x")` (a bare name, e.g.
    after `from importlib import import_module`), and
    `importlib.import_module("x")`. Returns None if `node` is not one of
    these calls. Returns `_DYNAMIC_IMPORT_SENTINEL` when the call is
    recognised but its first argument is not a string literal, since the
    target can't be determined by reading the source alone.
    """
    func = node.func
    is_dynamic_import_call = (
        isinstance(func, ast.Name) and func.id in ("__import__", "import_module")
    ) or (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and isinstance(func.value, ast.Name)
        and func.value.id == "importlib"
    )
    if not is_dynamic_import_call:
        return None
    first_arg = node.args[0] if node.args else None
    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
        return first_arg.value.split(".")[0]
    return _DYNAMIC_IMPORT_SENTINEL


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
        elif isinstance(node, ast.Call):
            dynamic_root = _dynamic_import_root(node)
            if dynamic_root is not None:
                roots.add(dynamic_root)
    return roots


def _sources() -> list[Path]:
    files: list[Path] = []
    for entry in CONVERT_SOURCES:
        if entry.is_dir():
            files.extend(sorted(entry.rglob("*.py")))
        elif entry.is_file():
            files.append(entry)
    return files


def test_convert_sources_exist() -> None:
    assert _sources(), f"nothing to check under {CONVERT_SOURCES}"


def test_convert_imports_only_stdlib() -> None:
    offenders: dict[str, list[str]] = {}
    for source in _sources():
        extra = sorted(r for r in _imported_roots(source) if not _is_stdlib(r))
        if extra:
            offenders[str(source.relative_to(ROOT))] = extra
    assert not offenders, (
        "the converter must run on a bare Python, but these files import "
        f"non-stdlib modules: {offenders}"
    )


def test_the_detector_catches_a_non_stdlib_import(tmp_path: Path) -> None:
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


def test_the_detector_ignores_relative_imports(tmp_path: Path) -> None:
    """`from .formats import Format` stays inside the package and is always fine."""
    sibling = tmp_path / "sibling.py"
    sibling.write_text("from .formats import Format\nfrom . import writer\n", encoding="utf-8")

    assert _imported_roots(sibling) == set()


def test_is_stdlib_rejects_namespace_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PEP 420 implicit namespace package (no __init__.py) is not stdlib.

    Real split packages such as the `google.*`/`azure.*` family are namespace
    packages: `find_spec(...).origin` is None, same as a genuine built-in or
    frozen module. The distinguishing signal is `submodule_search_locations`
    -- None for built-in/frozen, non-None for a namespace package -- so a
    namespace package must resolve to False here, never True.
    """
    package_dir = tmp_path / "not_stdlib_namespace_pkg"
    package_dir.mkdir()
    # Deliberately no __init__.py: this is what makes it an implicit
    # namespace package rather than a regular one.

    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    assert not _is_stdlib("not_stdlib_namespace_pkg")


def test_the_detector_catches_dynamic_imports(tmp_path: Path) -> None:
    """`importlib.import_module(...)` and `__import__(...)` are call expressions.

    A naive AST walk over Import/ImportFrom nodes never sees them, and
    `importlib` itself is stdlib, so nothing else would flag a `numpy` or
    `scipy` smuggled in this way.
    """
    offender = tmp_path / "dynamic_offender.py"
    offender.write_text(
        "import importlib\n"
        "importlib.import_module('numpy')\n"
        "__import__('scipy')\n",
        encoding="utf-8",
    )

    roots = _imported_roots(offender)

    assert "numpy" in roots
    assert "scipy" in roots
    assert not _is_stdlib("numpy")
    assert not _is_stdlib("scipy")


def test_the_detector_flags_unresolvable_dynamic_imports_via_sentinel(tmp_path: Path) -> None:
    """A dynamic import whose argument isn't a string literal can't be
    resolved by reading the source, so it must fail loudly (via the
    sentinel) rather than pass silently.
    """
    offender = tmp_path / "unresolvable_offender.py"
    offender.write_text(
        "import importlib\nname = 'numpy'\nimportlib.import_module(name)\n",
        encoding="utf-8",
    )

    roots = _imported_roots(offender)

    assert _DYNAMIC_IMPORT_SENTINEL in roots
    assert not _is_stdlib(_DYNAMIC_IMPORT_SENTINEL)
