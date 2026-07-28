# Unified Survey CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `main.py` and `csv_to_mymaps.py` with a single `survey.py` entry point that offers convert / solve / animate per survey, works on surveys that have no binocular workbook yet, and drives the ManimGL animation from real solved data.

**Architecture:** One front door (`survey.py`) dispatches noun-verb commands (`survey.py 20260716 solve`) and falls back to an interactive menu when given no arguments on a TTY. Today's `gnb_triangulate` package becomes `gnb_survey`, with `convert/` (stdlib-only), `triangulate/`, `animate/`, and `cli/` subpackages. Discovery stops classifying surveys as usable/unusable and instead reports, per verb, whether it can run and why not.

**Tech Stack:** Python ≥3.10 in a `.venv` built from `python3.13`; NumPy, SciPy, openpyxl, pyproj; ManimGL as an optional extra; pytest.

## Global Constraints

- **Python floor is `>=3.10`.** All work happens inside `.venv` created from `/opt/homebrew/bin/python3.13`. Never install into `/usr/bin/python3`.
- **`gnb_survey/convert/` must import only the standard library.** It runs on a bare field laptop. Task 1 adds a test that enforces this; that test must never be weakened.
- **Every new module starts with `from __future__ import annotations`**, matching the existing codebase.
- **Type annotations on every function signature** (project rule).
- **Immutability**: new dataclasses are `@dataclass(frozen=True)`. Never mutate a passed-in object.
- **No `print()` in library code.** Library functions take an injected `output_fn: Callable[[str], None]`. Only `survey.py` may default it to `print`. This is both the project's hook-enforced rule and how the existing tests stay terminal-free.
- **File size**: 200–400 lines typical, 800 max. Split rather than grow.
- **Vocabulary, taken from the on-disk layout `data/raw/surveys/<name>/{mappro,binoc}/`:**
  - a **survey** is the container (one date's work) — was called "campaign"
  - **mappro** is the MapPro CSV export — was called "survey" in `CampaignFiles.survey`
  - **binoc** is the sightings workbook
  - `SurveyPoint` keeps its meaning: one fused ground mark
- **Commit after every task.** Conventional commits (`feat:`, `refactor:`, `test:`, `chore:`, `docs:`).
- **The old entry points are deleted in the last task only**, so every earlier task is independently revertible.

## File Structure

| Path | Responsibility |
|---|---|
| `survey.py` | Sole entry point. Arg parsing, TTY detection, `output_fn` injection. ~80 lines. |
| `pyproject.toml` | Packaging, deps, `[animation]` extra, `requires-python = ">=3.10"`. |
| `gnb_survey/convert/formats.py` | `Format`, `detect_format`, `to_decimal`, decoders. Stdlib only. |
| `gnb_survey/convert/writer.py` | `convert()`, `processed_destination()`, cell sanitising. Stdlib only. |
| `gnb_survey/triangulate/*` | Today's `gnb_triangulate` modules, renamed vocabulary. |
| `gnb_survey/triangulate/assemble.py` | Was `campaign.py`. `build_survey()`. |
| `gnb_survey/triangulate/discovery.py` | `SurveyFiles`, `discover_surveys()`. `binoc` is now optional. |
| `gnb_survey/animate/scene_data.py` | `(Survey, Solution) -> scene dict/JSON`. Imports `geo`, no manim. |
| `gnb_survey/animate/runner.py` | Locate + invoke `manimgl`. |
| `gnb_survey/cli/capability.py` | `Blocked`, `convert_blocked`/`solve_blocked`/`animate_blocked`. |
| `gnb_survey/cli/menu.py` | Was `prompt.py`. Survey picker + verb picker. |
| `gnb_survey/cli/actions.py` | `do_convert`, `do_solve`, `do_animate`. |
| `gnb_survey/cli/dispatch.py` | `split_target_and_verb()`, `main()`. |

---

### Task 1: Environment, packaging, and the zero-dependency guard

**Files:**
- Create: `pyproject.toml`
- Create: `tests/test_convert_is_stdlib_only.py`
- Modify: `pytest.ini` (delete — its settings move into `pyproject.toml`)

**Interfaces:**
- Consumes: nothing.
- Produces: a working `.venv`; the guard test `test_convert_imports_only_stdlib`, which Task 4 retargets from `csv_to_mymaps.py` to `gnb_survey/convert/`.

- [ ] **Step 1: Create the virtualenv and install dependencies**

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install numpy scipy openpyxl pyproj pytest
```

`.venv/` is already in `.gitignore` — verify with `git check-ignore -q .venv && echo ignored`.

**From here on, every `python` and `pytest` command means `.venv/bin/python` and `.venv/bin/pytest`.**

- [ ] **Step 2: Verify the baseline still passes on 3.13**

Run: `.venv/bin/python -m pytest -q`
Expected: `138 passed`. If any test fails, STOP and report — a 3.9→3.13 behaviour difference must be understood before any refactoring begins, or it will be misattributed to a later task.

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "gnb-field-survey"
version = "0.1.0"
description = "5G gNB localisation from GNSS field survey data"
requires-python = ">=3.10"
dependencies = [
    "numpy",
    "scipy",
    "openpyxl",
    "pyproj",
]

[project.optional-dependencies]
animation = ["manimgl"]
dev = ["pytest"]

[tool.setuptools]
packages = ["gnb_survey"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: isolated function/module tests",
    "integration: tests that read the real files under data/raw/",
]
```

Note `packages = ["gnb_survey"]` names a package that does not exist until Task 2. That is fine — nothing installs the project in Task 1. Task 2 makes it true.

- [ ] **Step 4: Delete `pytest.ini`**

```bash
git rm pytest.ini
```

Its `testpaths` and `markers` are now in `[tool.pytest.ini_options]`. The old file's comment said markers referred to `raw_data/`; the new one says `data/raw/`, matching the actual tree.

- [ ] **Step 5: Verify pytest still discovers tests via pyproject**

Run: `.venv/bin/python -m pytest -q`
Expected: `138 passed`. If pytest collects 0 tests, `[tool.pytest.ini_options]` is not being read — check that `pyproject.toml` is at the repo root.

- [ ] **Step 6: Write the failing zero-dependency guard test**

Create `tests/test_convert_is_stdlib_only.py`. It points at `csv_to_mymaps.py` for now; Task 4 repoints it at the package.

```python
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
```

- [ ] **Step 7: Run the guard tests**

Run: `.venv/bin/python -m pytest tests/test_convert_is_stdlib_only.py -v`
Expected: **PASS** (4 tests). `csv_to_mymaps.py` already imports only `argparse, csv, math, re, sys, decimal, enum, pathlib, typing`.

`test_convert_imports_only_stdlib` passes on arrival by design — it locks in a property that already holds, so Task 4's move cannot silently break it. The two detector tests are what make it trustworthy: they prove the check fires on `numpy`/`scipy` and does not fire on relative imports.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml tests/test_convert_is_stdlib_only.py
git rm --cached pytest.ini 2>/dev/null || true
git add -A pytest.ini
git commit -m "chore: add pyproject, venv-based toolchain, and stdlib-only guard for the converter"
```

---

### Task 2: Rename the package to `gnb_survey`

**Files:**
- Rename: `gnb_triangulate/` → `gnb_survey/triangulate/`
- Create: `gnb_survey/__init__.py`
- Modify: `main.py` (imports), all files under `tests/gnb_triangulate/`
- Rename: `tests/gnb_triangulate/` → `tests/triangulate/`

**Interfaces:**
- Consumes: Task 1's venv.
- Produces: every module importable as `gnb_survey.triangulate.<name>`. No symbol names change in this task.

- [ ] **Step 1: Move the package**

```bash
mkdir -p gnb_survey
git mv gnb_triangulate gnb_survey/triangulate
git mv tests/gnb_triangulate tests/triangulate
printf '"""gNB field survey toolkit."""\n' > gnb_survey/__init__.py
git add gnb_survey/__init__.py
```

- [ ] **Step 2: Rewrite the imports**

```bash
grep -rl "gnb_triangulate" --include="*.py" . \
  | xargs sed -i '' 's/gnb_triangulate/gnb_survey.triangulate/g'
```

On Linux use `sed -i` without the `''`.

- [ ] **Step 3: Fix the intra-package relative imports**

The above rewrite does not touch `from .geo import ...` style imports, which stay correct. But `gnb_survey/triangulate/__init__.py` may name the old package. Check and fix:

```bash
grep -rn "gnb_survey.triangulate" gnb_survey/triangulate/*.py
```

Any hit *inside* the package should become a relative import (`from . import geo`). There should be none — the package uses relative imports throughout — but verify rather than assume.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `140 passed` (138 original + 2 guard tests from Task 1).

If you see `ModuleNotFoundError: No module named 'gnb_triangulate'`, a string was missed — `grep -rn "gnb_triangulate" --include="*.py" .` finds it.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename gnb_triangulate package to gnb_survey.triangulate"
```

---

### Task 3: Rename the domain vocabulary — campaign becomes survey

**Files:**
- Rename: `gnb_survey/triangulate/campaign.py` → `gnb_survey/triangulate/assemble.py`
- Modify: `gnb_survey/triangulate/{models,errors,solver,discovery,mymaps,report,prompt}.py`, `main.py`, all files under `tests/triangulate/`

**Interfaces:**
- Consumes: Task 2's package layout.
- Produces these renamed symbols, which every later task uses:
  - `models.Survey` (was `Campaign`), with `.name` and `.points: tuple[SurveyPoint, ...]`
  - `models.Solution.survey_name: str` (was `campaign_name`)
  - `errors.SurveyDataError` (was `CampaignDataError`)
  - `assemble.build_survey(stations, readings, name) -> Survey` (was `campaign.build_campaign`)
  - `solver.solve_survey(survey, sigma_distance_m, sigma_elevation_deg) -> Solution`
  - `discovery.SurveyFiles` with fields `name, mappro, binoc, export_count` — note the old `.survey` field becomes `.mappro`. Task 5 later replaces `export_count: int` with `exports: tuple[Path, ...]` plus a derived property, and makes `binoc` optional; this task changes names only, not shape.
  - `discovery.discover_surveys(data_root) -> DiscoveryResult`
  - `mymaps.default_csv_name(survey_name: str) -> str`
  - `prompt.select_survey(...)`

- [ ] **Step 1: Move the module**

```bash
git mv gnb_survey/triangulate/campaign.py gnb_survey/triangulate/assemble.py
```

Named `assemble.py`, not `survey.py`, so it does not read as a sibling of the root `survey.py` entry point added in Task 6.

- [ ] **Step 2: Apply the identifier renames**

Order matters — the longest, most specific names first, so a short pattern cannot corrupt a long one.

```bash
FILES=$(grep -rl "[Cc]ampaign" --include="*.py" . | grep -v '/\.venv/')
for f in $FILES; do
  sed -i '' \
    -e 's/CampaignDataError/SurveyDataError/g' \
    -e 's/CampaignFiles/SurveyFiles/g' \
    -e 's/discover_campaigns/discover_surveys/g' \
    -e 's/build_campaign/build_survey/g' \
    -e 's/solve_campaign/solve_survey/g' \
    -e 's/select_campaign/select_survey/g' \
    -e 's/campaign_name/survey_name/g' \
    -e 's/_no_campaigns_message/_no_surveys_message/g' \
    -e 's/\bCampaign\b/Survey/g' \
    -e 's/\bcampaign\b/survey/g' \
    -e 's/\bcampaigns\b/surveys/g' \
    "$f"
done
```

- [ ] **Step 3: Fix the two collisions the blind rename creates**

The mechanical rename produces `SurveyFiles.survey` (the MapPro CSV path) and `from .assemble import build_survey` used alongside a local variable now also called `survey`. Resolve by renaming the field:

In `gnb_survey/triangulate/discovery.py`, the dataclass becomes:

```python
@dataclass(frozen=True)
class SurveyFiles:
    """One survey on disk: where its input files are."""

    name: str
    mappro: Path          # the preferred MapPro CSV export
    binoc: Path
    export_count: int
```

Then repoint every use of the old field name:

```bash
grep -rn "\.survey\b" --include="*.py" . | grep -v '/\.venv/'
```

Every hit that refers to a `SurveyFiles` instance becomes `.mappro`. Hits on `args.survey` or a local `survey` variable of type `models.Survey` are unrelated — read each one. Expect roughly a dozen, concentrated in `main.py` and `tests/triangulate/test_main.py`.

- [ ] **Step 4: Check for over-eager replacements in prose**

```bash
grep -rn "survey survey\|surveys surveys\|the survey CSV" --include="*.py" . | grep -v '/\.venv/'
```

Docstrings that said "the campaign's survey CSV" now read "the survey's survey CSV". Rewrite those to "the survey's MapPro export". This is cosmetic but the docstrings are how the next reader learns the vocabulary, so leaving them contradictory defeats the whole task.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `140 passed`.

- [ ] **Step 6: Confirm the old vocabulary is gone**

```bash
grep -rni "campaign" --include="*.py" . | grep -v '/\.venv/'
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: rename campaign to survey throughout, matching data/raw/surveys/ layout"
```

---

### Task 4: Absorb the converter into `gnb_survey/convert/`

**Files:**
- Create: `gnb_survey/convert/__init__.py`, `gnb_survey/convert/formats.py`, `gnb_survey/convert/writer.py`
- Modify: `tests/test_convert_is_stdlib_only.py`, `tests/csv_to_mymaps/test_csv_to_mymaps.py`
- Keep (do not delete yet): `csv_to_mymaps.py`

**Interfaces:**
- Consumes: nothing from Tasks 2–3.
- Produces:
  - `gnb_survey.convert.formats`: `Format`, `UnknownFormat`, `BARE_NUMERIC_FORMATS`, `COORD_COLS`, `PLOT_COLS`, `PRECISION`, `detect_format(rows) -> Format`, `to_decimal(raw, fmt) -> str | None`
  - `gnb_survey.convert.writer`: `convert(in_path, out_path=None, output_fn=...) -> Path`, `processed_destination(source, raw_root, processed_root) -> Path`
  - `gnb_survey.convert` re-exports all of the above.

- [ ] **Step 1: Split the source**

`csv_to_mymaps.py` splits at line 326 — everything up to and including `detect_format` is format detection; `convert()` onward is writing.

```bash
mkdir -p gnb_survey/convert
```

`gnb_survey/convert/formats.py` = the module docstring plus lines 41–325 of `csv_to_mymaps.py` (imports through `detect_format`), minus `import argparse` and the `_safe_cell` function (which moves to `writer.py`). Copy the code verbatim; do not retype or "improve" it. The nine-format detection logic is subtle and load-bearing — the docstring explains why magnitude heuristics were rejected.

`gnb_survey/convert/writer.py` holds `_safe_cell`, `_FORMULA_PREFIXES`, `_NUMERIC_RE`, `_C0_STRIP`/`_SEPARATORS`, `convert()`, and the new `processed_destination()`.

- [ ] **Step 2: Write `gnb_survey/convert/__init__.py`**

```python
"""MapPro coordinate conversion. Standard library only -- see the guard test.

This subpackage must keep working on a stock Python with no site-packages,
because converting a survey is what happens on the field laptop.
"""

from __future__ import annotations

from .formats import (
    BARE_NUMERIC_FORMATS,
    COORD_COLS,
    PLOT_COLS,
    PRECISION,
    Format,
    UnknownFormat,
    detect_format,
    to_decimal,
)
from .writer import convert, processed_destination

__all__ = [
    "BARE_NUMERIC_FORMATS",
    "COORD_COLS",
    "PLOT_COLS",
    "PRECISION",
    "Format",
    "UnknownFormat",
    "convert",
    "detect_format",
    "processed_destination",
    "to_decimal",
]
```

- [ ] **Step 3: Write the failing test for `processed_destination`**

Add to a new file `tests/convert/test_writer.py`:

```python
"""Converted output mirrors the raw tree under data/processed/."""

from __future__ import annotations

from pathlib import Path

from gnb_survey.convert import processed_destination


def test_mirrors_the_raw_tree_into_processed():
    raw_root = Path("/p/data/raw")
    processed_root = Path("/p/data/processed")
    source = raw_root / "surveys" / "20260716" / "mappro" / "dd (Decimal).csv"

    result = processed_destination(source, raw_root, processed_root)

    assert result == (
        processed_root / "surveys" / "20260716" / "mappro" / "dd (Decimal)_mymaps.csv"
    )


def test_writes_beside_the_source_when_outside_the_raw_tree():
    raw_root = Path("/p/data/raw")
    processed_root = Path("/p/data/processed")
    source = Path("/somewhere/else/export.csv")

    result = processed_destination(source, raw_root, processed_root)

    assert result == Path("/somewhere/else/export_mymaps.csv")
```

Create `tests/convert/__init__.py`? No — the existing test tree has no `__init__.py` files (`tests/conftest.py` handles the path). Match that: no `__init__.py`.

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/convert/test_writer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gnb_survey.convert'` (if Step 1 is not done) or `ImportError: cannot import name 'processed_destination'`.

- [ ] **Step 5: Implement `processed_destination` in `writer.py`**

```python
def processed_destination(
    source: Path, raw_root: Path, processed_root: Path
) -> Path:
    """Where a converted copy of `source` belongs.

    Mirrors the path under raw_root into processed_root, so
    data/raw/surveys/X/mappro/E.csv becomes
    data/processed/surveys/X/mappro/E_mymaps.csv. Sources from outside the
    raw tree -- a one-off file a user passed by path -- are written beside
    themselves, because inventing a location under data/processed/ for them
    would bury the output somewhere the user never looks.
    """
    name = source.stem + "_mymaps.csv"
    try:
        relative = source.parent.relative_to(raw_root)
    except ValueError:
        return source.with_name(name)
    return processed_root / relative / name
```

- [ ] **Step 6: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/convert/test_writer.py -v`
Expected: 2 passed.

- [ ] **Step 7: Change `convert()` to accept a destination and an output function**

The current `convert()` hardcodes its output path and calls `print` five times. Both must become parameters. New signature and body changes only — the conversion logic itself is untouched:

```python
def convert(
    in_path: Path,
    out_path: Path | None = None,
    *,
    output_fn: Callable[[str], None],
    warn_fn: Callable[[str], None] | None = None,
) -> Path:
    """Rewrite a MapPro CSV's coordinate columns to decimal degrees.

    `out_path` defaults to a sibling `*_mymaps.csv`, preserving the behaviour
    of the standalone script. Warnings go to `warn_fn` if given, else to
    `output_fn`; nothing is printed directly, so callers control the stream
    and tests need no capsys.
    """
    if out_path is None:
        out_path = in_path.with_name(in_path.stem + "_mymaps.csv")
    if warn_fn is None:
        warn_fn = output_fn
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ...
```

Replace each `print(..., file=sys.stderr)` with `warn_fn(...)` and each plain `print(...)` with `output_fn(...)`, keeping the message text identical. Drop the now-unused `import sys`.

The `out_path.parent.mkdir(...)` line is new and necessary: `data/processed/surveys/<new-date>/mappro/` will not exist for a survey converted for the first time.

- [ ] **Step 8: Repoint the two existing test files**

In `tests/csv_to_mymaps/test_csv_to_mymaps.py`, change:

```python
from csv_to_mymaps import Format, UnknownFormat, detect_format, to_decimal
```

to:

```python
from gnb_survey.convert import Format, UnknownFormat, detect_format, to_decimal
```

Then move the directory to match the new package name:

```bash
git mv tests/csv_to_mymaps tests/convert_formats
```

(`tests/convert/` is already taken by Step 3's new file; keeping the format tests in their own directory preserves the existing split between format detection and writing.)

In `tests/test_convert_is_stdlib_only.py`, change:

```python
CONVERT_SOURCES = (ROOT / "csv_to_mymaps.py",)
```

to:

```python
CONVERT_SOURCES = (ROOT / "gnb_survey" / "convert",)
```

**Change that one line and nothing else in this file.** Task 1's review found two holes in the detector as originally specified here (PEP 420 namespace packages read as stdlib; `importlib.import_module("numpy")` invisible to the AST walk), and commit `3499beb` fixed both plus added tests that fail against the old logic. The file on disk is authoritative — do not restore the version printed in Task 1 Step 6 of this plan, which predates that fix.

- [ ] **Step 8b: Delete `csv_to_mymaps.py`**

```bash
git rm csv_to_mymaps.py
```

The move is complete and nothing references it any more — confirm with:

```bash
grep -rn "csv_to_mymaps" --include="*.py" . | grep -v '/\.venv/'
```

Expected: no output. Deleting here rather than in Task 8 avoids leaving a near-verbatim duplicate of the whole converter on disk for four tasks. `main.py` does not import it, so nothing breaks.

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `144 passed` (138 original + 4 guard + 2 `processed_destination`).

If `test_convert_imports_only_stdlib` fails naming `typing` or `decimal`, the `_is_stdlib` helper is misresolving — check that `.venv/bin/python` is the interpreter, since a venv's `sysconfig` stdlib path differs from the system one.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor: move the MapPro converter into gnb_survey.convert with injected output"
```

---

### Task 5: Capability-aware discovery

**Files:**
- Modify: `gnb_survey/triangulate/discovery.py`
- Create: `gnb_survey/cli/__init__.py`, `gnb_survey/cli/capability.py`
- Create: `tests/cli/test_capability.py`
- Modify: `tests/triangulate/test_discovery.py`

**Interfaces:**
- Consumes: `SurveyFiles` from Task 3.
- Produces:
  - `discovery.SurveyFiles(name: str, mappro: Path, exports: tuple[Path, ...], binoc: Path | None, scene_json: Path | None)`
  - `discovery.DiscoveryResult(surveys: tuple[SurveyFiles, ...], unreadable: tuple[tuple[str, str], ...])`
  - `discovery.discover_surveys(data_root: Path, output_dir: Path | None = None) -> DiscoveryResult`
  - `capability.Blocked(reason: str, fix: str)`
  - `capability.VERBS: tuple[str, ...]` = `("convert", "solve", "animate")`
  - `capability.convert_blocked(files) -> Blocked | None`
  - `capability.solve_blocked(files) -> Blocked | None`
  - `capability.animate_blocked(files, *, manim_available: bool | None = None) -> Blocked | None`
  - `capability.blocked_for(verb, files, *, manim_available=None) -> Blocked | None`

- [ ] **Step 1: Write the failing discovery test**

Add to `tests/triangulate/test_discovery.py`:

```python
def test_a_survey_without_a_workbook_is_still_discovered(tmp_path):
    """MapPro comes back from the field days before the sightings are typed up.

    Such a survey is fully convertible, so dropping it from the results (as
    the old available/unavailable split did) hides work the user can do.
    """
    folder = tmp_path / "surveys" / "20260722" / "mappro"
    folder.mkdir(parents=True)
    (folder / "dd (Decimal).csv").write_text("Point Name\nPt1\n", encoding="latin-1")

    result = discover_surveys(tmp_path)

    assert [s.name for s in result.surveys] == ["20260722"]
    assert result.surveys[0].binoc is None
    assert result.unreadable == ()


def test_a_folder_with_no_exports_is_unreadable(tmp_path):
    (tmp_path / "surveys" / "20260723").mkdir(parents=True)

    result = discover_surveys(tmp_path)

    assert result.surveys == ()
    assert len(result.unreadable) == 1
    name, reason = result.unreadable[0]
    assert name == "20260723"
    assert "csv" in reason.lower()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/triangulate/test_discovery.py -v`
Expected: FAIL — `AttributeError: 'DiscoveryResult' object has no attribute 'surveys'`, and the binoc-less survey lands in `unavailable`.

- [ ] **Step 3: Rewrite `discovery.py`**

```python
@dataclass(frozen=True)
class SurveyFiles:
    """One survey on disk, and which of its inputs are present."""

    name: str
    mappro: Path                    # the preferred MapPro export
    exports: tuple[Path, ...]       # every export found, newest-preferred first
    binoc: Path | None              # None until the sightings are typed up
    scene_json: Path | None = None  # written by a previous solve

    @property
    def export_count(self) -> int:
        return len(self.exports)


@dataclass(frozen=True)
class DiscoveryResult:
    """What a scan found, and which folders held nothing usable at all."""

    surveys: tuple[SurveyFiles, ...]
    unreadable: tuple[tuple[str, str], ...]  # (name, reason)


def discover_surveys(
    data_root: Path, output_dir: Path | None = None
) -> DiscoveryResult:
    """Scan a data root, newest survey first.

    A survey needs only a MapPro export to be discovered. Whether it can be
    solved or animated is a separate question, answered by cli.capability --
    keeping "what exists" apart from "what you can do with it".
    """
    survey_root = Path(data_root) / SURVEY_SUBDIR
    if not survey_root.is_dir():
        return DiscoveryResult(surveys=(), unreadable=())

    surveys: list[SurveyFiles] = []
    unreadable: list[tuple[str, str]] = []
    folders = sorted(
        (d for d in survey_root.iterdir() if d.is_dir()),
        key=lambda d: d.name,
        reverse=True,
    )
    for folder in folders:
        exports = _usable(list(folder.rglob("*.csv")))
        if not exports:
            unreadable.append((folder.name, "no .csv exports in the survey folder"))
            continue
        scene = None
        if output_dir is not None:
            candidate = Path(output_dir) / f"{folder.name}_scene.json"
            scene = candidate if candidate.is_file() else None
        surveys.append(
            SurveyFiles(
                name=folder.name,
                mappro=_preferred_export(exports),
                exports=tuple(exports),
                binoc=_find_binoc(Path(data_root), folder.name),
                scene_json=scene,
            )
        )
    return DiscoveryResult(tuple(surveys), tuple(unreadable))
```

`_usable`, `_preferred_export`, `_find_binoc` and `SURVEY_SUBDIR` are unchanged. `_find_binoc` already returns `None` when nothing matches, so it needs no edit — only its caller stops treating `None` as disqualifying.

- [ ] **Step 4: Run the discovery tests**

Run: `.venv/bin/python -m pytest tests/triangulate/test_discovery.py -v`
Expected: PASS. Existing tests in that file that assert on `result.campaigns`/`result.unavailable` were renamed to `.surveys`/`.unavailable` by Task 3's sed; rename `.unavailable` to `.unreadable` in them now, and delete any test asserting that a binoc-less survey is excluded — that behaviour is what this task deliberately removes.

- [ ] **Step 5: Write the failing capability test**

Create `tests/cli/test_capability.py`:

```python
"""Each verb reports whether it can run, and if not, what to do about it."""

from __future__ import annotations

from pathlib import Path

from gnb_survey.cli.capability import (
    animate_blocked,
    blocked_for,
    convert_blocked,
    solve_blocked,
)
from gnb_survey.triangulate.discovery import SurveyFiles

_CSV = Path("/p/data/raw/surveys/20260722/mappro/dd (Decimal).csv")
_XLSX = Path("/p/data/raw/surveys/20260722/binoc/20260722.xlsx")


def _files(*, binoc: Path | None, scene: Path | None = None) -> SurveyFiles:
    return SurveyFiles(
        name="20260722",
        mappro=_CSV,
        exports=(_CSV,),
        binoc=binoc,
        scene_json=scene,
    )


def test_convert_is_never_blocked_for_a_discovered_survey():
    assert convert_blocked(_files(binoc=None)) is None


def test_solve_is_blocked_without_a_workbook_and_names_the_file():
    blocked = solve_blocked(_files(binoc=None))
    assert blocked is not None
    assert "20260722" in blocked.reason
    assert "xlsx" in blocked.reason
    assert "binoc" in blocked.fix


def test_solve_is_available_with_a_workbook():
    assert solve_blocked(_files(binoc=_XLSX)) is None


def test_animate_is_blocked_when_it_cannot_solve():
    blocked = animate_blocked(_files(binoc=None), manim_available=True)
    assert blocked is not None
    assert "xlsx" in blocked.reason


def test_animate_is_blocked_when_manimgl_is_absent():
    blocked = animate_blocked(_files(binoc=_XLSX), manim_available=False)
    assert blocked is not None
    assert "manimgl" in blocked.reason
    assert "animation" in blocked.fix


def test_animate_is_available_with_a_workbook_and_manimgl():
    assert animate_blocked(_files(binoc=_XLSX), manim_available=True) is None


def test_animate_works_from_an_existing_scene_without_a_workbook():
    """A solve already happened; the workbook can be gone and the video still renders."""
    scene = Path("/p/data/output/20260722_scene.json")
    assert animate_blocked(_files(binoc=None, scene=scene), manim_available=True) is None


def test_blocked_for_rejects_an_unknown_verb():
    import pytest

    with pytest.raises(ValueError, match="unknown verb"):
        blocked_for("teleport", _files(binoc=_XLSX))
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/cli/test_capability.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gnb_survey.cli'`.

- [ ] **Step 7: Implement `capability.py`**

```python
"""What each verb can do with a given survey, and why not when it cannot.

Availability is computed here rather than baked into discovery so that "what
files exist" and "what you can do with them" stay separable: the menu, the
--list table and the error paths all ask the same question and get the same
answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from shutil import which

from ..triangulate.discovery import SurveyFiles

VERBS: tuple[str, ...] = ("convert", "solve", "animate")

MANIM_BINARY = "manimgl"
_INSTALL_HINT = 'pip install -e ".[animation]"'


@dataclass(frozen=True)
class Blocked:
    """Why a verb cannot run, and the single action that would unblock it."""

    reason: str
    fix: str


def convert_blocked(files: SurveyFiles) -> Blocked | None:
    if not files.exports:
        return Blocked(
            reason="no MapPro CSV export",
            fix=f"put an export in data/raw/surveys/{files.name}/mappro/",
        )
    return None


def solve_blocked(files: SurveyFiles) -> Blocked | None:
    if files.binoc is None:
        return Blocked(
            reason=f"no {files.name}*.xlsx sightings workbook",
            fix=f"add the binocular workbook under data/raw/surveys/{files.name}/binoc/",
        )
    return None


def animate_blocked(
    files: SurveyFiles, *, manim_available: bool | None = None
) -> Blocked | None:
    """Animation needs a solution and a renderer.

    An existing scene JSON stands in for the solve, so a survey whose workbook
    has been archived can still be re-rendered.
    """
    if files.scene_json is None:
        blocked = solve_blocked(files)
        if blocked is not None:
            return blocked
    if manim_available is None:
        manim_available = which(MANIM_BINARY) is not None
    if not manim_available:
        return Blocked(
            reason=f"{MANIM_BINARY} is not installed",
            fix=_INSTALL_HINT,
        )
    return None


_CHECKS = {
    "convert": convert_blocked,
    "solve": solve_blocked,
}


def blocked_for(
    verb: str, files: SurveyFiles, *, manim_available: bool | None = None
) -> Blocked | None:
    """Dispatch to the check for `verb`."""
    if verb == "animate":
        return animate_blocked(files, manim_available=manim_available)
    try:
        return _CHECKS[verb](files)
    except KeyError:
        raise ValueError(
            f"unknown verb {verb!r}; expected one of {', '.join(VERBS)}"
        ) from None
```

Also create `gnb_survey/cli/__init__.py` containing `"""Command line interface."""`.

- [ ] **Step 8: Run the capability tests**

Run: `.venv/bin/python -m pytest tests/cli/test_capability.py -v`
Expected: 8 passed.

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green. `main.py` still calls `discover_surveys` and reads `result.surveys`/`.unreadable` — Task 3's sed renamed `.campaigns` to `.surveys`, but `.unavailable` is now `.unreadable`, and `SurveyFiles.survey` is now `.mappro` with `export_count` a property. Fix `main.py`'s `_describe`, `_no_surveys_message` and `_resolve` accordingly; it is deleted in Task 8, but it must stay green until then.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: report per-verb capability so surveys without a workbook stay usable"
```

---

### Task 6: The unified CLI

**Files:**
- Create: `survey.py`, `gnb_survey/cli/dispatch.py`, `gnb_survey/cli/actions.py`
- Rename: `gnb_survey/triangulate/prompt.py` → `gnb_survey/cli/menu.py`
- Create: `tests/cli/test_dispatch.py`, `tests/cli/test_menu.py`
- Modify: `tests/triangulate/test_prompt.py` → `tests/cli/test_menu.py`

**Interfaces:**
- Consumes: `capability.*` and `discovery.*` from Task 5; `convert.convert`, `convert.processed_destination` from Task 4; `solver.solve_survey`, `assemble.build_survey`, `report.format_solution`, `mymaps.write_csv`, `mymaps.default_csv_name` from Task 3.
- Produces:
  - `dispatch.split_target_and_verb(positionals: list[str]) -> tuple[str | None, str | None, list[str]]`
  - `dispatch.main(argv, *, input_fn=input, output_fn=print, is_tty=None) -> int`
  - `actions.do_convert(files, *, raw_root, processed_root, output_fn) -> int`
  - `actions.do_solve(files, args, *, output_dir, output_fn) -> int`
  - `actions.do_animate(files, args, *, output_dir, output_fn) -> int`
  - `menu.select_survey(result, *, input_fn, output_fn) -> SurveyFiles | None`
  - `menu.select_verb(files, *, input_fn, output_fn, manim_available=None) -> str | None`

- [ ] **Step 1: Write the failing test for argument splitting**

Create `tests/cli/test_dispatch.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/cli/test_dispatch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gnb_survey.cli.dispatch'`.

- [ ] **Step 3: Implement `split_target_and_verb`**

Create `gnb_survey/cli/dispatch.py` containing **only** the function below plus `from __future__ import annotations` and `from .capability import VERBS`. The full module arrives in Step 9. Keeping it minimal here matters: the finished `dispatch.py` imports `actions`, which imports `..animate`, which does not exist until Step 8 — so a full module now would make this step's test fail on an unrelated import.

```python
def split_target_and_verb(
    positionals: list[str],
) -> tuple[str | None, str | None, list[str]]:
    """Separate the survey from the verb.

    Two orderings are legal, and a verb name is what tells them apart:

        survey.py 20260716 solve       -> ("20260716", "solve", [])
        survey.py solve A.csv B.xlsx   -> (None, "solve", ["A.csv", "B.xlsx"])

    A survey named "solve" would be ambiguous. Survey names are dates, so
    this cannot arise in practice; `main` rejects it explicitly rather than
    resolving it silently.
    """
    if not positionals:
        return None, None, []
    if positionals[0] in VERBS:
        return None, positionals[0], positionals[1:]
    if len(positionals) >= 2 and positionals[1] in VERBS:
        return positionals[0], positionals[1], positionals[2:]
    return positionals[0], None, positionals[1:]
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/cli/test_dispatch.py -v`
Expected: 8 passed.

- [ ] **Step 5: Move the picker and add a verb menu**

```bash
git mv gnb_survey/triangulate/prompt.py gnb_survey/cli/menu.py
git mv tests/triangulate/test_prompt.py tests/cli/test_menu.py
```

Fix the import in `tests/cli/test_menu.py` to `from gnb_survey.cli import menu`. In `menu.py`, change the relative import from `from .discovery import ...` to `from ..triangulate.discovery import ...`.

Update `select_survey`'s listing loop so a missing workbook is shown rather than hidden:

```python
    for index, files in enumerate(result.surveys, start=1):
        binoc = files.binoc.name if files.binoc is not None else "-- not yet"
        output_fn(
            f"    {index}) {files.name}   {files.export_count} export format(s)"
            f" · binoc: {binoc}"
        )
    for name, reason in result.unreadable:
        output_fn(f"       {name}   unreadable: {reason}")
```

Then add the verb picker:

```python
def select_verb(
    files: SurveyFiles,
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
    manim_available: bool | None = None,
) -> str | None:
    """Ask what to do with `files`. Blocked verbs are listed, not hidden.

    Seeing "solve -- needs 20260722*.xlsx" tells the user what to go and
    fetch. Omitting the line would leave them wondering whether the tool
    supports solving at all.
    """
    blocks = {
        verb: blocked_for(verb, files, manim_available=manim_available)
        for verb in VERBS
    }
    output_fn("")
    output_fn(f"  {files.name}")
    output_fn("")
    for index, verb in enumerate(VERBS, start=1):
        blocked = blocks[verb]
        if blocked is None:
            output_fn(f"    {index}) {_VERB_LABELS[verb]}")
        else:
            output_fn(f"       {_VERB_LABELS[verb]}   -- {blocked.reason}")
    output_fn("    b) back")
    output_fn("")

    while True:
        try:
            answer = input_fn("  Select: ").strip().lower()
        except EOFError:
            return None
        if answer in ("b", ""):
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(VERBS):
            verb = VERBS[int(answer) - 1]
            blocked = blocks[verb]
            if blocked is None:
                return verb
            output_fn(f"  {verb} is unavailable: {blocked.reason}")
            output_fn(f"  To fix: {blocked.fix}")
            continue
        output_fn(f"  Not a choice: {answer!r}")


_VERB_LABELS = {
    "convert": "Convert MapPro exports to My Maps CSV",
    "solve": "Solve the gNB position",
    "animate": "Render the animation",
}
```

- [ ] **Step 6: Write the failing menu test**

Append to `tests/cli/test_menu.py`:

```python
def test_verb_menu_shows_a_blocked_verb_with_its_reason():
    lines: list[str] = []
    files = SurveyFiles(
        name="20260722",
        mappro=Path("/p/m.csv"),
        exports=(Path("/p/m.csv"),),
        binoc=None,
        scene_json=None,
    )

    chosen = menu.select_verb(
        files,
        input_fn=lambda _: "1",
        output_fn=lines.append,
        manim_available=True,
    )

    assert chosen == "convert"
    listing = "\n".join(lines)
    assert "Solve the gNB position" in listing
    assert "20260722*.xlsx" in listing


def test_verb_menu_refuses_to_pick_a_blocked_verb():
    """Typing the number of a blocked verb must not run it."""
    answers = iter(["2", "b"])
    lines: list[str] = []
    files = SurveyFiles(
        name="20260722",
        mappro=Path("/p/m.csv"),
        exports=(Path("/p/m.csv"),),
        binoc=None,
        scene_json=None,
    )

    chosen = menu.select_verb(
        files,
        input_fn=lambda _: next(answers),
        output_fn=lines.append,
        manim_available=True,
    )

    assert chosen is None
    assert any("To fix:" in line for line in lines)
```

- [ ] **Step 7: Run the menu tests**

Run: `.venv/bin/python -m pytest tests/cli/test_menu.py -v`
Expected: all pass, including the pre-existing `select_survey` tests.

- [ ] **Step 8: Stub the animate package, then implement `actions.py`**

`actions.py` imports `..animate`, which Task 7 fills in. Create the stubs first so imports resolve:

```bash
mkdir -p gnb_survey/animate
printf '"""Rendering the solved geometry."""\n' > gnb_survey/animate/__init__.py
cat > gnb_survey/animate/scene_data.py <<'PY'
"""Placeholder: implemented in Task 7."""

from __future__ import annotations


def write_scene(*args, **kwargs):
    raise NotImplementedError("scene_data lands in Task 7")


def build_scene(*args, **kwargs):
    raise NotImplementedError("scene_data lands in Task 7")
PY
cat > gnb_survey/animate/runner.py <<'PY'
"""Placeholder: implemented in Task 7."""

from __future__ import annotations


class ManimMissing(RuntimeError):
    """manimgl is not on PATH."""


def render(*args, **kwargs):
    raise NotImplementedError("runner lands in Task 7")
PY
```

Do not write tests against these stubs — Task 7 replaces both files entirely and adds the real tests.

```python
"""One function per verb. Each returns a process exit code and prints nothing."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from ..animate import runner
from ..convert import UnknownFormat, convert, processed_destination
from ..triangulate.assemble import build_survey
from ..triangulate.binoc import read_binoc_readings
from ..triangulate.discovery import SurveyFiles
from ..triangulate.errors import SurveyDataError
from ..triangulate.mappro import read_stations
from ..triangulate.mymaps import default_csv_name, write_csv
from ..triangulate.report import format_solution
from ..triangulate.solver import solve_survey

OutputFn = Callable[[str], None]


def do_convert(
    files: SurveyFiles,
    *,
    raw_root: Path,
    processed_root: Path,
    output_fn: OutputFn,
) -> int:
    """Convert every export of one survey."""
    failures = 0
    for export in files.exports:
        destination = processed_destination(export, raw_root, processed_root)
        try:
            convert(export, destination, output_fn=output_fn)
        except UnknownFormat as exc:
            output_fn(f"error: {export.name}: {exc}")
            failures += 1
    return 1 if failures else 0


def do_solve(
    files: SurveyFiles,
    args: argparse.Namespace,
    *,
    output_dir: Path,
    output_fn: OutputFn,
) -> int:
    """Solve one survey, then write the My Maps CSV and the scene JSON."""
    if files.binoc is None:
        output_fn(f"error: {files.name} has no sightings workbook.")
        return 1
    try:
        survey = build_survey(
            read_stations(files.mappro),
            read_binoc_readings(files.binoc),
            name=args.name or files.name,
        )
    except SurveyDataError as exc:
        # Field-data problems, not crashes: name what is wrong and which file
        # to fix. Re-prompting cannot repair a spreadsheet.
        output_fn(f"error: {exc}")
        return 1

    solution = solve_survey(survey, args.sigma_distance, args.sigma_elevation)
    output_fn(format_solution(solution))

    output_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_csv:
        destination = args.csv or output_dir / default_csv_name(survey.name)
        try:
            rows = write_csv(solution, destination)
        except ValueError as exc:
            output_fn(f"error: {exc}")
            return 1
        output_fn(f"  Wrote {rows} rows to {destination}")

    # Task 7 adds the scene-data write here.
    return 0


def do_animate(
    files: SurveyFiles,
    args: argparse.Namespace,
    *,
    output_dir: Path,
    output_fn: OutputFn,
) -> int:
    """Render the animation, solving first if no scene data exists yet."""
    scene_path = output_dir / f"{files.name}_scene.json"
    if not scene_path.is_file():
        output_fn(f"  No scene data for {files.name}; solving first.")
        code = do_solve(files, args, output_dir=output_dir, output_fn=output_fn)
        if code != 0:
            return code
    try:
        return runner.render(
            scene_json=scene_path,
            scene_name=args.scene,
            quality=args.quality,
            video_dir=output_dir,
            output_fn=output_fn,
        )
    except runner.ManimMissing as exc:
        output_fn(f"error: {exc}")
        return 1
```

- [ ] **Step 9: Implement `dispatch.py`**

This replaces `main.py` wholesale. Every flag it had is preserved; `--non-interactive` gains `--no-input` as its clig.dev-conformant primary spelling.

```python
"""Parse the command line, decide which survey, run the verb.

Arguments are a contract: given a survey and a verb, nothing here prompts.
The menu appears only when there is nothing to act on and stdin is a
terminal -- clig.dev's rule that a prompt must never be the only way in.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from ..triangulate import solver
from ..triangulate.discovery import (
    SURVEY_SUBDIR,
    DiscoveryResult,
    SurveyFiles,
    discover_surveys,
)
from . import actions, menu
from .capability import VERBS, blocked_for

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATA_ROOT = _ROOT / "data" / "raw"
_DEFAULT_PROCESSED_ROOT = _ROOT / "data" / "processed"
# Generated output lives outside data/raw/, which stays purely raw.
_DEFAULT_OUTPUT_DIR = _ROOT / "data" / "output"

# What `survey.py 20260716` does with no verb and no terminal to ask at.
# Matches what `main.py 20260716` used to do.
_DEFAULT_VERB = "solve"

_MAPPRO_DIRS = ("mappro", "map_pro")


def split_target_and_verb(
    positionals: list[str],
) -> tuple[str | None, str | None, list[str]]:
    """Separate the survey from the verb.

    Two orderings are legal, and a verb name is what tells them apart:

        survey.py 20260716 solve       -> ("20260716", "solve", [])
        survey.py solve A.csv B.xlsx   -> (None, "solve", ["A.csv", "B.xlsx"])

    A survey named "solve" would be ambiguous. Survey names are dates, so
    this cannot arise in practice; `main` rejects it explicitly rather than
    resolving it silently.
    """
    if not positionals:
        return None, None, []
    if positionals[0] in VERBS:
        return None, positionals[0], positionals[1:]
    if len(positionals) >= 2 and positionals[1] in VERBS:
        return positionals[0], positionals[1], positionals[2:]
    return positionals[0], None, positionals[1:]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="survey.py",
        description="Convert, solve and animate gNB field surveys.",
    )
    parser.add_argument(
        "positionals", nargs="*", metavar="SURVEY|VERB|FILE",
        help="a survey name then a verb, or a verb then explicit file paths",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="print what each survey can do, and exit",
    )
    parser.add_argument(
        "--data-root", type=Path, default=_DEFAULT_DATA_ROOT,
        help="folder to scan for surveys (default: this project's data/raw/)",
    )
    parser.add_argument(
        "--processed-root", type=Path, default=_DEFAULT_PROCESSED_ROOT,
        help="where converted CSVs go (default: this project's data/processed/)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR,
        help="where solutions and videos go (default: this project's data/output/)",
    )
    parser.add_argument(
        "--no-input", "--non-interactive", action="store_true", dest="no_input",
        help="never prompt; error instead if inputs are missing",
    )
    parser.add_argument("--name", help="survey name for the report")
    parser.add_argument(
        "--csv", type=Path, metavar="OUT.csv",
        help="write the My Maps CSV here instead of the default output folder",
    )
    parser.add_argument(
        "--no-csv", action="store_true", help="skip writing the My Maps CSV",
    )
    parser.add_argument(
        "--sigma-distance", type=float, default=solver.SIGMA_DISTANCE_M,
        help=f"1-sigma distance error, metres (default {solver.SIGMA_DISTANCE_M})",
    )
    parser.add_argument(
        "--sigma-elevation", type=float, default=solver.SIGMA_ELEVATION_DEG,
        help=(
            f"1-sigma elevation error, degrees (default {solver.SIGMA_ELEVATION_DEG}). "
            "Only the ratio of the two sigmas affects the result."
        ),
    )
    parser.add_argument(
        "--quality", choices=("low", "medium", "hd", "uhd"), default="hd",
        help="render quality for `animate` (default hd)",
    )
    parser.add_argument(
        "--scene", choices=("GnbTriangulation", "GnbMath"),
        default="GnbTriangulation",
        help="which scene to render (default GnbTriangulation)",
    )
    return parser.parse_args(argv[1:])


def _no_surveys_message(data_root: Path) -> str:
    return (
        f"error: no surveys found under {data_root}. Expected MapPro exports "
        f"in {data_root / SURVEY_SUBDIR}/<NAME>/mappro/*.csv."
    )


def _describe(
    result: DiscoveryResult, data_root: Path, output_fn: OutputFn
) -> None:
    output_fn(f"  Surveys under {data_root}:")
    for files in result.surveys:
        can = ", ".join(v for v in VERBS if blocked_for(v, files) is None)
        output_fn(
            f"    {files.name}   {files.export_count} export(s)"
            f" · can: {can or 'nothing'}"
        )
    for name, reason in result.unreadable:
        output_fn(f"    {name}   unreadable: {reason}")


def _survey_name_for(path: Path) -> str:
    """Name a one-off survey after its folder, skipping the mappro/ level."""
    parent = path.parent.name
    if parent in _MAPPRO_DIRS:
        return path.parent.parent.name
    return parent


def _files_from_paths(verb: str, rest: list[str]) -> SurveyFiles | str:
    """Build a one-off SurveyFiles from paths typed on the command line."""
    paths = [Path(raw).expanduser() for raw in rest]
    for path in paths:
        if not path.is_file():
            return f"error: not a file: {path}"

    if verb == "convert":
        return SurveyFiles(
            name=_survey_name_for(paths[0]),
            mappro=paths[0],
            exports=tuple(paths),
            binoc=None,
            scene_json=None,
        )

    if len(paths) != 2:
        return (
            f"error: `survey.py {verb}` with explicit paths needs exactly two: "
            "the MapPro CSV and the sightings workbook."
        )
    return SurveyFiles(
        name=_survey_name_for(paths[0]),
        mappro=paths[0],
        exports=(paths[0],),
        binoc=paths[1],
        scene_json=None,
    )


def _resolve(
    args: argparse.Namespace,
    result: DiscoveryResult,
    target: str | None,
    verb: str | None,
    rest: list[str],
    *,
    interactive: bool,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> SurveyFiles | str:
    """Return the survey to act on, or an error message explaining why not."""
    if verb is not None and rest:
        return _files_from_paths(verb, rest)

    if target is not None:
        for files in result.surveys:
            if files.name == target:
                return files
        if Path(target).exists():
            return (
                f"error: {target} is a file. Put the verb first, e.g. "
                f"`survey.py convert {target}`."
            )
        found = ", ".join(f.name for f in result.surveys) or "none"
        return f"error: no survey named {target!r}. Found: {found}"

    if not result.surveys:
        return _no_surveys_message(args.data_root)
    if not interactive:
        return (
            "error: no survey given and not running interactively. Pass a "
            "survey name, or a verb with explicit file paths."
        )

    chosen = menu.select_survey(result, input_fn=input_fn, output_fn=output_fn)
    if chosen is None:
        return "error: cancelled."
    return chosen


def main(
    argv: list[str],
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    is_tty: bool | None = None,
) -> int:
    args = _parse_args(argv)
    if is_tty is None:
        is_tty = sys.stdin.isatty()
    interactive = is_tty and not args.no_input

    result = discover_surveys(args.data_root, args.output_dir)

    if args.list:
        if not result.surveys and not result.unreadable:
            output_fn(_no_surveys_message(args.data_root))
            return 1
        _describe(result, args.data_root, output_fn)
        return 0

    # A survey folder named after a verb would make `survey.py solve`
    # ambiguous. Dates never collide, but say so plainly if one ever does
    # rather than picking an interpretation.
    collisions = sorted({f.name for f in result.surveys} & set(VERBS))
    if collisions:
        output_fn(
            f"error: these surveys are named after verbs, so they cannot be "
            f"addressed unambiguously: {', '.join(collisions)}. Rename the "
            f"folder under {args.data_root / SURVEY_SUBDIR}/."
        )
        return 1

    target, verb, rest = split_target_and_verb(args.positionals)

    resolved = _resolve(
        args, result, target, verb, rest,
        interactive=interactive, input_fn=input_fn, output_fn=output_fn,
    )
    if isinstance(resolved, str):
        output_fn(resolved)
        return 1

    if verb is None:
        if interactive:
            verb = menu.select_verb(
                resolved, input_fn=input_fn, output_fn=output_fn
            )
            if verb is None:
                output_fn("cancelled.")
                return 1
        else:
            verb = _DEFAULT_VERB

    blocked = blocked_for(verb, resolved)
    if blocked is not None:
        output_fn(f"error: cannot {verb} {resolved.name}: {blocked.reason}")
        output_fn(f"  To fix: {blocked.fix}")
        return 1

    if verb == "convert":
        return actions.do_convert(
            resolved,
            raw_root=args.data_root,
            processed_root=args.processed_root,
            output_fn=output_fn,
        )
    if verb == "solve":
        return actions.do_solve(
            resolved, args, output_dir=args.output_dir, output_fn=output_fn
        )
    return actions.do_animate(
        resolved, args, output_dir=args.output_dir, output_fn=output_fn
    )
```

Delete the duplicate `split_target_and_verb` written in Step 3 if you drafted it in a scratch file — the version above is the one that ships.

`menu.py` needs three new imports for `select_verb`:

```python
from ..triangulate.discovery import SurveyFiles
from .capability import VERBS, blocked_for
```

- [ ] **Step 10: Write `survey.py`**

```python
#!/usr/bin/env python3
"""Field survey toolkit: convert MapPro exports, solve the gNB, render the story.

Usage:
    python survey.py                          interactive picker
    python survey.py 20260716                 pick a verb for one survey
    python survey.py 20260716 convert         MapPro exports -> My Maps CSV
    python survey.py 20260716 solve           trilaterate the gNB
    python survey.py 20260716 animate         render the animation
    python survey.py --list                   what each survey can do
    python survey.py convert FILE.csv...      convert files by path
    python survey.py solve SURVEY.csv BINOC.xlsx

Surveys are discovered under --data-root, which defaults to this project's
data/raw/. A survey needs only a MapPro export to be discovered; solving also
needs its <name>*.xlsx sightings workbook, and animating needs manimgl.
"""

from __future__ import annotations

import sys

from gnb_survey.cli.dispatch import main

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except KeyboardInterrupt:
        print("\ncancelled.", file=sys.stderr)
        raise SystemExit(130)
```

- [ ] **Step 11: Port the CLI tests**

```bash
git mv tests/triangulate/test_main.py tests/cli/test_dispatch_resolution.py
```

Change `import main as cli` to `from gnb_survey.cli import dispatch as cli`. The tests call `cli.main([...])` with injected `input_fn`/`output_fn`/`is_tty` — that contract is preserved, so most cases pass with only the import changed. Two need updating:

- any test asserting `--non-interactive` — add a sibling asserting `--no-input` behaves identically
- any test asserting a binoc-less survey produces "no campaign named" — it now produces a capability error naming the workbook

- [ ] **Step 12: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green, with the animate stubs from Step 8 satisfying `actions.py`'s imports.

- [ ] **Step 13: Smoke-test against the real data**

```bash
.venv/bin/python survey.py --list
.venv/bin/python survey.py 20260716 solve
```

Expected: the list shows nine surveys with `can: convert, solve`; the solve prints the same report `main.py` produces and writes `data/output/20260716_gnb.csv`. Compare against `git stash`-free `main.py 20260716` output if in doubt — they must match.

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat: add survey.py, a single noun-verb entry point with a capability-aware menu"
```

---

### Task 7: The animation seam

**Files:**
- Create: `gnb_survey/animate/scene_data.py`, `gnb_survey/animate/runner.py` (replacing Task 6's stubs)
- Modify: `docs/animation/triangulate_scene.py:28-56` (constants block) and `:265-280` (ellipse orientation)
- Create: `tests/animate/test_scene_data.py`, `tests/animate/test_runner.py`

**Interfaces:**
- Consumes: `models.Survey`, `models.Solution`, `geo.make_origin`, `geo.to_enu`, `report.format_solution`.
- Produces:
  - `scene_data.SCHEMA: int` = 1
  - `scene_data.build_scene(survey: Survey, solution: Solution) -> dict`
  - `scene_data.write_scene(survey: Survey, solution: Solution, path: Path) -> Path`
  - `scene_data.load_scene(path: Path) -> dict` (raises `ValueError` on schema mismatch)
  - `runner.ManimMissing(RuntimeError)`
  - `runner.SCENE_ENV: str` = `"GNB_SCENE_JSON"`
  - `runner.QUALITY_FLAGS: dict[str, str]`
  - `runner.build_argv(*, scene_file: Path, scene_name: str, quality: str, video_dir: Path) -> list[str]` — all keyword-only
  - `runner.render(*, scene_json: Path, scene_name: str, quality: str, video_dir: Path, output_fn: Callable[[str], None], scene_file: Path | None = None, runner_fn: Callable[[list[str], dict], int] | None = None, which_fn: Callable[[str], str | None] | None = None) -> int` — `runner_fn` and `which_fn` exist so the tests can drive it without manimgl installed

- [ ] **Step 1: Write the failing scene-data test**

Create `tests/animate/test_scene_data.py`:

```python
"""Scene data must reproduce the solver's own ENU frame, not an approximation."""

from __future__ import annotations

import json
import math

import pytest

from gnb_survey.animate import scene_data
from gnb_survey.triangulate import geo
from gnb_survey.triangulate.models import Solution, Survey, SurveyPoint

_POINTS = (
    SurveyPoint("Pt1", 1.35579855, 103.69391447, 32.5729, 17.0, 82.3),
    SurveyPoint("Pt2", 1.35585427, 103.69387394, 33.6284, 17.0, 98.2),
    SurveyPoint("Pt3", 1.35588038, 103.69377627, 34.5987, 16.0, 97.8),
)
_SURVEY = Survey(name="20260716", points=_POINTS)
_SOLUTION = Solution(
    survey_name="20260716",
    latitude=1.35534,
    longitude=103.69447,
    altitude_m=54.2,
    horiz_sigma_m=1.8,
    ellipse_major_m=4.36,
    ellipse_minor_m=0.73,
    vert_sigma_m=2.1,
    condition_number=120.0,
    n_points=3,
    residuals=(),
    ellipse_azimuth_deg=118.2,
)


def test_first_point_is_the_enu_origin():
    scene = scene_data.build_scene(_SURVEY, _SOLUTION)
    first = scene["points"][0]
    assert first["label"] == "Pt1"
    assert first["e"] == pytest.approx(0.0, abs=1e-6)
    assert first["n"] == pytest.approx(0.0, abs=1e-6)


def test_gnb_enu_matches_a_direct_geo_conversion():
    """The scene must not reimplement the projection -- same origin, same call."""
    origin = geo.make_origin(
        _POINTS[0].latitude, _POINTS[0].longitude, _POINTS[0].altitude_m
    )
    expected_e, expected_n, _ = geo.to_enu(
        _SOLUTION.latitude, _SOLUTION.longitude, _SOLUTION.altitude_m, origin
    )

    scene = scene_data.build_scene(_SURVEY, _SOLUTION)

    assert scene["gnb_en"][0] == pytest.approx(expected_e, abs=1e-3)
    assert scene["gnb_en"][1] == pytest.approx(expected_n, abs=1e-3)


def test_distances_survive_the_round_trip():
    """A point's plotted offset from the gNB must equal its measured range."""
    scene = scene_data.build_scene(_SURVEY, _SOLUTION)
    gnb_e, gnb_n = scene["gnb_en"]
    up = _SOLUTION.altitude_m - _POINTS[0].altitude_m
    first = scene["points"][0]

    horizontal = math.hypot(gnb_e - first["e"], gnb_n - first["n"])
    slant = math.hypot(horizontal, up)

    # Within a few metres of the measured 82.3 m -- this is a fabricated
    # solution, so the check is that the frame is coherent, not that it fits.
    assert slant == pytest.approx(first["dist_m"], abs=15.0)


def test_srls_seed_is_included_when_the_solver_used_one():
    scene = scene_data.build_scene(_SURVEY, _SOLUTION)
    seed = scene["srls_seed_en"]
    assert seed is not None
    assert len(seed) == 2
    assert all(isinstance(v, float) for v in seed)


def test_no_srls_seed_when_the_solver_fell_back():
    """seed_method says the closed form was skipped, so there is none to draw."""
    import dataclasses

    fallback = dataclasses.replace(_SOLUTION, seed_method="azimuth-multistart")

    scene = scene_data.build_scene(_SURVEY, fallback)

    assert scene["srls_seed_en"] is None


def test_write_then_load_round_trips(tmp_path):
    path = tmp_path / "20260716_scene.json"
    scene_data.write_scene(_SURVEY, _SOLUTION, path)

    loaded = scene_data.load_scene(path)

    assert loaded["schema"] == scene_data.SCHEMA
    assert loaded["survey"] == "20260716"
    assert loaded["ellipse"]["azimuth_deg"] == pytest.approx(118.2)


def test_a_stale_schema_is_refused(tmp_path):
    """A scene file from an older version must not silently draw a wrong picture."""
    path = tmp_path / "old_scene.json"
    path.write_text(json.dumps({"schema": 0, "survey": "x"}), encoding="utf-8")

    with pytest.raises(ValueError, match="schema"):
        scene_data.load_scene(path)
```

Before running, confirm the `Solution(...)` and `SurveyPoint(...)` keyword names above match `gnb_survey/triangulate/models.py` after Task 3. `SurveyPoint`'s field order is `label, latitude, longitude, altitude_m, elevation_deg, distance_m` — the positional args above follow it. If `Solution` has required fields not listed, add them.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/animate/test_scene_data.py -v`
Expected: FAIL with `NotImplementedError` from the Task 6 stub.

- [ ] **Step 3: Implement `scene_data.py`**

```python
"""Turn a solved survey into the numbers the animation draws.

The scene runs as a separate manimgl process, so it cannot be handed Python
objects -- it reads this JSON instead. The ENU frame is rebuilt exactly as
solver.solve_survey builds it (origin at the first point, same geo.to_enu),
so the picture is the solution rather than a redrawing of it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ..triangulate import geo
from ..triangulate.models import Solution, Survey
from ..triangulate.report import format_solution
from ..triangulate.srls import srls_position

SCHEMA = 1


def _srls_seed(points: list[dict], survey: Survey, solution: Solution):
    """The closed-form SR-LS seed the animation shows before refinement.

    Recomputed from the public srls_position rather than plumbed out of the
    solver, because it is a pure function of the same anchors and ranges. When
    the solver reports it fell back to the azimuth multi-start there was no
    usable seed, so there is nothing honest to draw.
    """
    if solution.seed_method != "srls":
        return None
    anchors = np.array([[p["e"], p["n"], 0.0] for p in points], dtype=float)
    ranges = np.array([p.distance_m for p in survey.points], dtype=float)
    try:
        seed = srls_position(anchors, ranges)
    except (ValueError, np.linalg.LinAlgError):
        # Same pair solver.solve_survey catches. Degenerate geometry means no
        # seed, not a broken run.
        return None
    return [round(float(seed[0]), 4), round(float(seed[1]), 4)]


def build_scene(survey: Survey, solution: Solution) -> dict:
    first = survey.points[0]
    origin = geo.make_origin(first.latitude, first.longitude, first.altitude_m)

    points = []
    for point in survey.points:
        east, north, _up = geo.to_enu(
            point.latitude, point.longitude, point.altitude_m, origin
        )
        points.append(
            {
                "label": point.label,
                "e": round(east, 4),
                "n": round(north, 4),
                "dist_m": point.distance_m,
                "elev_deg": point.elevation_deg,
            }
        )

    gnb_e, gnb_n, _gnb_u = geo.to_enu(
        solution.latitude, solution.longitude, solution.altitude_m, origin
    )

    return {
        "schema": SCHEMA,
        "survey": solution.survey_name,
        "origin": {
            "lat": origin.latitude,
            "lon": origin.longitude,
            "alt_m": origin.altitude_m,
        },
        "points": points,
        "gnb_en": [round(gnb_e, 4), round(gnb_n, 4)],
        "srls_seed_en": _srls_seed(points, survey, solution),
        "ellipse": {
            "major_m": solution.ellipse_major_m,
            "minor_m": solution.ellipse_minor_m,
            "azimuth_deg": solution.ellipse_azimuth_deg,
        },
        "result_lines": format_solution(solution).splitlines(),
    }


def write_scene(survey: Survey, solution: Solution, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_scene(survey, solution), indent=2), encoding="utf-8"
    )
    return path


def load_scene(path: Path) -> dict:
    """Read scene data, refusing anything this version cannot draw correctly."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    found = data.get("schema")
    if found != SCHEMA:
        raise ValueError(
            f"{path} has scene schema {found!r}, expected {SCHEMA}. "
            "Re-run `python survey.py <name> solve` to regenerate it."
        )
    return data
```

- [ ] **Step 4: Run the scene-data tests**

Run: `.venv/bin/python -m pytest tests/animate/test_scene_data.py -v`
Expected: 7 passed.

- [ ] **Step 4b: Wire the scene write into `do_solve`**

In `gnb_survey/cli/actions.py`, add `scene_data` to the animate import:

```python
from ..animate import runner, scene_data
```

and replace the `# Task 7 adds the scene-data write here.` comment left by Task 6 with:

```python
    scene_path = output_dir / f"{survey.name}_scene.json"
    scene_data.write_scene(survey, solution, scene_path)
    output_fn(f"  Wrote scene data to {scene_path}")
```

This is what makes `do_animate`'s solve-then-render chain work: it looks for exactly this file before deciding whether to solve first.

Run: `.venv/bin/python survey.py 20260716 solve`
Expected: the report, the My Maps CSV, and a new `data/output/20260716_scene.json`.

- [ ] **Step 5: Write the failing runner test**

Create `tests/animate/test_runner.py`:

```python
"""The runner builds a correct manimgl command and fails helpfully without it."""

from __future__ import annotations

from pathlib import Path

import pytest

from gnb_survey.animate import runner


def test_argv_uses_the_documented_flags():
    argv = runner.build_argv(
        scene_file=Path("/p/docs/animation/triangulate_scene.py"),
        scene_name="GnbTriangulation",
        quality="hd",
        video_dir=Path("/p/data/output"),
    )

    assert argv[0] == "manimgl"
    assert argv[1] == "/p/docs/animation/triangulate_scene.py"
    assert argv[2] == "GnbTriangulation"
    assert "-w" in argv
    assert "--hd" in argv
    assert "--video_dir" in argv
    assert argv[argv.index("--video_dir") + 1] == "/p/data/output"


@pytest.mark.parametrize(
    "quality,flag",
    [("low", "-l"), ("medium", "-m"), ("hd", "--hd"), ("uhd", "--uhd")],
)
def test_every_quality_maps_to_a_real_flag(quality, flag):
    argv = runner.build_argv(
        scene_file=Path("/s.py"),
        scene_name="GnbMath",
        quality=quality,
        video_dir=Path("/out"),
    )
    assert flag in argv


def test_an_unknown_quality_is_refused():
    with pytest.raises(ValueError, match="quality"):
        runner.build_argv(
            scene_file=Path("/s.py"),
            scene_name="GnbMath",
            quality="cinematic",
            video_dir=Path("/out"),
        )


def test_missing_manimgl_raises_with_the_install_hint(tmp_path):
    scene_json = tmp_path / "s.json"
    scene_json.write_text("{}", encoding="utf-8")

    with pytest.raises(runner.ManimMissing) as excinfo:
        runner.render(
            scene_json=scene_json,
            scene_name="GnbTriangulation",
            quality="hd",
            video_dir=tmp_path,
            output_fn=lambda _: None,
            runner_fn=None,
            which_fn=lambda _: None,   # pretend manimgl is not on PATH
        )

    message = str(excinfo.value)
    assert "manimgl" in message
    assert "animation" in message


def test_render_passes_the_scene_path_through_the_environment(tmp_path):
    scene_json = tmp_path / "s.json"
    scene_json.write_text("{}", encoding="utf-8")
    seen: dict = {}

    def fake_runner(argv, env):
        seen["argv"] = argv
        seen["env"] = env
        return 0

    code = runner.render(
        scene_json=scene_json,
        scene_name="GnbTriangulation",
        quality="low",
        video_dir=tmp_path,
        output_fn=lambda _: None,
        runner_fn=fake_runner,
        which_fn=lambda _: "/usr/local/bin/manimgl",
    )

    assert code == 0
    assert seen["env"][runner.SCENE_ENV] == str(scene_json)
    assert "-l" in seen["argv"]
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/animate/test_runner.py -v`
Expected: FAIL — `build_argv` does not exist on the stub.

- [ ] **Step 7: Implement `runner.py`**

```python
"""Invoke manimgl on the scene file, pointing it at one survey's scene data.

manimgl has no mechanism for forwarding unrecognised arguments to the Scene
being rendered -- its own argparse rejects them -- so the scene path travels
in an environment variable instead. Flags below are from manimgl's documented
CLI: -w (write file), -l/-m/--hd/--uhd (quality), --video_dir.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

MANIM_BINARY = "manimgl"
SCENE_ENV = "GNB_SCENE_JSON"
SCENE_FILE = (
    Path(__file__).resolve().parents[2] / "docs" / "animation" / "triangulate_scene.py"
)
QUALITY_FLAGS = {"low": "-l", "medium": "-m", "hd": "--hd", "uhd": "--uhd"}
_INSTALL_HINT = 'pip install -e ".[animation]"'


class ManimMissing(RuntimeError):
    """manimgl is not on PATH."""


def build_argv(
    *, scene_file: Path, scene_name: str, quality: str, video_dir: Path
) -> list[str]:
    try:
        quality_flag = QUALITY_FLAGS[quality]
    except KeyError:
        raise ValueError(
            f"unknown quality {quality!r}; expected one of "
            f"{', '.join(QUALITY_FLAGS)}"
        ) from None
    return [
        MANIM_BINARY,
        str(scene_file),
        scene_name,
        "-w",
        quality_flag,
        "--video_dir",
        str(video_dir),
    ]


def _default_runner(argv: list[str], env: dict[str, str]) -> int:
    return subprocess.call(argv, env=env)


def render(
    *,
    scene_json: Path,
    scene_name: str,
    quality: str,
    video_dir: Path,
    output_fn: Callable[[str], None],
    scene_file: Path | None = None,
    runner_fn: Callable[[list[str], dict], int] | None = None,
    which_fn: Callable[[str], str | None] | None = None,
) -> int:
    """Render one scene. Returns manimgl's exit code."""
    which_fn = which_fn or shutil.which
    if which_fn(MANIM_BINARY) is None:
        argv = build_argv(
            scene_file=scene_file or SCENE_FILE,
            scene_name=scene_name,
            quality=quality,
            video_dir=video_dir,
        )
        raise ManimMissing(
            f"{MANIM_BINARY} is not installed. Install it with:\n"
            f"    {_INSTALL_HINT}\n"
            f"then run:\n"
            f"    {SCENE_ENV}={scene_json} {' '.join(argv)}"
        )

    argv = build_argv(
        scene_file=scene_file or SCENE_FILE,
        scene_name=scene_name,
        quality=quality,
        video_dir=video_dir,
    )
    env = dict(os.environ)
    env[SCENE_ENV] = str(scene_json)
    Path(video_dir).mkdir(parents=True, exist_ok=True)

    output_fn(f"  Rendering {scene_name} at {quality} quality...")
    code = (runner_fn or _default_runner)(argv, env)
    if code == 0:
        output_fn(f"  Video written under {video_dir}")
    else:
        # manim's own stderr already reached the terminal. Paraphrasing a
        # missing-LaTeX or no-OpenGL-context error would only obscure it.
        output_fn(f"  {MANIM_BINARY} exited {code}; see its output above.")
    return code
```

- [ ] **Step 8: Run the runner tests**

Run: `.venv/bin/python -m pytest tests/animate/test_runner.py -v`
Expected: 8 passed.

- [ ] **Step 9: Make the scene read the environment**

In `docs/animation/triangulate_scene.py`, replace the constants block at lines 28–56 (from `import numpy as np` through `RESULT_LINES = [...]`) with:

```python
import json
import os

import numpy as np

from manimlib import *

# --- Scene data ---------------------------------------------------------------
# gnb_survey.animate.runner sets GNB_SCENE_JSON to one survey's solved geometry.
# Unset, the real Hall 14 numbers below are used, so this file still renders
# standalone as documentation.
SCENE_ENV = "GNB_SCENE_JSON"
SCENE_SCHEMA = 1


def _load_scene():
    path = os.environ.get(SCENE_ENV)
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("schema") != SCENE_SCHEMA:
        raise SystemExit(
            f"{path} has scene schema {data.get('schema')!r}, expected "
            f"{SCENE_SCHEMA}. Re-run `python survey.py <name> solve`."
        )
    return data


_SCENE = _load_scene()

if _SCENE is None:
    # Real solved geometry (Hall 14), local ENU metres.
    # (label, East, North, slant_distance_m, elevation_deg)
    SURVEY = [
        ("S1", 0.00, 0.00, 82.3, 17.0),
        ("S2", -8.81, 12.39, 98.2, 17.0),
        ("S3", 11.59, 27.27, 97.8, 16.0),
        ("S4", 21.30, 31.82, 95.5, 18.0),
        ("S?", 4.12, 22.41, 97.5, 17.0),   # "Sniffer optional"
        ("UE", 6.35, 4.06, 80.9, 18.0),
    ]
    SRLS_SEED_EN = (61.23, -54.76)        # closed-form global seed (E, N)
    GNB_EN = (61.58, -50.34)              # refined gNB position (E, N)
    ELLIPSE_MAJOR_M = 4.36                # 1-sigma semi-axes
    ELLIPSE_MINOR_M = 0.73
    ELLIPSE_AZIMUTH_DEG = None
    RESULT_LINES = [
        "lat  1.3524001°",
        "lon  103.6822124°",
        "alt  52.9 m",
        "SVY21  11183.6 E,  37167.6 N",
    ]
    SURVEY_NAME = "Hall 14"
else:
    SURVEY = [
        (p["label"], p["e"], p["n"], p["dist_m"], p["elev_deg"])
        for p in _SCENE["points"]
    ]
    seed = _SCENE.get("srls_seed_en")
    # None when SR-LS was degenerate and the solver fell back to a multi-start.
    # The seed beat then starts from the final fix, which is honest: there was
    # no closed-form seed to show.
    SRLS_SEED_EN = tuple(seed) if seed else tuple(_SCENE["gnb_en"])
    GNB_EN = tuple(_SCENE["gnb_en"])
    ELLIPSE_MAJOR_M = _SCENE["ellipse"]["major_m"]
    ELLIPSE_MINOR_M = _SCENE["ellipse"]["minor_m"]
    ELLIPSE_AZIMUTH_DEG = _SCENE["ellipse"]["azimuth_deg"]
    RESULT_LINES = _SCENE["result_lines"]
    SURVEY_NAME = _SCENE["survey"]
```

The values in the `if` branch are copied verbatim from the current file (lines 33–51) — verify them against `git show HEAD:docs/animation/triangulate_scene.py` rather than trusting this transcription. Leave the colour constants that follow (`C_POINT` onward) exactly where they are.

- [ ] **Step 10: Use the real ellipse orientation when it is known**

At lines 265–280 the scene currently derives the ellipse angle from the centroid→gNB line of sight. That was a stand-in because the azimuth was unavailable. Replace:

```python
        centroid = np.mean([[e, n] for _, e, n, *_ in SURVEY], axis=0)
        los = np.array(GNB_EN) - centroid
        ang = np.arctan2(los[1], los[0])
```

with:

```python
        if ELLIPSE_AZIMUTH_DEG is None:
            # No solved azimuth: fall back to the centroid->gNB line of sight,
            # which is roughly the major axis for a fan of range-only fixes.
            centroid = np.mean([[e, n] for _, e, n, *_ in SURVEY], axis=0)
            los = np.array(GNB_EN) - centroid
            ang = np.arctan2(los[1], los[0])
        else:
            # Solution.ellipse_azimuth_deg is a compass bearing (0 = north),
            # while manim rotates anticlockwise from +x (east).
            ang = np.radians(90.0 - ELLIPSE_AZIMUTH_DEG)
```

- [ ] **Step 11: Verify the scene file still parses**

manimgl is not installed, so the scene cannot be rendered here. Check the syntax and the fallback path instead:

```bash
.venv/bin/python -c "import ast,pathlib; ast.parse(pathlib.Path('docs/animation/triangulate_scene.py').read_text()); print('parses')"
```

Expected: `parses`.

- [ ] **Step 12: Verify the env-var path end to end**

```bash
.venv/bin/python survey.py 20260716 solve
.venv/bin/python - <<'PY'
import json, os, pathlib
os.environ["GNB_SCENE_JSON"] = "data/output/20260716_scene.json"
data = json.loads(pathlib.Path(os.environ["GNB_SCENE_JSON"]).read_text())
assert data["schema"] == 1
assert len(data["points"]) >= 3
assert data["ellipse"]["azimuth_deg"] is not None
print("scene data OK:", data["survey"], len(data["points"]), "points")
PY
```

Expected: `scene data OK: 20260716 <N> points`.

- [ ] **Step 13: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "feat: drive the animation from solved survey data via a scene JSON seam"
```

---

### Task 8: Delete the old entry points and update the docs

**Files:**
- Delete: `main.py` (`csv_to_mymaps.py` already went in Task 4 Step 8b)
- Modify: `README.md`, `docs/TRIANGULATE_README.md`, `docs/mappro_guide/MapPro_Guide.tex`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: nothing new. This task removes the last duplicate and makes the docs true.

- [ ] **Step 1: Confirm nothing still imports it**

```bash
grep -rn "^import main\|^from main\|import csv_to_mymaps\|from csv_to_mymaps" \
  --include="*.py" . | grep -v '/\.venv/'
```

Expected: no output. If `tests/` still references either, Task 4 or 6 left a test behind — fix it before deleting.

- [ ] **Step 2: Delete it**

```bash
git rm main.py
```

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all green. A failure here means a test was still reaching into a deleted module.

- [ ] **Step 4: Re-verify both verbs against real data**

```bash
.venv/bin/python survey.py --list
.venv/bin/python survey.py 20260716 convert
.venv/bin/python survey.py 20260716 solve
```

Expected: convert writes into `data/processed/surveys/20260716/mappro/`; solve writes `data/output/20260716_gnb.csv` and `data/output/20260716_scene.json`.

- [ ] **Step 5: Update `README.md`**

Replace the Quick Start block:

```bash
# Install (from a Python 3.10+ interpreter)
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e .              # add ".[animation]" for the ManimGL scenes

# What can each survey do?
python survey.py --list

# Convert one survey's MapPro exports to My Maps CSVs
python survey.py 20260716 convert

# Solve the gNB position
python survey.py 20260716 solve

# Render the animation from that solution
python survey.py 20260716 animate

# Or just run it and pick from the menu
python survey.py

# Tests
pytest
```

Then update the Project Structure block: `main.py` and `csv_to_mymaps.py` become `survey.py`; `gnb_triangulate/` becomes `gnb_survey/` with its four subpackages; add `pyproject.toml`; remove the `requirements.txt` reference. Correct the dependency section to say Python 3.10+, and note ManimGL is an optional extra.

- [ ] **Step 6: Update `docs/TRIANGULATE_README.md`**

Seven call sites at lines 19, 26–28 and 184–187. Rewrite as:

```
python survey.py                            # interactive picker
python survey.py 20260716                   # pick a verb for one survey
python survey.py 20260716 solve             # solve, no prompts
python survey.py --list                     # what each survey can do
python survey.py solve "/path/SURVEY.csv" "/path/BINOC.xlsx"
```

Line 150 says `csv_to_mymaps.py` lives "in the `map-data-plot` repository" — that is stale twice over. Replace with: "Conversion is `python survey.py <name> convert`, in this repository."

- [ ] **Step 7: Update `docs/mappro_guide/MapPro_Guide.tex`**

Three call sites at lines 343, 346 and 349:

```latex
python3 survey.py convert 20260626.csv
python3 survey.py convert file1.csv file2.csv
python3 survey.py --help
```

- [ ] **Step 7b: Sweep the old vocabulary out of the docs**

Task 3 renamed `campaign` to `survey` in the code but scoped itself to `*.py`, so the prose still says "campaign" in roughly 19 places across `README.md` and `docs/TRIANGULATE_README.md` — including a file-tree listing a `campaign.py` that no longer exists (it is `assemble.py` now).

```bash
grep -rni "campaign" --include="*.md" --include="*.tex" . | grep -v '/\.venv/'
```

Rewrite each hit to the survey vocabulary: the container is a **survey**, its MapPro CSV is the **mappro** export, its sightings workbook is the **binoc** workbook. Watch for file-tree blocks and command examples, which are easy to skim past.

- [ ] **Step 8: Confirm no stale references remain**

```bash
grep -rn "csv_to_mymaps\|gnb_triangulate\|requirements.txt\|main\.py" \
  --include="*.md" --include="*.tex" . | grep -v '/\.venv/'
grep -rni "campaign" --include="*.md" --include="*.tex" . | grep -v '/\.venv/'
```

Expected: no output from either. Hits inside `docs/RESEARCH.md` describing historical work may stay if they are clearly retrospective — read each before deciding.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor!: replace main.py and csv_to_mymaps.py with survey.py

BREAKING CHANGE: both former entry points are gone. Use
  python survey.py <name> convert|solve|animate
See README.md for the full command surface."
```

- [ ] **Step 10: Final verification**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python survey.py --list
git status --short
```

Expected: all tests pass; the list prints; the working tree is clean.

---

## Notes for the implementer

**Why the converter is quarantined.** `gnb_survey/convert/` importing NumPy would not fail any functional test — it would just quietly make the tool unusable on a stock field laptop, discovered months later in a car park with no signal. `tests/test_convert_is_stdlib_only.py` is the only thing standing between you and that. If it fails, move the offending code out of `convert/` rather than relaxing the test.

**Why blocked verbs are shown, not hidden.** Today, a survey with no workbook vanishes from the picker entirely, so you count nine entries where you expected ten and have no idea why. Listing `solve — needs 20260722*.xlsx` costs one line and answers the question.

**Why an environment variable.** manimgl's documented CLI has no pass-through for user arguments — its own argparse rejects unknown flags. The env var is the only channel that does not require patching manim.

**Where the numbers come from.** `scene_data.build_scene` rebuilds the origin the same way `solver.solve_survey` does, and calls the same `geo.to_enu`. If you find yourself writing a projection formula, stop — you are reimplementing something that already exists and will drift from it.
