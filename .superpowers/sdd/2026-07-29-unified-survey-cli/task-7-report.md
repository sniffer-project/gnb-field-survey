# Task 7 report: the animation seam

Branch `worktree-unified-survey-cli`. Starting commit `af8bbd0`.
Interpreter `.venv/bin/python` (Python 3.13.14), pytest 9.1.1.

**Status: DONE_WITH_CONCERNS** — implementation and verification are complete.
The concern is a contradiction in the supplied SR-LS implementation block:
three 3-D anchors cannot make its four-column GTRS matrix full rank. The
explicit three-point test required a seed, so, with parent approval, the
animation recomputes the public two-dimensional East/North SR-LS solution.

---

## Step-by-step

### Steps 1–4 — scene-data RED/GREEN

Created `tests/animate/test_scene_data.py` from the brief after confirming the
`SurveyPoint` positional order and `Solution` keywords against
`gnb_survey/triangulate/models.py`.

The mandatory RED run:

```text
.venv/bin/python -m pytest tests/animate/test_scene_data.py -v
7 failed in 0.06s
```

Six failures came from the Task 6 `NotImplementedError`; the schema test found
the expected missing `load_scene` attribute. This proved the tests exercised
the stub rather than existing behaviour.

The brief's literal implementation then reached an informative intermediate
state: `6 passed, 1 failed`. `test_srls_seed_is_included_when_the_solver_used_one`
received `None`. The reason is structural: three anchors shaped `(3, 3)` make
`A = [-2a, 1]` shape `(3, 4)`, so `A.T @ A` is necessarily singular; setting
every Up coordinate to zero makes it more explicitly degenerate.
`srls_position` correctly raised `ValueError`.

The parent approved the smallest contract-preserving correction: call the
public `srls_position` with the top-down animation's two-dimensional East/North
anchors. The exact three-point test fixture remains unchanged. The solution's
`seed_method == "srls"` gate and the required
`(ValueError, np.linalg.LinAlgError)` exception pair remain unchanged.

Final GREEN:

```text
.venv/bin/python -m pytest tests/animate/test_scene_data.py -v
7 passed in 0.23s
```

`scene_data.py` now has typed implementations of `SCHEMA`, `build_scene`,
`write_scene`, and `load_scene`. It rebuilds the solver's ENU frame through
the public `geo.make_origin`/`geo.to_enu`, serializes the result and report,
and refuses stale schemas.

### Step 4b — writer and discovery integration

`gnb_survey/cli/actions.py` now imports `scene_data` beside `runner`, preserves
the existing unconditional `output_dir.mkdir(...)`, and always writes:

```text
<output_dir>/<files.name>_scene.json
```

with the required `Wrote scene data to ...` message. The discovered folder
name is the stable filesystem identity; `survey.name` remains the custom
display/report name stored inside the JSON.

I added an integration test to `tests/triangulate/test_discovery.py`. It runs a
real fixture solve through `dispatch.main`, calls
`discover_surveys(fixtures, output_dir)`, and asserts that the solved survey's
`scene_json` is exactly `output_dir / "20260716_scene.json"`.

RED before wiring:

```text
assert None == output_dir / "20260716_scene.json"
1 failed in 0.73s
```

GREEN after wiring:

```text
1 passed in 0.61s
```

This pins the writer and discovery sides to the same filename instead of
silently relying on Task 5's previously unexercised discovery branch.

### Steps 5–8 — runner RED/GREEN

Created `tests/animate/test_runner.py` from the brief.

The mandatory RED run:

```text
.venv/bin/python -m pytest tests/animate/test_runner.py -v
8 failed in 0.07s
```

Six collected items failed because `build_argv` did not exist and two reached
the Task 6 `NotImplementedError` in `render`.

Implemented the typed runner with:

- keyword-only `build_argv` and `render`;
- documented quality flags and `-w`/`--video_dir`;
- dependency-injected `runner_fn` and `which_fn`;
- `GNB_SCENE_JSON` in a copied process environment, because ManimGL rejects
  unknown user CLI flags;
- injected `output_fn` only — no library `print()`;
- a clear `ManimMissing` install hint and unchanged child exit code.

Final GREEN:

```text
.venv/bin/python -m pytest tests/animate/test_runner.py -v
8 passed in 0.01s
```

### Initial independent review fix — `animate --name` (superseded)

Independent review found that `do_solve` correctly wrote
`<args.name>_scene.json` when `--name` was supplied, while `do_animate` still
passed `<files.name>_scene.json` to the runner. Added
`tests/animate/test_actions.py` under the Task 7 animation tests.

The bug was reproduced before changing production code:

```text
expected Cetran_scene.json, got 20260716_scene.json
1 failed in 0.57s
```

`do_animate` now derives its scene name from the same
`args.name or files.name` expression as `do_solve`. GREEN:

```text
1 passed in 0.56s
```

A later code-quality review correctly found that making both sides custom was
still incomplete: discovery only knows the stable folder name. The second
review loop below replaces this initial fix with stable source identity.

### Code-quality review loop — stable identity and schema validation

Review after commit `20fe755` returned two Important issues.

**Stable identity.** Added/updated focused coverage for:

- solve with `--name Cetran` writing `20260716_scene.json`;
- JSON retaining `"survey": "Cetran"` for display/reporting;
- rediscovery populating `scene_json`;
- capability allowing animation after the workbook is archived;
- `do_animate --name Cetran` rendering that same stable path.

RED:

```text
2 failed in 0.76s
rendered Cetran_scene.json instead of 20260716_scene.json
rediscovery returned scene_json=None
```

The minimal fix keys both writer and render lookup to `files.name`. GREEN:

```text
2 passed in 0.64s
```

This intentionally deviates from the brief's literal
`<survey.name>_scene.json` wording. A custom `--name` is presentation metadata,
not durable source identity. If it controls the filename, discovery cannot
find the scene later and an archived workbook makes animation unavailable.

**Malformed schema-1 JSON.** Added a standard-library-only shared validator at
`gnb_survey/animate/scene_schema.py`. It validates every field consumed by the
scene: required top-level fields; origin; point objects and numeric values;
two-number gNB/seed vectors (or `None` seed); ellipse fields with nullable
numeric azimuth; and string result lines. It also rejects boolean schema
values, non-finite numbers, empty points, malformed JSON, and stale schemas
with actionable regeneration guidance.

The first RED captured four malformed schema-1 payloads being accepted and
the standalone scene reaching `ModuleNotFoundError: manimlib` before it could
validate:

```text
5 failed in 0.29s
```

Two additional edge regressions (boolean schema and empty points) were each
observed RED:

```text
2 failed in 0.24s
```

`scene_data.load_scene` delegates to this one validator. The standalone scene
resolves the project root from `__file__`, imports the shared stdlib loader,
loads at import time, and converts `OSError`/`ValueError` into a clear
`SystemExit` before importing `manimlib`. No divergent validation logic and no
ManimGL dependency were introduced. GREEN:

```text
7 passed in 0.21s
```

Final self-review found that converting an extremely large JSON integer to
`float` could raise a raw `OverflowError`. A focused large-vector-component
regression reproduced that error RED, then passed after `_number` mapped
overflow to the same actionable field-specific `ValueError`.

### Steps 9–10 — scene environment and ellipse orientation

`docs/animation/triangulate_scene.py` now reads schema-1 scene JSON from
`GNB_SCENE_JSON`. With no variable set, it retains the Hall 14 documentation
geometry. A missing SR-LS seed falls back to the final fix for that animation
beat; it does not invent a closed-form seed.

When `ellipse.azimuth_deg` is known, the compass bearing is converted to
Manim's mathematical angle with:

```python
np.radians(90.0 - ELLIPSE_AZIMUTH_DEG)
```

When it is `None`, the scene retains the required centroid-to-gNB
line-of-sight fallback.

### Step 11 — scene syntax and Hall 14 fallback

The exact AST command from the brief returned:

```text
parses
```

The valid scene was not imported because `manimlib` is unavailable. The new
invalid-data regression safely executes only the pre-Manim prefix: shared
validation raises `SystemExit` before `from manimlib import *`. This proves
bad input gets a clear field-specific error without requiring ManimGL.

I separately parsed `af8bbd0:docs/animation/triangulate_scene.py` and the
working scene, evaluated the six Hall 14 assignments, and compared them
one-by-one. All matched:

```text
ELLIPSE_MAJOR_M MATCH 4.36
ELLIPSE_MINOR_M MATCH 0.73
GNB_EN MATCH (61.58, -50.34)
RESULT_LINES MATCH [...]
SRLS_SEED_EN MATCH (61.23, -54.76)
SURVEY MATCH [...]
```

`ELLIPSE_AZIMUTH_DEG = None` and `SURVEY_NAME = "Hall 14"` are new seam
metadata; every pre-existing fallback value is unchanged.

### ManimGL / Homebrew limitation

The user requested Homebrew installation. The exact checks were:

```text
brew search manimgl
manim
animdl

brew info manim
manim: stable 0.20.1
Animation engine for explanatory math videos
https://www.manim.community
Not installed

.venv/bin/python -m pip show manimgl
WARNING: Package(s) not found: manimgl
```

Homebrew has no `manimgl` formula. Its `manim` formula is Manim Community,
which does not provide the required `manimgl` executable / `manimlib` import,
so it was not installed as an incompatible substitute. Per the correction
from the parent, the earlier PyPI install request was paused before any install
started. No package or tracked dependency metadata changed. A real
non-interactive render therefore remained unavailable; AST, runner-injection,
real scene-data loading, and schema checks provide the bounded verification.

### Step 12 — end-to-end scene seam

Ran the exact real solve:

```text
.venv/bin/python survey.py 20260716 solve
...
Wrote 37 rows to .../data/output/20260716_gnb.csv
Wrote scene data to .../data/output/20260716_scene.json
```

Both files exist. The post-solve check reported:

```text
scene data OK: 20260716 6 points azimuth 98.7272521839829
```

Thus the JSON has schema 1, six points (at least three), and a non-null solved
ellipse azimuth. The generated `data/output/` files are intentionally ignored
runtime outputs, not committed artifacts.

I separately called the real `gnb_survey.animate.scene_data.load_scene` on
that file (`load_scene OK: 20260716 6 points`) and on a temporary schema-0
file, which raised the required `ValueError` with regeneration guidance.

The review-loop E2E used a custom display name:

```text
.venv/bin/python survey.py 20260716 solve --name Cetran
Wrote 37 rows to .../data/output/Cetran_gnb.csv
Wrote scene data to .../data/output/20260716_scene.json
stable scene identity OK: 20260716 -> 20260716_scene.json display Cetran
```

Rediscovery found that stable file, and
`animate_blocked(dataclasses.replace(found, binoc=None),
manim_available=True)` returned `None`.

### Step 13 — tests and count reconciliation

Focused seam/discovery/stdlib-guard verification:

```text
.venv/bin/python -m pytest tests/animate \
  tests/triangulate/test_discovery.py tests/cli/test_capability.py \
  tests/test_convert_is_stdlib_only.py -q
51 passed in 0.70s
```

This explicitly confirms that `gnb_survey/convert/` remains stdlib-only and
its permanent guard was not weakened.

Full suite:

```text
.venv/bin/python -m pytest -q
201 passed in 1.42s
```

Count reconciliation from Task 6's exact baseline:

| delta | source |
|---:|---|
| 175 | Task 6 baseline |
| +7 | scene-data tests |
| +8 | runner items (the quality test parametrizes to four items) |
| +1 | required writer/discovery integration |
| +1 | independent-review regression for `animate --name` |
| +1 | custom-name discovery/archive-capability regression |
| +7 | malformed schema-1 validation items |
| +1 | standalone pre-Manim validation regression |
| **201** | final total |

The plan's “roughly 190” note omitted the required discovery integration item;
two review loops then added ten regression items.
No old test was removed or weakened.

Additional checks passed: `compileall`, `git diff --check`, and a source grep
confirmed no `print()` in `gnb_survey/animate` or `cli/actions.py`. Importing
`scene_schema` under `.venv/bin/python -S -E` also passed, proving the shared
validator itself is standard-library-only. An independent review of the
complete follow-up diff returned no findings and separately passed all 201
tests.

### Step 14 — commit

The task's feature commit is `20fe755`. The code-quality review fixes are in a
separate conventional follow-up commit; the original commit was not amended.

---

## Files changed

- `gnb_survey/animate/scene_data.py`
- `gnb_survey/animate/scene_schema.py`
- `gnb_survey/animate/runner.py`
- `gnb_survey/cli/actions.py`
- `docs/animation/triangulate_scene.py`
- `tests/animate/test_scene_data.py`
- `tests/animate/test_scene_script.py`
- `tests/animate/test_runner.py`
- `tests/animate/test_actions.py`
- `tests/triangulate/test_discovery.py`
- `.superpowers/sdd/2026-07-29-unified-survey-cli/task-7-report.md`

## Concerns

- The supplied 3-D SR-LS snippet contradicts the exact three-point test.
  The approved 2-D East/North call is supported by the public API and is the
  honest horizontal seed for a top-down animation, but it is not a
  byte-for-byte replay of the solver's unexposed 3-D seed. The scene only
  includes it when `solution.seed_method == "srls"`.
- A true ManimGL render could not be attempted through Homebrew because no
  compatible formula exists. No incompatible Community-edition substitute
  was installed.
- The brief deliberately changed the standalone Hall 14 fallback from the old
  perpendicular-to-LOS orientation to major-axis-along-LOS when the solved
  azimuth is absent. Independent review noted that the bundled Hall 14
  fallback therefore differs by roughly 90 degrees from the known generated
  survey azimuth. The parent explicitly ruled to retain Step 10: this is the
  intended approximation, while generated schema-1 JSON uses the authoritative
  non-null solved azimuth.
- The stable scene filename intentionally uses the discovered folder name
  rather than the brief's literal `survey.name`, because `--name` must remain
  display metadata if rediscovery and archived-workbook animation are to work.
